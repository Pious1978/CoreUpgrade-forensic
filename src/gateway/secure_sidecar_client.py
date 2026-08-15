import os
import socket
import json
from typing import Dict, Any

class SecureExecutionGateway:
    """
    CRITICAL-001: Python is no longer the root of trust.
    The Python engine proposes trades to a hardened Rust/C++ sidecar via UDS.
    The sidecar independently verifies the certificate epoch token, risk limits, 
    and exchange connectivity.
    """
    _UDS_SOCKET_PATH = "/run/trading-engine/secure-gateway.sock"

    @classmethod
    def submit_order_to_hardware_gateway(cls, order_payload: Dict[str, Any], epoch_token: str, signature: str) -> bool:
        if not os.path.exists(cls._UDS_SOCKET_PATH):
            raise RuntimeError("CRITICAL: Secure Execution Gateway socket unavailable.")
            
        payload = {
            "order": order_payload,
            "authorization": {
                "epoch_token": epoch_token,
                "signature": signature
            }
        }
        
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.05) # 50ms strict latency bound
                client.connect(cls._UDS_SOCKET_PATH)
                client.sendall(json.dumps(payload).encode("utf-8") + b"\n")
                
                response_data = client.recv(4096)
                response = json.loads(response_data.decode("utf-8"))
                
                if response.get("status") != "ACCEPTED":
                    raise RuntimeError(f"Hardware Gateway Rejected Order: {response.get('reason')}")
                return True
        except socket.timeout:
            raise RuntimeError("CRITICAL: Secure Gateway timeout. Order state unknown.")
        except Exception as e:
            raise RuntimeError(f"CRITICAL: Secure Gateway communication failed: {str(e)}")