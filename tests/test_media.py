"""Teacher media upload library."""

from pathlib import Path

from backend.services.media_service import latex_snippet_for_url, save_upload


def test_save_upload_writes_under_media(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.services.media_service.settings.media_root",
        str(tmp_path / "media"),
    )
    monkeypatch.setattr(
        "backend.services.media_service.settings.public_api_url",
        "http://test.local:8000",
    )
    saved = save_upload(
        filename="diagram.png",
        content=b"\x89PNG\r\n",
        content_type="image/png",
    )
    assert saved["kind"] == "image"
    assert saved["url"].startswith("http://test.local:8000/media/")
    assert Path(tmp_path / "media" / saved["stored_name"]).is_file()
    from backend.services.media_service import latex_snippet_for_media

    snippet = latex_snippet_for_media(url=saved["url"], kind="image")
    assert snippet.startswith("\\includegraphics{")


def test_url_snippets_use_standard_latex() -> None:
    youtube = latex_snippet_for_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert youtube.startswith("\\href{")
    image = latex_snippet_for_url("https://cdn.example.com/a.png")
    assert image.startswith("\\includegraphics{")
    file_link = latex_snippet_for_url(
        "http://127.0.0.1:8000/media/notes.pdf",
        label="Notes",
    )
    assert file_link == "\\href{http://127.0.0.1:8000/media/notes.pdf}{Notes}"


def test_admin_can_upload_media(client, database_session) -> None:
    from tests.helpers import register_and_login_headers
    from backend.models.user import User

    headers = register_and_login_headers(client, database_session, "media_teacher")
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    user = database_session.get(User, user_id)
    user.role = "admin"
    database_session.commit()

    response = client.post(
        "/api/v1/admin/media/upload",
        headers=headers,
        files={"file": ("note.txt", b"hello media", "text/plain")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "file"
    assert "latex" in body
    assert body["latex"].startswith("\\href{")

    link = client.post(
        "/api/v1/admin/media/link",
        headers=headers,
        json={"url": "https://cdn.example.com/fig.png", "label": "Figure"},
    )
    assert link.status_code == 200
    assert "includegraphics" in link.json()["latex"]
