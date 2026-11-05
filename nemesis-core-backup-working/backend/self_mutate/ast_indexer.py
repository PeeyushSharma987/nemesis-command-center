import ast
from pathlib import Path
from typing import Any, Dict, List


class ASTCodebaseIndexer:
    """Builds a live map of all mutable Ring-1 files, classes, and functions so N.E.M.E.S.I.S. can read its own source code."""

    @staticmethod
    def index_ring1_codebase(backend_root: Path) -> Dict[str, Any]:
        code_map: Dict[str, Any] = {}
        for py_file in sorted(backend_root.rglob("*.py")):
            if "__pycache__" in str(py_file):
                continue
            rel_path = str(py_file.relative_to(backend_root)).replace("\\", "/")
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source)
                classes: List[str] = []
                functions: List[str] = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        classes.append(node.name)
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        functions.append(node.name)
                code_map[rel_path] = {
                    "classes": classes,
                    "functions": functions,
                    "lines": len(source.splitlines()),
                }
            except Exception as exc:
                code_map[rel_path] = {"error": str(exc)}
        return {
            "commander": "N.E.M.E.S.I.S. Self-Indexer",
            "mutable_ring1_files": len(code_map),
            "ast_map": code_map,
        }
