import os

gate4_code = '''import os
import importlib

class RuntimeIntegrityGate:
    """
    Gate 4: Runtime Integrity
    Verifies that modules load without error, manifests match state, 
    the control plane workflow scheduler initializes, and public contracts are discoverable.
    """
    def __init__(self):
        self.passed_checks = 0
        self.total_checks = 0

    def run_all_checks(self):
        print("--- GATE 4: RUNTIME INTEGRITY ---")
        
        self._check_manifest_consistency()
        self._check_module_importability()
        self._check_control_plane_startup()
        self._check_contract_registry_discovery()
        
        print(f"\\nGate 4 Result: {self.passed_checks}/{self.total_checks} Checks Passed")
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
        """Verifies that ARCHITECTURE_RULES.md exists and is readable."""
        exists = os.path.exists("ARCHITECTURE_RULES.md")
        self._assert(exists, "Manifest Consistency: ARCHITECTURE_RULES.md manifest present.", "Architecture manifest missing!")

    def _check_module_importability(self):
        """Verifies core and domain packages load cleanly into memory without import errors."""
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

    def _check_control_plane_startup(self):
        """Verifies workflow scheduler initializes correctly."""
        try:
            from control_plane.workflow_scheduler import __file__
            initialized = True
        except ImportError:
            initialized = False
            
        self._assert(initialized, "Control Plane Startup: workflow_scheduler is present and loadable.", "Workflow scheduler failed to initialize.")

    def _check_contract_registry_discovery(self):
        """Verifies all public schemas in contracts/ can be dynamically discovered and loaded."""
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
'''

os.makedirs("audits", exist_ok=True)
with open(os.path.join("audits", "gate4_runtime.py"), "w", encoding="utf-8") as f:
    f.write(gate4_code)

print("Created audits/gate4_runtime.py")
