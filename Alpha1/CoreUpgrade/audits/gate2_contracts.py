def _check_contract_fingerprints(self):
        """Computes structural schema hashes and registers them via ArtifactRegistry."""
        from core.artifact_envelope import AuditArtifactEnvelope
        from core.artifact_registry import ArtifactRegistry
        
        current_fingerprints = {}
        contracts_dir = "contracts"
        
        if os.path.exists(contracts_dir):
            for file in sorted(os.listdir(contracts_dir)):
                if not file.endswith(".py") or file == "__init__.py": continue
                filepath = os.path.join(contracts_dir, file)
                
                with open(filepath, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                    
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        fields = []
                        for body_item in node.body:
                            if isinstance(body_item, ast.AnnAssign) and isinstance(body_item.target, ast.Name):
                                field_name = body_item.target.id
                                field_type = ast.unparse(body_item.annotation) if hasattr(ast, 'unparse') else str(body_item.annotation)
                                fields.append(f"{field_name}:{field_type}")
                        
                        schema_signature = f"{node.name}|" + "|".join(sorted(fields))
                        h = hashlib.sha256(schema_signature.encode()).hexdigest()[:12]
                        current_fingerprints[node.name] = h

        # Register artifact via centralized registry
        registry = ArtifactRegistry()
        envelope = AuditArtifactEnvelope.create(
            artifact_type="contract_fingerprints",
            generated_by="ContractIntegrityGate",
            payload={"fingerprints": current_fingerprints}
        )
        registry.register_artifact("gate2", envelope)

        baseline_path = os.path.join("event_store", "fingerprints", "contract_fingerprints_baseline.json")
        if not os.path.exists(baseline_path):
            with open(baseline_path, "w", encoding="utf-8") as f:
                json.dump(envelope.to_dict(), f, indent=4)
            print(f"[INFO] Initialized contract baseline at {baseline_path}")

        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline_data = json.load(f)
        
        baseline_fingerprints = baseline_data.get("payload", baseline_data).get("fingerprints", baseline_data)

        mismatches = []
        for name, current_hash in current_fingerprints.items():
            if name not in baseline_fingerprints:
                mismatches.append(f"New un-baselined contract: {name} ({current_hash})")
            elif baseline_fingerprints[name] != current_hash:
                mismatches.append(f"Breaking API Change! Contract '{name}' changed ({baseline_fingerprints[name]} -> {current_hash}).")

        self._assert(len(mismatches) == 0, 
                     f"Contract Fingerprints Stable: All public schemas match baseline hashes.", 
                     f"Breaking changes detected:\n" + "\n".join(mismatches))
