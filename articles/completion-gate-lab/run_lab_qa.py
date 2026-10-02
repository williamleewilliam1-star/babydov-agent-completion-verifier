"""Reproduce the offline tests and four deliberately broken local variants."""
import ast
import hashlib
import io
import json
from pathlib import Path
import platform
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / "completion_gate_lab.py").read_text(encoding="utf-8")
ALLOWED_IMPORTS = {"__future__", "hashlib", "itertools", "json", "math", "unittest", "dataclasses", "enum"}
MUTATIONS = {
    "ignore_http_status": ("if observation.status != 200:", "if False:"),
    "accept_ready_or_revision": (
        'matched = payload["ready"] is True and payload["revision"] == contract.revision',
        'matched = payload["ready"] is True or payload["revision"] == contract.revision'),
    "ignore_evidence_age": (
        "and now - observation.observed_at <= contract.max_age_s", "and True"),
    "ignore_release_identity": (
        'matched = payload["ready"] is True and payload["revision"] == contract.revision',
        'matched = payload["ready"] is True'),
}


def run_suite(source: str, name: str) -> dict:
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        with patch("socket.socket", side_effect=RuntimeError("Network forbidden in this lab")), \
             patch("socket.create_connection", side_effect=RuntimeError("Network forbidden in this lab")):
            exec(compile(source, name + ".py", "exec"), module.__dict__)
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(module.CompletionGateTests)
            stream = io.StringIO()
            result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
            return {"tests_run": result.testsRun, "failures": len(result.failures),
                    "errors": len(result.errors), "passed": result.wasSuccessful()}
    finally:
        sys.modules.pop(name, None)


def main() -> None:
    tree = ast.parse(SOURCE)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(item.name.split(".")[0] for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module.split(".")[0])
    if imports - ALLOWED_IMPORTS:
        raise RuntimeError("Unexpected imports: " + repr(imports - ALLOWED_IMPORTS))
    compile(SOURCE, "completion_gate_lab.py", "exec")
    baseline = run_suite(SOURCE, "lab_baseline")
    mutations = {}
    for name, (old, new) in MUTATIONS.items():
        if SOURCE.count(old) != 1:
            raise RuntimeError("Mutation anchor is not unique: " + name)
        result = run_suite(SOURCE.replace(old, new), "lab_" + name)
        result["caught_by_assertions"] = result["failures"] > 0 and result["errors"] == 0
        mutations[name] = result
    passed = baseline["passed"] and all(item["caught_by_assertions"] for item in mutations.values())
    report = {
        "scope": "new standalone teaching lab only; not production verifier or payment validation",
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "source_sha256": hashlib.sha256(SOURCE.encode()).hexdigest(),
        "static_parse_and_compile": "passed",
        "source_import_allowlist": sorted(imports),
        "network_socket_creation": "blocked during all test suites",
        "baseline": baseline,
        "matrix_distinct_cases_within_one_test": 64,
        "matrix_dimensions": ["transport", "resource", "freshness", "http_status", "ready", "revision"],
        "mutations": mutations,
        "passed": passed,
    }
    (ROOT / "qa-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
