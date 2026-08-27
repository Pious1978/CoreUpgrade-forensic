import os

manifests = {
    'replay': {
        'api': {'ReplayEngine': 'replay_engine.ReplayEngine'},
        'forbidden': []
    },
    'event_store': {
        'api': {
            'InMemoryEventStore': 'store.InMemoryEventStore',
            'EventPublisherProtocol': 'publisher.EventPublisherProtocol'
        },
        'forbidden': []
    },
    'audits': {
        'api': {'InstitutionalStaticArchitectureVerifier': 'run_gate1.InstitutionalStaticArchitectureVerifier'},
        'forbidden': []
    }
}

for domain, cfg in manifests.items():
    with open(os.path.join(domain, 'manifest.py'), 'w', encoding='utf-8') as f:
        f.write(f'DOMAIN_NAME = "{domain}"\n')
        f.write('VERSION = "1.0"\n')
        f.write(f'PUBLIC_API = {cfg["api"]}\n')
        f.write(f'FORBIDDEN_IMPORTS = {cfg["forbidden"]}\n')

print('Updated manifests for replay, event_store, and audits.')
