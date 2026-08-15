use std::io::{self, Cursor, Read, Write, Seek, SeekFrom};
use gateway::durable_file::DurableFile;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum JournalFaultPoint {
    BeforeMagic,
    AfterMagic,
    AfterLength,
    DuringPayload,
    AfterPayload,
    DuringChecksum,
    AfterChecksum,
    BeforeFirstSync,
    AfterFirstSync,
    DuringCommitMarker,
    AfterCommitMarker,
    BeforeSecondSync,
    AfterSecondSync,
}

#[derive(Debug, Clone, Copy)]
pub enum FaultAction {
    None,
    Crash,            // Simulated process death
    ShortWrite(usize), // Write N bytes, then crash
    IoError,          // Return temporary OS error
}

#[derive(Debug, Clone)]
pub struct InjectedCrash {
    pub transaction_index: usize,
    pub fault_point: JournalFaultPoint,
    pub action: FaultAction,
}

pub struct FaultInjectingFile {
    pub inner: Cursor<Vec<u8>>,
    config: InjectedCrash,
    
    // State Tracking
    current_tx_index: usize,
    tx_byte_offset: usize,
    expected_payload_len: usize,
    is_crashed: bool,
}

impl FaultInjectingFile {
    pub fn new(config: InjectedCrash, existing_data: Vec<u8>) -> Self {
        let mut cursor = Cursor::new(existing_data);
        cursor.seek(SeekFrom::End(0)).unwrap(); // Start at end for appending
        
        Self {
            inner: cursor,
            config,
            current_tx_index: 0,
            tx_byte_offset: 0,
            expected_payload_len: 0,
            is_crashed: false,
        }
    }

    fn check_fault(&mut self, point: JournalFaultPoint, data_len: usize) -> io::Result<usize> {
        if self.is_crashed {
            return Err(io::Error::new(io::ErrorKind::BrokenPipe, "Simulated crash state"));
        }

        if self.current_tx_index == self.config.transaction_index && self.config.fault_point == point {
            match self.config.action {
                FaultAction::Crash => {
                    self.is_crashed = true;
                    return Err(io::Error::new(io::ErrorKind::BrokenPipe, "Injected crash"));
                }
                FaultAction::ShortWrite(n) => {
                    let write_len = std::cmp::min(n, data_len);
                    self.is_crashed = true; // Crashes immediately after the short write
                    return Ok(write_len);
                }
                FaultAction::IoError => {
                    return Err(io::Error::new(io::ErrorKind::Other, "Injected IO Error"));
                }
                FaultAction::None => {}
            }
        }
        Ok(data_len)
    }

    fn advance_state(&mut self, bytes_written: usize, data: &[u8]) {
        self.tx_byte_offset += bytes_written;

        // Sniff the payload length to accurately track phase transitions
        if self.tx_byte_offset == 8 {
            let mut len_bytes = [0u8; 4];
            len_bytes.copy_from_slice(&self.inner.get_ref()[self.inner.position() as usize - 4 .. self.inner.position() as usize]);
            self.expected_payload_len = u32::from_be_bytes(len_bytes) as usize;
        }

        let total_tx_size = 4 + 4 + self.expected_payload_len + 48 + 4; // Magic + Len + Payload + Checksum + Comm
        if self.tx_byte_offset >= total_tx_size {
            self.current_tx_index += 1;
            self.tx_byte_offset = 0;
            self.expected_payload_len = 0;
        }
    }
}

// Implement standard I/O traits intersecting with the fault state machine
impl Write for FaultInjectingFile {
    fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
        if self.is_crashed { return Err(io::Error::new(io::ErrorKind::BrokenPipe, "Simulated crash state")); }

        // State Machine determination based on tx_byte_offset
        let point = match self.tx_byte_offset {
            0 => JournalFaultPoint::BeforeMagic,
            4 => JournalFaultPoint::AfterMagic,
            8 => JournalFaultPoint::AfterLength,
            x if x > 8 && x < 8 + self.expected_payload_len => JournalFaultPoint::DuringPayload,
            x if x == 8 + self.expected_payload_len => JournalFaultPoint::AfterPayload,
            x if x > 8 + self.expected_payload_len && x < 8 + self.expected_payload_len + 48 => JournalFaultPoint::DuringChecksum,
            x if x == 8 + self.expected_payload_len + 48 => JournalFaultPoint::AfterChecksum,
            x if x > 8 + self.expected_payload_len + 48 && x < 8 + self.expected_payload_len + 48 + 4 => JournalFaultPoint::DuringCommitMarker,
            _ => JournalFaultPoint::AfterCommitMarker,
        };

        let allowed_len = self.check_fault(point, buf.len())?;
        if allowed_len == 0 && buf.len() > 0 {
            return Err(io::Error::new(io::ErrorKind::BrokenPipe, "Short write resulted in 0 bytes"));
        }

        let written = self.inner.write(&buf[..allowed_len])?;
        self.advance_state(written, &buf[..allowed_len]);
        
        if self.is_crashed {
            Err(io::Error::new(io::ErrorKind::BrokenPipe, "Crashed during short write"))
        } else {
            Ok(written)
        }
    }

    fn flush(&mut self) -> io::Result<()> {
        self.inner.flush()
    }
}

impl DurableFile for FaultInjectingFile {
    fn sync_data(&mut self) -> io::Result<()> {
        if self.is_crashed { return Err(io::Error::new(io::ErrorKind::BrokenPipe, "Crash")); }
        
        let point = if self.tx_byte_offset < 8 + self.expected_payload_len + 48 + 4 {
            JournalFaultPoint::BeforeFirstSync
        } else {
            JournalFaultPoint::BeforeSecondSync
        };
        
        self.check_fault(point, 0)?;
        Ok(())
    }

    fn set_len(&mut self, len: u64) -> io::Result<()> {
        self.inner.get_mut().truncate(len as usize);
        Ok(())
    }
}

// Pass-through Read and Seek implementations omitted for brevity...
impl Read for FaultInjectingFile { fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> { self.inner.read(buf) } }
impl Seek for FaultInjectingFile { fn seek(&mut self, pos: SeekFrom) -> io::Result<u64> { self.inner.seek(pos) } }