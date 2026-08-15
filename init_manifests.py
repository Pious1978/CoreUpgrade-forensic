import os

manifests = {
    "research": {
        "api": ["generate_candidates", "backtest"],
        "forbidden": ["execution"],
    },
    "portfolio": {
        "api": ["optimize", "rebalance"],
        "forbidden": ["execution"],
    },
    "risk": {
        "api": ["evaluate"],
        "forbidden": [],
    },
    "governance": {
        "api": ["evaluate", "approve"],
        "forbidden": [],
    },
    "execution": {
        "api": ["plan", "execute"],
        "forbidden": ["research"],
    },
    "control_plane": {
        "api": ["run_cycle"],
        "forbidden": [],
    },
    "contracts": {
        "api": ["ContractBase"],
        "forbidden": [],
    },
    "infrastructure": {
        "api": ["fetch_market_data"],
        "forbidden": [],
    },
    "event_store": {
        "api": ["append", "get_events"],
        "forbidden": [],
    },
    "replay": {
        "api": ["replay_run"],
        "forbidden": [],
    },
    "audits": {
        "api": ["verify_all"],
        "forbidden": [],
    },
}

for domain, cfg in manifests.items():
    os.makedirs(domain, exist_ok=True)
    manifest_path = os.path.join(domain, "manifest.py")

    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(f'DOMAIN_NAME = "{domain}"\n')
        f.write('VERSION = "1.0"\n')
        f.write(f'PUBLIC_API = {repr(cfg["api"])}\n')
        f.write(f'FORBIDDEN_IMPORTS = {repr(cfg["forbidden"])}\n')

print("Architecture manifests initialized with strict boundary configurations.")
