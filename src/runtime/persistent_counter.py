import os
import tempfile
import threading
import json
from src.runtime.state import RuntimeStateController
from src.security.hardware import TPM2HardwareAttestation
from src.security.kms.aws_kms import AWSKMSProvider
from src.security.crypto import StrictCryptographicEngine

class PersistentBootCounter:
    """
    SEC-004: Boot counter protected by KMS/TPM signing, entirely eliminating local env secrets.
    """
    _lock = threading.Lock()
    _counter_file = ".boot_counter_state"
    _last_seen_counter: int = 0

    @classmethod
    def get_and_increment(cls) -> int:
        with cls._lock:
            hardware_quote = TPM2HardwareAttestation.get_pcr_quote_hash()
            counter = 1
            kms = AWSKMSProvider()
            kms_key_id = os.environ.get("TE_BOOT_COUNTER_KMS_KEY_ID")
            
            if not kms_key_id:
                raise RuntimeError("CRITICAL SECURITY ERROR: KMS Key ID for boot counter missing.")
                
            kms_pub_key = kms.get_public_key(kms_key_id).hex()

            if os.path.exists(cls._counter_file):
                try:
                    with open(cls._counter_file, "r") as f:
                        state = json.load(f)
                        
                    stored_quote = state.get("hardware_quote")
                    stored_count = state.get("counter", 0)
                    stored_sig = state.get("signature", "")
                    
                    payload = f"{stored_quote}\n{stored_count}".encode("utf-8")
                    
                    if not StrictCryptographicEngine.verify_ed25519(kms_pub_key, stored_sig, payload):
                        RuntimeStateController.revoke_and_halt("Boot counter KMS signature verification failed!", fatal=True)
                        raise RuntimeError("CRITICAL SECURITY ERROR: Boot counter integrity violation.")
                    
                    if stored_quote != hardware_quote:
                        RuntimeStateController.revoke_and_halt("Hardware TPM quote mismatch in boot counter. Machine clone detected.", fatal=True)
                        raise RuntimeError("CRITICAL SECURITY ERROR: TPM quote mismatch.")
                        
                    counter = int(stored_count) + 1
                except Exception as e:
                    if isinstance(e, RuntimeError): raise
                    RuntimeStateController.revoke_and_halt("Failed to read signed boot counter state safely.", fatal=True)
                    raise RuntimeError("FATAL: Failed to read persistent monotonic boot counter.") from e
            
            if counter <= cls._last_seen_counter:
                RuntimeStateController.revoke_and_halt("Boot counter rollback attack detected!", fatal=True)
                raise RuntimeError("CRITICAL SECURITY ERROR: Boot counter rollback detected.")

            message_to_sign = f"{hardware_quote}\n{counter}".encode("utf-8")
            sig = kms.sign(kms_key_id, message_to_sign).hex()
            
            new_state = {
                "hardware_quote": hardware_quote,
                "counter": counter,
                "signature": sig
            }

            dir_name = os.path.dirname(os.path.abspath(cls._counter_file))
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)

            try:
                with tempfile.NamedTemporaryFile("w", dir=dir_name or ".", delete=False) as tf:
                    json.dump(new_state, tf)
                    tf.flush()
                    os.fsync(tf.fileno())
                    temp_name = tf.name
                os.replace(temp_name, cls._counter_file)
            except Exception as e:
                if 'temp_name' in locals() and os.path.exists(temp_name):
                    try: os.unlink(temp_name)
                    except Exception: pass
                RuntimeStateController.revoke_and_halt(f"Atomic persistence of boot counter failed: {str(e)}", fatal=True)
                raise RuntimeError(f"FATAL: Atomic persistence of boot counter failed: {str(e)}") from e
            
            cls._last_seen_counter = counter
            return counter