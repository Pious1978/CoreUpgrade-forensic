def _export_dependency_artifact(self, current_edges: Dict[str, List[str]], update_baseline: bool):
        from core.artifact_envelope import AuditArtifactEnvelope
        from core.artifact_registry import ArtifactRegistry
        
        registry = ArtifactRegistry()
        envelope = AuditArtifactEnvelope.create(
            artifact_type="dependency_dag_snapshot",
            generated_by="DependencyIntegrityGate",
            payload={"edges": current_edges}
        )
        
        # Register operational run artifact
        registry.register_artifact("gate3", envelope)

        if not os.path.exists(self.baseline_path) or update_baseline:
            with open(self.baseline_path, "w", encoding="utf-8") as f:
                json.dump(envelope.to_dict(), f, indent=4)
            print(f"[INFO] Dependency baseline explicitly locked/updated at {self.baseline_path}")

        with open(self.baseline_path, "r", encoding="utf-8") as f:
            baseline_data = json.load(f)
        
        baseline_edges = baseline_data.get("payload", baseline_data).get("edges", baseline_data)

        drift_messages = []
        all_domains = set(list(current_edges.keys()) + list(baseline_edges.keys()))
        for domain in all_domains:
            curr_set = set(current_edges.get(domain, []))
            base_set = set(baseline_edges.get(domain, []))
            
            added = curr_set - base_set
            removed = base_set - curr_set
            
            if added:
                drift_messages.append(f"  - Domain '{domain}' added edges: {list(added)}")
            if removed:
                drift_messages.append(f"  - Domain '{domain}' removed edges: {list(removed)}")

        is_stable = len(drift_messages) == 0
        self._assert(is_stable, 
                     "Dependency Graph Stable: Zero structural edge drift detected against baseline.", 
                     f"Architectural Dependency Drift Detected:\n" + "\n".join(drift_messages))
