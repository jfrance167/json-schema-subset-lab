"""Nine fixed assertion mutants in fresh isolated copies; source remains untouched.

Usage: python -m scripts.mutation_check FRESH_DIRECTORY
Input: trusted local runtime/tests/frozen fixtures. Output: copies, raw logs and
summary.json. No downloads, deletion, generated commands, or arbitrary mutants.
Expect each targeted unittest to fail by assertion, not syntax/import exceptions.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MUTANTS = [('bool-as-integer', 'model.py', 'type(instance) is TYPES[name]', 'isinstance(instance, TYPES[name])', 'test_boolean_integer'), ('python-enum-equality', 'model.py', 'if type(left) is not type(right):', 'if False:', 'test_enum_kind'), ('required-null-missing', 'model.py', 'if name not in instance]', 'if name not in instance or instance[name] is None]', 'test_required_null'), ('properties-implies-required', 'model.py', 'if name in instance:\n                _evaluate', 'if name not in instance:\n                _issue(issues, ip, _pointer(dp, "properties"), "properties", "required-missing")\n            if name in instance:\n                _evaluate', 'test_properties_absent'), ('declared-failed-extra', 'model.py', 'instance.keys() - declared.keys()', 'instance.keys() - {name for name, child in declared.items() if child is not False}', 'test_declared_failed_child'), ('skip-child-support-scan', 'model.py', '_scan(children[name], _pointer(_pointer(pointer, "properties"), name), depth + 1, count, features)', 'pass', 'test_unsupported_absent_child'), ('short-circuit', 'model.py', '_issue(issues, ip, _pointer(dp, "type"), "type", "type-mismatch")', '_issue(issues, ip, _pointer(dp, "type"), "type", "type-mismatch")\n            return', 'test_no_short_circuit'), ('issue-cap', 'contract.py', 'issues=128', 'issues=256', 'test_issue_cap'), ('output-cap', 'contract.py', 'output_bytes=262144', 'output_bytes=1048576', 'test_output_cap')]

def hashes():
    return {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("schema_lab", "tests", "fixtures") for p in sorted((ROOT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    resolved = args.output.resolve()
    if any(resolved.is_relative_to(ROOT / folder) for folder in ("schema_lab", "tests", "fixtures")):
        raise ValueError("mutation output must be outside copied source directories")
    args.output.mkdir(parents=True, exist_ok=False)
    before = hashes()
    results = []
    for name, file, original, replacement, test in MUTANTS:
        copy = args.output / name
        copy.mkdir()
        for folder in ("schema_lab", "tests", "fixtures"):
            shutil.copytree(ROOT / folder, copy / folder, ignore=shutil.ignore_patterns("__pycache__"))
        target = copy / "schema_lab" / file
        text = target.read_text(encoding="utf-8")
        if text.count(original) != 1:
            raise RuntimeError("mutation anchor must occur exactly once")
        target.write_text(text.replace(original, replacement), encoding="utf-8", newline="\n")
        command = [sys.executable, "-m", "unittest", "-v", "tests.test_model.ModelTests." + test]
        result = subprocess.run(command, cwd=copy, capture_output=True, timeout=30)
        log = result.stdout + result.stderr
        (copy / "result.log").write_bytes(log)
        detected = result.returncode == 1 and b"AssertionError" in log and b"FAILED (failures=1)" in log and b"ERROR:" not in log
        results.append({"name": name, "target_test": test, "exit": result.returncode,
                        "assertion_detected": detected, "log_sha256": hashlib.sha256(log).hexdigest()})
    unchanged = before == hashes()
    summary = {"mutants": results, "originals_unchanged": unchanged, "original_hashes": before}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="ascii")
    print(json.dumps({"detected": sum(r["assertion_detected"] for r in results), "total": len(results), "unchanged": unchanged}))
    return 0 if unchanged and all(r["assertion_detected"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
