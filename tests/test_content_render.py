"""Content rendering helpers for images, links, and multimedia blocks."""

from frontend.utils.content_render import (
    classify_media_url,
    media_from_payload,
    youtube_embed_url,
    youtube_player_url,
)


def test_youtube_watch_url_becomes_embed() -> None:
    assert (
        youtube_embed_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        == "https://www.youtube.com/embed/dQw4w9WgXcQ"
    )
    assert (
        youtube_embed_url("https://youtu.be/dQw4w9WgXcQ")
        == "https://www.youtube.com/embed/dQw4w9WgXcQ"
    )
    player = youtube_player_url("https://youtu.be/dQw4w9WgXcQ")
    assert player is not None
    assert "enablejsapi=1" in player


def test_classify_media_url() -> None:
    assert classify_media_url("https://youtu.be/abcdefghijk") == "youtube"
    assert classify_media_url("http://127.0.0.1:8000/media/a.mp4") == "video"
    assert classify_media_url("http://127.0.0.1:8000/media/a.png") == "image"
    assert classify_media_url("http://127.0.0.1:8000/media/a.pdf") == "download"


def test_media_from_single_payload() -> None:
    item = media_from_payload(
        {
            "title": "Demo",
            "url": "https://youtu.be/abcdefghijk",
            "kind": "youtube",
        }
    )
    assert item is not None
    assert item["kind"] == "youtube"
    assert item["url"] == "https://youtu.be/abcdefghijk"


def test_media_from_legacy_items() -> None:
    item = media_from_payload(
        {
            "title": "Old",
            "items": [
                {
                    "kind": "image",
                    "url": "http://127.0.0.1:8000/media/a.png",
                }
            ],
        }
    )
    assert item is not None
    assert item["kind"] == "image"
