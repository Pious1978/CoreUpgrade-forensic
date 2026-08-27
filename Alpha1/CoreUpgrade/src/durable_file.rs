use std::fs::File;
use std::io::{Read, Seek, Write};

pub trait DurableFile: Read + Write + Seek {
    fn sync_data(&mut self) -> std::io::Result<()>;
    fn set_len(&mut self, size: u64) -> std::io::Result<()>;
}

impl DurableFile for File {
    fn sync_data(&mut self) -> std::io::Result<()> {
        self.sync_all()
    }
    fn set_len(&mut self, size: u64) -> std::io::Result<()> {
        File::set_len(self, size)
    }
}