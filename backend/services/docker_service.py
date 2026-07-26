"""Run student Python code inside short-lived Docker containers.

Security model:
- never ``exec`` student code on the host
- disable container networking
- enforce CPU, memory, and wall-clock limits
- drop Linux capabilities and run as a non-root image user
- always destroy the container afterward
"""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)


class DockerExecutionError(RuntimeError):
    """Raised when the sandbox cannot start or finish a run."""


@dataclass
class ExecutionResult:
    """Normalized report produced by ``docker/runner.py``."""

    mode: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
    tests_passed: int = 0
    tests_total: int = 0
    test_results: list[dict[str, Any]] = field(default_factory=list)


def _nano_cpus(cpu_limit: float) -> int:
    """Convert a fractional CPU quota to Docker's nano-CPU units."""

    return max(1, int(cpu_limit * 1_000_000_000))


def _get_docker_client():
    """Create a Docker client or raise a clear setup error."""

    try:
        import docker
        from docker.errors import DockerException
    except ImportError as error:
        raise DockerExecutionError(
            "The Python package 'docker' is not installed. "
            "Run: pip install -r requirements.txt"
        ) from error

    try:
        client = docker.from_env()
        client.ping()
        return client
    except DockerException as error:
        raise DockerExecutionError(
            "Cannot connect to Docker. Install Docker Desktop, start it, "
            "then verify with `docker version`."
        ) from error


def _write_workspace(code: str, test_cases: list[dict[str, Any]] | None) -> Path:
    """Persist student files into a host temp directory for bind-mounting."""

    workspace = Path(tempfile.mkdtemp(prefix="etoz-code-"))
    (workspace / "solution.py").write_text(code, encoding="utf-8")
    if test_cases is not None:
        (workspace / "tests.json").write_text(
            json.dumps(test_cases),
            encoding="utf-8",
        )
    return workspace


def _parse_runner_output(raw_logs: str) -> ExecutionResult:
    """Decode the JSON report printed by the in-container runner."""

    text = raw_logs.strip()
    if not text:
        return ExecutionResult(
            mode="error",
            stderr="Runner produced no output.",
            exit_code=1,
        )

    # Prefer the last JSON object in case Docker attached unrelated lines.
    for candidate in reversed(text.splitlines()):
        candidate = candidate.strip()
        if not candidate.startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        return ExecutionResult(
            mode=str(payload.get("mode", "error")),
            stdout=str(payload.get("stdout", "")),
            stderr=str(payload.get("stderr", "")),
            exit_code=int(payload.get("exit_code", 1)),
            timed_out=bool(payload.get("timed_out", False)),
            tests_passed=int(payload.get("tests_passed", 0)),
            tests_total=int(payload.get("tests_total", 0)),
            test_results=list(payload.get("test_results") or []),
        )

    return ExecutionResult(
        mode="error",
        stderr=f"Could not parse runner output:\n{text[:2000]}",
        exit_code=1,
    )


def _run_in_container(
    *,
    code: str,
    mode: str,
    test_cases: list[dict[str, Any]] | None = None,
) -> ExecutionResult:
    """Create, wait for, and destroy one sandbox container."""

    client = _get_docker_client()
    workspace = _write_workspace(code, test_cases)
    container = None
    timeout = settings.docker_timeout_seconds

    try:
        from docker.errors import ImageNotFound

        try:
            container = client.containers.run(
                image=settings.docker_image,
                detach=True,
                network_disabled=True,
                mem_limit=settings.docker_memory_limit,
                nano_cpus=_nano_cpus(settings.docker_cpu_limit),
                environment={
                    "ETOZ_MODE": mode,
                    "ETOZ_TEST_TIMEOUT": str(max(1, timeout - 1)),
                },
                volumes={
                    str(workspace.resolve()): {
                        "bind": "/code",
                        "mode": "ro",
                    }
                },
                working_dir="/code",
                read_only=True,
                tmpfs={"/tmp": "size=16m,mode=1777"},
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                pids_limit=64,
                stdout=True,
                stderr=True,
            )
        except ImageNotFound as error:
            raise DockerExecutionError(
                f"Docker image '{settings.docker_image}' was not found. "
                "Build it with: docker build -t etoz-python-runner "
                "-f docker/Dockerfile docker"
            ) from error

        timed_out = False
        try:
            wait_result = container.wait(timeout=timeout)
            status_code = int(wait_result.get("StatusCode", 1))
        except Exception:  # noqa: BLE001 — SDK raises variously on timeout
            timed_out = True
            status_code = 124
            try:
                container.kill()
            except Exception:  # noqa: BLE001
                logger.exception("Failed to kill timed-out container")

        raw_logs = container.logs(stdout=True, stderr=True).decode(
            "utf-8",
            errors="replace",
        )
        result = _parse_runner_output(raw_logs)
        if timed_out:
            result.timed_out = True
            result.exit_code = 124
            if not result.stderr:
                result.stderr = (
                    f"Execution timed out after {timeout} seconds."
                )
        elif result.mode == "error" and not result.stderr and status_code != 0:
            result.stderr = f"Container exited with status {status_code}."
            result.exit_code = status_code
        return result
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to remove container %s", container.id)
                try:
                    from docker.errors import NotFound

                    # Best-effort second pass if the first remove raced.
                    client.containers.get(container.id).remove(force=True)
                except NotFound:
                    pass
                except Exception:  # noqa: BLE001
                    logger.exception("Second remove attempt also failed")

        # Clean host temp files after the bind mount is unused.
        try:
            for path in workspace.glob("*"):
                path.unlink(missing_ok=True)
            workspace.rmdir()
        except OSError:
            logger.warning("Could not clean workspace %s", workspace)


def run_python_code(code: str) -> ExecutionResult:
    """Execute student code once and return stdout/stderr."""

    return _run_in_container(code=code, mode="run")


def grade_python_code(
    code: str,
    test_cases: list[dict[str, Any]],
) -> ExecutionResult:
    """Execute student code against hidden stdin/stdout test cases."""

    if not test_cases:
        raise DockerExecutionError("Coding questions require at least one test case")
    return _run_in_container(code=code, mode="grade", test_cases=test_cases)
