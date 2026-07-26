# Isolated Python runner for student code.
# Build from the project root:
#   docker build -t etoz-python-runner -f docker/Dockerfile docker
#
# Why a dedicated image?
#   Student programs must never run on the host process. This image provides a
#   minimal Python environment; the backend starts a throwaway container per run
#   with no network, low CPU/memory, and a hard timeout.

FROM python:3.12-slim

# Non-root user limits damage if student code is malicious.
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin runner

COPY runner.py /opt/etoz/runner.py

WORKDIR /code
USER runner

ENTRYPOINT ["python", "-u", "/opt/etoz/runner.py"]
