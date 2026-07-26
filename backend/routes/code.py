"""Routes for free-running student code in the Docker sandbox."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.submission import CodeRunRequest, CodeRunResponse
from backend.services.docker_service import DockerExecutionError, run_python_code

router = APIRouter(prefix="/code", tags=["Code"])


@router.post("/run", response_model=CodeRunResponse)
def run_code(
    payload: CodeRunRequest,
    _: User = Depends(get_current_user),
) -> CodeRunResponse:
    """Execute Python code once and return captured output (not graded)."""

    try:
        result = run_python_code(payload.code)
    except DockerExecutionError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return CodeRunResponse(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        timed_out=result.timed_out,
        detail=(
            "Execution timed out."
            if result.timed_out
            else None
        ),
    )
