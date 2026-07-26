# Docker Python Runner

Student code runs only inside this sandbox — never on the host.

## Prerequisites

Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
and make sure it is running (`docker version` should work in PowerShell).

## Build the image

From the project root:

```powershell
docker build -t etoz-python-runner -f docker/Dockerfile docker
```

## How it works

1. Backend writes `solution.py` (+ optional `tests.json`) to a temp folder.
2. `docker_service` starts a container from `etoz-python-runner`.
3. Container has **no network**, CPU/memory caps, and a timeout.
4. `runner.py` executes the code, prints one JSON report, then exits.
5. Backend collects logs and **force-removes** the container.

## Security defaults

| Control | Value |
|---------|-------|
| Network | disabled |
| Memory | `DOCKER_MEMORY_LIMIT` (default 128m) |
| CPU | `DOCKER_CPU_LIMIT` (default 0.5) |
| Timeout | `DOCKER_TIMEOUT_SECONDS` (default 10) |
| User | non-root `runner` (uid 1000) |
| Caps | all dropped |
| Filesystem | student files mounted read-only |
