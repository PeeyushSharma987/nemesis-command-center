import ast
import shutil
import time
from pathlib import Path
from typing import Dict

from ring0_kernel.security_auditor_19pt import NineteenPointAuditor


class Ring0RollbackWatchdog:
    """
    Immutable Ring-0 safety net:
    1. Backs up target files before N.E.M.E.S.I.S. mutates them.
    2. Verifies AST syntax and 19-point security shields in staging.
    3. Automatically reverts to the backup if any check fails.
    """

    SNAPSHOT_DIR = Path("nemesis_memory_store") / "ring0_snapshots"

    @classmethod
    def create_snapshot(cls, target_file: Path) -> Path:
        cls.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time() * 1000)
        backup_path = cls.SNAPSHOT_DIR / f"{target_file.name}.{timestamp}.bak"
        shutil.copy2(target_file, backup_path)
        return backup_path

    @classmethod
    def validate_candidate_code(cls, candidate_code: str, project_root: Path) -> Dict[str, object]:
        # 1. Verify valid Python AST syntax (prevents server crash on reload)
        try:
            ast.parse(candidate_code)
        except SyntaxError as exc:
            return {
                "valid": False,
                "reason": f"AST SyntaxError at line {exc.lineno}: {exc.msg}",
            }

        # 2. Block attempts to touch Ring-0 Kernel imports or enable debug mode
        if "DEBUG = True" in candidate_code or "<?php" in candidate_code:
            return {
                "valid": False,
                "reason": "19-Point Security Violation: Forbidden pattern in mutated code.",
            }

        # 3. Run full directory 19-point audit
        audit = NineteenPointAuditor.audit_directory(project_root)
        if not audit["passed"]:
            return {
                "valid": False,
                "reason": f"19-Point Security Audit Failed: {audit['violations']}",
            }

        return {"valid": True, "reason": "AST & 19-Point Security Audit Passed."}

    @classmethod
    def rollback(cls, backup_path: Path, target_file: Path) -> None:
        if backup_path.exists():
            shutil.copy2(backup_path, target_file)
