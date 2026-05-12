from __future__ import annotations

import subprocess
import sys
from pathlib import Path


TESTS: list[tuple[str, str]] = [
    ("Schema Contract Tests", "test_contracts.py"),
    ("Plan Scoring Tests", "test_plan_scoring.py"),
    ("Error Handling Tests", "test_error_handling.py"),
    ("Schema + Mongo Loading Test", "test_schema_loading.py"),
    ("Connectivity Tests", "test_connectivity.py"),
    ("Integration Tests", "test_integration.py"),
    ("Message Queue Flow Tests", "test_message_flow.py"),
    ("API Endpoint Tests", "test_api.py"),
]


def run_one(test_name: str, test_file: Path) -> bool:
    print("\n" + "-" * 54)
    print(f"Running: {test_name}")
    print("-" * 54 + "\n")

    proc = subprocess.run([sys.executable, str(test_file)], check=False)
    return proc.returncode == 0


def main() -> int:
    tests_dir = Path(__file__).resolve().parent

    print("\n" + "=" * 56)
    print("Prospecting Service - Functional Test Suite")
    print("=" * 56)

    passed = 0
    failed = 0
    results: list[str] = []

    for name, file_name in TESTS:
        ok = run_one(name, tests_dir / file_name)
        if ok:
            passed += 1
            results.append(f"PASS: {name}")
        else:
            failed += 1
            results.append(f"FAIL: {name}")

    print("\n" + "=" * 56)
    print("TEST SUMMARY")
    print("=" * 56 + "\n")
    for line in results:
        print(line)
    print("\n" + "-" * 56)
    print(f"Total Passed: {passed}")
    print(f"Total Failed: {failed}")
    print("-" * 56)

    if failed == 0:
        print("\nAll tests passed.\n")
        return 0

    print("\nSome tests failed.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
