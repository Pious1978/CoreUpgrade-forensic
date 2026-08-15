"""
Linux Seccomp-BPF Syscall Restriction Loader

Enforces kernel-level syscall restrictions on the Python process.
"""

import ctypes
import ctypes.util

# Seccomp constants
PR_SET_NO_NEW_PRIVS = 38
PR_SET_SECCOMP = 22
SECCOMP_MODE_FILTER = 2

# Action values
SCMP_ACT_KILL_PROCESS = 0x80000000
SCMP_ACT_ALLOW = 0x7fff0000

class SeccompFilterManager:

    @classmethod
    def apply_strict_seccomp_policy(cls):
        """
        Applies PR_SET_NO_NEW_PRIVS and blocks dangerous syscalls using libseccomp.
        """
        libc_path = ctypes.util.find_library("c")
        libseccomp_path = ctypes.util.find_library("seccomp")

        if not libc_path or not libseccomp_path:
            raise RuntimeError("CRITICAL SECURITY ERROR: Unable to locate libc or libseccomp for kernel sandbox.")

        libc = ctypes.CDLL(libc_path, use_errno=True)
        libseccomp = ctypes.CDLL(libseccomp_path, use_errno=True)

        # 1. Set PR_SET_NO_NEW_PRIVS = 1
        res = libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
        if res != 0:
            errno = ctypes.get_errno()
            raise RuntimeError(f"CRITICAL SECURITY ERROR: prctl(PR_SET_NO_NEW_PRIVS) failed with errno {errno}")

        # 2. Initialize libseccomp context with DEFAULT ALLOW
        ctx = libseccomp.seccomp_init(SCMP_ACT_ALLOW)
        if not ctx:
            raise RuntimeError("CRITICAL SECURITY ERROR: Failed to initialize seccomp context.")

        # Syscall blacklist to prevent process spawning and memory injection
        syscall_blacklist = [
            "execve",
            "execveat",
            "ptrace",
            "process_vm_writev",
            "process_vm_readv",
            "kexec_load",
            "kexec_file_load",
            "init_module",
            "finit_module",
            "delete_module",
        ]

        try:
            for sys_name in syscall_blacklist:
                sys_nr = libseccomp.seccomp_syscall_resolve_name(sys_name.encode("utf-8"))
                if sys_nr >= 0:
                    # SCMP_ACT_KILL_PROCESS terminates process on violation
                    rule_res = libseccomp.seccomp_rule_add(ctx, SCMP_ACT_KILL_PROCESS, sys_nr, 0)
                    if rule_res < 0:
                        raise RuntimeError(f"Failed to add seccomp rule for {sys_name}")

            # 3. Load filter into Linux Kernel
            load_res = libseccomp.seccomp_load(ctx)
            if load_res < 0:
                raise RuntimeError("CRITICAL SECURITY ERROR: Failed to load seccomp filter into kernel.")

        finally:
            libseccomp.seccomp_release(ctx)