"""Register the bootstrap teacher account against a live API.

Usage:
  python scripts/bootstrap_teacher.py https://etoz-api.onrender.com teacher you@example.com 'YourPassword123'
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def _post(url: str, payload: dict) -> tuple[int, dict | str]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        try:
            return error.code, json.loads(body)
        except json.JSONDecodeError:
            return error.code, body


def main() -> int:
    if len(sys.argv) != 5:
        print(
            "Usage: python scripts/bootstrap_teacher.py "
            "<api_base> <username> <email> <password>",
            file=sys.stderr,
        )
        return 1
    api_base, username, email, password = sys.argv[1:5]
    api_base = api_base.rstrip("/")
    status, body = _post(
        f"{api_base}/api/v1/auth/register",
        {"username": username, "email": email, "password": password},
    )
    print("register", status, body)
    if status not in (200, 201) and not (
        status == 400 and "already" in str(body).lower()
    ):
        return 1
    status, body = _post(
        f"{api_base}/api/v1/auth/login",
        {"username": username, "password": password},
    )
    print("login", status, body if status != 200 else {"access_token": "(ok)"})
    return 0 if status == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
