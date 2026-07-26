"""In-container entrypoint that safely executes student Python code.

This script runs *inside* the Docker sandbox — never on the host. It either:
- runs the student's program once (free Run), or
- grades it against stdin/stdout test cases (Submit).

Student stdout/stderr are captured per attempt. The container's own stdout is
only the final JSON report consumed by ``docker_service``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

CODE_DIR = Path("/code")
SOLUTION_PATH = CODE_DIR / "solution.py"
TESTS_PATH = CODE_DIR / "tests.json"

# Per-test subprocess budget (seconds). The host also enforces a hard container timeout.
DEFAULT_TEST_TIMEOUT = 3


def _normalize_output(text: str) -> str:
    """Compare outputs without trailing whitespace noise."""

    return text.replace("\r\n", "\n").rstrip()


def _run_solution(stdin_data: str, timeout: float) -> dict[str, object]:
    """Execute the student file once and return captured streams."""

    try:
        completed = subprocess.run(
            [sys.executable, str(SOLUTION_PATH)],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(CODE_DIR),
            env={
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", "/home/runner"),
                "PYTHONPATH": "",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "Time limit exceeded while running your code.",
            "exit_code": 124,
            "timed_out": True,
        }
    except OSError as error:
        return {
            "stdout": "",
            "stderr": f"Failed to start Python: {error}",
            "exit_code": 1,
            "timed_out": False,
        }

    return {
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "exit_code": completed.returncode,
        "timed_out": False,
    }


def _load_tests() -> list[dict[str, object]]:
    """Load optional test cases written by the host service."""

    if not TESTS_PATH.is_file():
        return []
    raw = TESTS_PATH.read_text(encoding="utf-8")
    if not raw.strip():
        return []
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("tests.json must be a JSON list")
    return payload


def _grade(tests: list[dict[str, object]], timeout: float) -> dict[str, object]:
    """Run every stdin/stdout test case and summarize results."""

    results: list[dict[str, object]] = []
    passed = 0

    for index, case in enumerate(tests):
        stdin_data = str(case.get("stdin", ""))
        expected = _normalize_output(str(case.get("expected_stdout", "")))
        run = _run_solution(stdin_data, timeout=timeout)
        actual = _normalize_output(str(run["stdout"]))
        case_passed = (
            not run["timed_out"]
            and run["exit_code"] == 0
            and actual == expected
            and not str(run["stderr"]).strip()
        )
        if case_passed:
            passed += 1
        results.append(
            {
                "index": index,
                "passed": case_passed,
                "stdin": stdin_data,
                "expected_stdout": expected,
                "actual_stdout": actual,
                "stderr": run["stderr"],
                "timed_out": run["timed_out"],
                "exit_code": run["exit_code"],
            }
        )

    return {
        "mode": "grade",
        "stdout": "",
        "stderr": "",
        "exit_code": 0 if passed == len(tests) else 1,
        "timed_out": any(item["timed_out"] for item in results),
        "tests_passed": passed,
        "tests_total": len(tests),
        "test_results": results,
    }


def main() -> int:
    """Entry point used by the Docker image."""

    try:
        if not SOLUTION_PATH.is_file():
            report = {
                "mode": "error",
                "stdout": "",
                "stderr": "Missing /code/solution.py",
                "exit_code": 2,
                "timed_out": False,
                "tests_passed": 0,
                "tests_total": 0,
                "test_results": [],
            }
            print(json.dumps(report))
            return 2

        mode = os.environ.get("ETOZ_MODE", "run").strip().lower()
        timeout = float(os.environ.get("ETOZ_TEST_TIMEOUT", DEFAULT_TEST_TIMEOUT))

        if mode == "grade":
            tests = _load_tests()
            if not tests:
                report = {
                    "mode": "error",
                    "stdout": "",
                    "stderr": "No test cases provided for grading.",
                    "exit_code": 2,
                    "timed_out": False,
                    "tests_passed": 0,
                    "tests_total": 0,
                    "test_results": [],
                }
            else:
                report = _grade(tests, timeout=timeout)
        else:
            run = _run_solution("", timeout=timeout)
            report = {
                "mode": "run",
                "stdout": run["stdout"],
                "stderr": run["stderr"],
                "exit_code": run["exit_code"],
                "timed_out": run["timed_out"],
                "tests_passed": 0,
                "tests_total": 0,
                "test_results": [],
            }

        print(json.dumps(report))
        return int(report.get("exit_code", 0))
    except Exception:  # noqa: BLE001 — last-resort report for the host
        report = {
            "mode": "error",
            "stdout": "",
            "stderr": traceback.format_exc(),
            "exit_code": 1,
            "timed_out": False,
            "tests_passed": 0,
            "tests_total": 0,
            "test_results": [],
        }
        print(json.dumps(report))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
