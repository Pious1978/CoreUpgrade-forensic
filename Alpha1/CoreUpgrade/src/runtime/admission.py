"""
Untrusted Order Proposer (Formerly OrderAdmissionController)

Python proposes the trade. It cannot authorize execution.
It relies entirely on the Secure Execution Sidecar (Rust) for admission.
"""

import os
import socket
import json
from typing import Dict, Any

from src.gateway.protocol import OrderProposalBuilder
from src.security.kms.execution_gate_signer import ExecutionGateSigner
from src.runtime.state import RuntimeStateController
from src.security.audit import ImmutableAuditLedger

class UntrustedOrderProposer:

    _UDS_SOCKET_PATH = "/run/trading-engine/secure-gateway.sock"

    @classmethod
    def propose_order(
        cls,
        account: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        order_type: str,
        strategy_hash: str
    ) -> bool:
        """
        Builds the proposal, requests KMS signature, and submits to Sidecar.
        """
        # 1. Fetch current epoch/sequence tracking (Best effort, untrusted by sidecar)
        is_enabled, cert, state_epoch = RuntimeStateController.get_atomic_admission_token()
        if not is_enabled or not cert:
            raise RuntimeError("Proposer: Execution not enabled or certificate missing.")

        # In production, sequence generation would be backed by a local Redis/DB counter
        # to prevent proposing colliding sequences. The sidecar holds the ultimate truth.
        sequence = cls._get_next_sequence_number()

        # 2. Build the semantic payload
        order_payload = OrderProposalBuilder.build_payload(
            epoch=state_epoch,
            sequence=sequence,
            account=account,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            strategy_hash=strategy_hash
        )

        # 3. Two-Phase Audit Commit: Reserve intent to propose
        audit_res_id = ImmutableAuditLedger.reserve_event("ORDER_PROPOSAL", order_payload)

        try:
            # 4. Canonicalize and get SHA-384 digest for KMS
            _, digest = OrderProposalBuilder.serialize_and_digest(order_payload)

            # 5. Request AWS KMS ECDSA Signature
            signer = ExecutionGateSigner()
            signature_bytes = signer.sign(
                authorization_payload=order_payload, 
                certificate_serial=cert.serial
            )

            # 6. Construct UDS Envelope
            envelope = {
                "order_payload": order_payload,  # Semantic JSON object
                "authorization": {
                    "certificate_signature_hex": signature_bytes.hex(),
                    "leaf_public_key_der_hex": cert.leaf_public_key.hex()
                }
            }

            # 7. Submit to Rust Sidecar over UDS
            success = cls._submit_to_sidecar(envelope)
            
            # Phase 2 Audit: Commit Success
            ImmutableAuditLedger.commit_event(audit_res_id, "ACCEPTED_BY_SIDECAR")
            return success

        except Exception as e:
            # Phase 2 Audit: Commit Failure
            ImmutableAuditLedger.commit_event(audit_res_id, "REJECTED", {"reason": str(e)})
            raise

    @classmethod
    def _submit_to_sidecar(cls, envelope: Dict[str, Any]) -> bool:
        if not os.path.exists(cls._UDS_SOCKET_PATH):
            raise RuntimeError("Proposer: Secure Execution Gateway socket unavailable.")

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.1) # 100ms max allowed gateway latency
                client.connect(cls._UDS_SOCKET_PATH)
                client.sendall(json.dumps(envelope).encode("utf-8") + b"\n")

                response_data = client.recv(4096)
                if not response_data:
                    raise RuntimeError("Proposer: Sidecar closed connection unexpectedly.")

                response = json.loads(response_data.decode("utf-8"))

                if response.get("status") != "ACCEPTED":
                    reason = response.get("reason", "Unknown")
                    raise RuntimeError(f"Hardware Gateway Reject: {reason}")
                
                return True

        except socket.timeout:
            raise RuntimeError("Proposer: Secure Gateway latency timeout.")
        except Exception as e:
            raise RuntimeError(f"Proposer: Secure Gateway communication failed: {e}")

    @classmethod
    def _get_next_sequence_number(cls) -> int:
        """
        Mock sequence generator. In a real system, this pulls from Redis/DB.
        The sidecar strictly enforces monotonicity regardless of what is returned here.
        """
        import time
        return int(time.time_ns() / 1000)