"""Unit tests for Docker sandbox helpers (no live Docker required)."""

from backend.services.docker_service import ExecutionResult, _parse_runner_output


def test_parse_runner_output_reads_last_json_line() -> None:
    """Ignore noise lines and decode the runner's JSON report."""

    raw = "starting...\n{\"mode\": \"run\", \"stdout\": \"hi\\n\", \"stderr\": \"\", \"exit_code\": 0, \"timed_out\": false, \"tests_passed\": 0, \"tests_total\": 0, \"test_results\": []}\n"
    result = _parse_runner_output(raw)

    assert isinstance(result, ExecutionResult)
    assert result.mode == "run"
    assert result.stdout == "hi\n"
    assert result.exit_code == 0


def test_parse_runner_output_handles_empty_logs() -> None:
    """Empty container logs become a clear error result."""

    result = _parse_runner_output("")
    assert result.mode == "error"
    assert "no output" in result.stderr.lower()
