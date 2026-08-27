import os
import importlib
from control_plane.workflow_scheduler import WorkflowScheduler

class RuntimeIntegrityGate:
    """
    Gate 4: Runtime Integrity
    Verifies manifest presence, module importability, public contract discovery, 
    and actual orchestrator operability (instantiation + readiness).
    """
    def __init__(self):
        self.passed_checks = 0
        self.total_checks = 0

    def run_all_checks(self):
        print("--- GATE 4: RUNTIME INTEGRITY ---")
        
        self._check_manifest_consistency()
        self._check_module_importability()
        self._check_workflow_scheduler_operability()
        self._check_contract_registry_discovery()
        
        print(f"\nGate 4 Result: {self.passed_checks}/{self.total_checks} Checks Passed")
        if self.passed_checks == self.total_checks:
            print("Verdict: PASS - Runtime environment, modules, and orchestrators are fully operational.")
        else:
            print("Verdict: FAIL - Runtime initialization errors detected.")

    def _assert(self, condition: bool, success_msg: str, fail_msg: str):
        self.total_checks += 1
        if condition:
            print(f"[PASS] {success_msg}")
            self.passed_checks += 1
        else:
            print(f"[FAIL] {fail_msg}")

    def _check_manifest_consistency(self):
        exists = os.path.exists("ARCHITECTURE_RULES.md")
        self._assert(exists, "Manifest Consistency: ARCHITECTURE_RULES.md manifest present.", "Architecture manifest missing!")

    def _check_module_importability(self):
        modules_to_test = ["core", "research", "portfolio", "execution", "governance", "control_plane"]
        failed_modules = []
        for mod in modules_to_test:
            try:
                importlib.import_module(mod)
            except Exception as e:
                failed_modules.append(f"{mod}: {e}")
        self._assert(len(failed_modules) == 0, 
                     "Module Importability: All foundational domain packages imported successfully.", 
                     f"Failed module imports: {failed_modules}")

    def _check_workflow_scheduler_operability(self):
        """Verifies actual workflow scheduler instantiation and initialization logic."""
        try:
            scheduler = WorkflowScheduler()
            scheduler.initialize()
            is_operable = scheduler.is_ready and len(scheduler.registered_workflows) > 0
        except Exception as e:
            is_operable = False
            
        self._assert(is_operable, "Workflow Scheduler Operability: Initialized successfully and marked ready.", "Scheduler failed operational initialization check.")

    def _check_contract_registry_discovery(self):
        contracts_dir = "contracts"
        discovered = 0
        if os.path.exists(contracts_dir):
            for file in os.listdir(contracts_dir):
                if file.endswith(".py") and file != "__init__.py":
                    mod_name = f"contracts.{file[:-3]}"
                    try:
                        importlib.import_module(mod_name)
                        discovered += 1
                    except Exception:
                        pass
        self._assert(discovered >= 4, f"Contract Registry Discovery: Successfully loaded {discovered} public schemas.", "Failed to discover public contracts.")

if __name__ == "__main__":
    gate = RuntimeIntegrityGate()
    gate.run_all_checks()
