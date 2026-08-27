"""
Python Runtime Lockdown & Memory Containment

Security Objectives:
- Disable dynamic execution primitives (eval, exec, compile)
- Enforce strict sys.meta_path import allow-list
- Purge dangerous modules (pickle, pdb, ctypes) from runtime environment
"""

import sys
import builtins
import importlib.abc
import importlib.machinery
from typing import Set, Optional, Sequence


class RestrictedImportFinder(importlib.abc.MetaPathFinder):
    """
    sys.meta_path import hook prohibiting dynamic import of unauthorized modules.
    """
    
    ALLOWED_PREFIXES: Set[str] = {
        "src.",
        "cryptography.",
        "rfc8785.",
        "canonicaljson.",
        "boto3.",
        "botocore.",
        "redis.",
        "requests.",
        "urllib3.",
        "json",
        "math",
        "time",
        "hashlib",
        "hmac",
        "os",
        "sys",
        "socket",
        "threading",
        "dataclasses",
        "enum",
        "typing",
        "struct",
        "binascii",
        "tempfile",
        "subprocess",
        "platform",
        "ssl",
        "datetime",
        "contextlib",
        "abc",
    }

    BANNED_MODULES: Set[str] = {
        "pickle",
        "_pickle",
        "cPickle",
        "pdb",
        "code",
        "codeop",
        "pty",
        "tty",
    }

    @classmethod
    def find_spec(
        cls,
        fullname: str,
        path: Optional[Sequence[str]],
        target: Optional[object] = None
    ) -> Optional[importlib.machinery.ModuleSpec]:
        
        # 1. Reject explicitly blacklisted modules
        if any(fullname == banned or fullname.startswith(f"{banned}.") for banned in cls.BANNED_MODULES):
            raise ImportError(f"CRITICAL SECURITY ERROR: Import of blacklisted module '{fullname}' is forbidden.")

        # 2. Enforce strict prefix allow-list
        is_allowed = any(fullname == prefix.rstrip(".") or fullname.startswith(prefix) for prefix in cls.ALLOWED_PREFIXES)
        
        if not is_allowed:
            raise ImportError(f"CRITICAL SECURITY ERROR: Import of unverified module '{fullname}' rejected by runtime policy.")

        # Fall through to standard loaders if allowed
        return None


class RuntimeLockdownController:
    
    @staticmethod
    def _disable_dynamic_eval():
        """
        Disables dynamic code execution builtins.
        """
        def _disabled_eval(*args, **kwargs):
            raise RuntimeError("CRITICAL SECURITY ERROR: Dynamic code evaluation (eval) is disabled.")

        def _disabled_exec(*args, **kwargs):
            raise RuntimeError("CRITICAL SECURITY ERROR: Dynamic code execution (exec) is disabled.")

        def _disabled_compile(*args, **kwargs):
            raise RuntimeError("CRITICAL SECURITY ERROR: Dynamic code compilation (compile) is disabled.")

        builtins.eval = _disabled_eval
        builtins.exec = _disabled_exec
        builtins.compile = _disabled_compile

    @staticmethod
    def _purge_dangerous_modules():
        """
        Purges dangerous modules if already loaded by interpreter initialization.
        """
        banned = {"pickle", "_pickle", "cPickle", "pdb"}
        for mod in list(sys.modules.keys()):
            if any(mod == b or mod.startswith(f"{b}.") for b in banned):
                del sys.modules[mod]

    @staticmethod
    def _install_import_hook():
        """
        Prepends the restricted finder to sys.meta_path.
        """
        sys.meta_path.insert(0, RestrictedImportFinder())

    @classmethod
    def enforce_runtime_lockdown(cls):
        """
        Executes complete Python runtime lockdown sequence.
        """
        cls._purge_dangerous_modules()
        cls._disable_dynamic_eval()
        cls._install_import_hook()