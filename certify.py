"""
Certification Root Entrypoint

Initializes the certification engine, loads registered gates from the registry,
runs the audit pipeline, and exits with a status code matching the final verdict.
"""

from control_plane.certification_engine import CertificationEngine
from control_plane.gate_registry import load_registered_gates


def main():
    engine = CertificationEngine()

    for gate in load_registered_gates():
        engine.register_gate(gate)

    report = engine.run_certification()

    if report["payload"]["master_verdict"] != "CERTIFIED":
        exit(1)

    exit(0)


if __name__ == "__main__":
    main()
