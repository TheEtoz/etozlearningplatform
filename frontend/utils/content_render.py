"""Rich content rendering — Markdown/LaTeX text plus watchable media blocks."""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urlparse

import streamlit as st
import streamlit.components.v1 as components

from frontend.utils.latex_markdown import prepare_lecture_markdown

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
_VIDEO_EXT = {".mp4", ".webm", ".ogg", ".mov"}
_IMAGE_MARKER = re.compile(r"@@ETOZ_IMAGE:([^@]+)@@")
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# Cap display height; width follows the media's native aspect ratio.
_MEDIA_MAX_HEIGHT_PX = 360


def youtube_video_id(url: str) -> str | None:
    """Extract a YouTube video id from watch/share/embed URLs."""

    match = re.search(
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)"
        r"([A-Za-z0-9_-]{6,})",
        (url or "").strip(),
    )
    return match.group(1) if match else None


def youtube_embed_url(url: str) -> str | None:
    """Convert a YouTube watch/share URL into an embeddable URL."""

    video_id = youtube_video_id(url)
    if not video_id:
        return None
    return f"https://www.youtube.com/embed/{video_id}"


def youtube_player_url(url: str) -> str | None:
    """Legacy helper — embed URL for a video id (controls come from our bar)."""

    embed = youtube_embed_url(url)
    if not embed:
        return None
    return f"{embed}?controls=0&rel=0&playsinline=1&enablejsapi=1"


def classify_media_url(url: str) -> str:
    """Return youtube | video | image | download."""

    if youtube_embed_url(url):
        return "youtube"
    path = urlparse(url or "").path.lower()
    for ext in _VIDEO_EXT:
        if path.endswith(ext):
            return "video"
    for ext in _IMAGE_EXT:
        if path.endswith(ext):
            return "image"
    return "download"


def render_youtube(url: str) -> None:
    """YouTube player with our own seek/volume bar (Streamlit-safe).

    YouTube's native control bar often only receives play/pause clicks inside
    Streamlit's sandboxed component frame. Custom HTML controls sit outside
    that iframe and drive the player through the YouTube IFrame API.
    """

    video_id = youtube_video_id(url)
    if not video_id:
        return
    safe_id = html.escape(video_id, quote=True)
    height = _MEDIA_MAX_HEIGHT_PX
    width = int(round(height * 16 / 9))
    bar_h = 64
    components.html(
        f"""
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="utf-8" />
            <style>
              html, body {{
                margin: 0; padding: 0; background: #0f0f0f; color: #f3f3f3;
                font: 13px/1.3 system-ui, sans-serif; overflow: hidden;
              }}
              #player {{ width: 100%; height: {height}px; background: #000; }}
              .bar {{
                display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
                padding: 8px 10px; box-sizing: border-box; height: {bar_h}px;
                background: #1a1a1a; border-top: 1px solid #333;
              }}
              button {{
                border: 0; border-radius: 6px; padding: 6px 10px; cursor: pointer;
                background: #2f2f2f; color: #fff; font-weight: 600;
              }}
              button:hover {{ background: #3d3d3d; }}
              .seek-wrap, .vol-wrap {{
                display: flex; align-items: center; gap: 6px; flex: 1 1 auto;
                min-width: 120px;
              }}
              .vol-wrap {{ flex: 0 1 140px; min-width: 100px; }}
              input[type="range"] {{ width: 100%; accent-color: #3b82f6; }}
              .time {{ font-variant-numeric: tabular-nums; opacity: 0.9; white-space: nowrap; }}
            </style>
          </head>
          <body>
            <div id="player"></div>
            <div class="bar">
              <button type="button" id="btn-play">Play</button>
              <div class="seek-wrap">
                <span class="time" id="time">0:00</span>
                <input id="seek" type="range" min="0" max="100" value="0" step="0.25" />
                <span class="time" id="dur">0:00</span>
              </div>
              <button type="button" id="btn-mute">Mute</button>
              <div class="vol-wrap">
                <input id="vol" type="range" min="0" max="100" value="80" step="1" />
              </div>
            </div>
            <script>
              var player = null;
              var seeking = false;
              var ready = false;

              function fmt(seconds) {{
                seconds = Math.max(0, Math.floor(seconds || 0));
                var m = Math.floor(seconds / 60);
                var s = seconds % 60;
                return m + ":" + String(s).padStart(2, "0");
              }}

              function syncPlayLabel() {{
                if (!player || !ready) return;
                var playing = player.getPlayerState() === YT.PlayerState.PLAYING;
                document.getElementById("btn-play").textContent = playing ? "Pause" : "Play";
              }}

              function tick() {{
                if (!player || !ready || seeking) return;
                var duration = player.getDuration() || 0;
                var current = player.getCurrentTime() || 0;
                var seek = document.getElementById("seek");
                seek.max = String(duration || 100);
                seek.value = String(current);
                document.getElementById("time").textContent = fmt(current);
                document.getElementById("dur").textContent = fmt(duration);
                syncPlayLabel();
              }}

              function onYouTubeIframeAPIReady() {{
                player = new YT.Player("player", {{
                  height: "{height}",
                  width: "100%",
                  videoId: "{safe_id}",
                  playerVars: {{
                    autoplay: 0,
                    controls: 0,
                    disablekb: 0,
                    fs: 0,
                    rel: 0,
                    modestbranding: 1,
                    playsinline: 1,
                    iv_load_policy: 3,
                    enablejsapi: 1
                  }},
                  events: {{
                    onReady: function () {{
                      ready = true;
                      try {{ player.setVolume(80); }} catch (e) {{}}
                      document.getElementById("vol").value = "80";
                      setInterval(tick, 250);
                    }},
                    onStateChange: function () {{ syncPlayLabel(); }}
                  }}
                }});
              }}

              document.getElementById("btn-play").addEventListener("click", function () {{
                if (!player || !ready) return;
                if (player.getPlayerState() === YT.PlayerState.PLAYING) {{
                  player.pauseVideo();
                }} else {{
                  player.playVideo();
                }}
              }});

              var seekEl = document.getElementById("seek");
              seekEl.addEventListener("input", function () {{
                seeking = true;
                document.getElementById("time").textContent = fmt(Number(seekEl.value));
              }});
              seekEl.addEventListener("change", function () {{
                if (!player || !ready) return;
                player.seekTo(Number(seekEl.value), true);
                seeking = false;
              }});
              // Support drag-release on some browsers that only fire input.
              seekEl.addEventListener("mouseup", function () {{
                if (!player || !ready) return;
                player.seekTo(Number(seekEl.value), true);
                seeking = false;
              }});
              seekEl.addEventListener("touchend", function () {{
                if (!player || !ready) return;
                player.seekTo(Number(seekEl.value), true);
                seeking = false;
              }});

              document.getElementById("vol").addEventListener("input", function () {{
                if (!player || !ready) return;
                var value = Number(this.value);
                player.unMute();
                player.setVolume(value);
                document.getElementById("btn-mute").textContent = value === 0 ? "Unmute" : "Mute";
              }});

              document.getElementById("btn-mute").addEventListener("click", function () {{
                if (!player || !ready) return;
                if (player.isMuted() || player.getVolume() === 0) {{
                  player.unMute();
                  if (player.getVolume() === 0) player.setVolume(80);
                  document.getElementById("vol").value = String(player.getVolume());
                  this.textContent = "Mute";
                }} else {{
                  player.mute();
                  this.textContent = "Unmute";
                }}
              }});

              var tag = document.createElement("script");
              tag.src = "https://www.youtube.com/iframe_api";
              document.head.appendChild(tag);
              // If the API script was already present, call ready manually.
              if (window.YT && window.YT.Player) {{
                onYouTubeIframeAPIReady();
              }}
            </script>
          </body>
        </html>
        """,
        width=width,
        height=height + bar_h,
        scrolling=False,
    )


def render_video_file(url: str) -> None:
    """Show a controllable video player with seek and volume."""

    if youtube_embed_url(url):
        render_youtube(url)
        return
    height = _MEDIA_MAX_HEIGHT_PX
    # Native Streamlit player includes seek + volume.
    try:
        st.video(url)
        return
    except Exception:  # noqa: BLE001
        pass
    safe = html.escape(url, quote=True)
    components.html(
        f"""
        <video controls playsinline preload="metadata"
               style="display:block;max-height:{height}px;width:auto;height:auto;
                      max-width:100%;border-radius:8px;background:#000;">
          <source src="{safe}">
          Your browser cannot play this video.
        </video>
        """,
        height=height + 8,
    )


def render_image_file(url: str) -> None:
    """Show an image at a fixed max height; width follows the native ratio."""

    safe = html.escape(url, quote=True)
    height = _MEDIA_MAX_HEIGHT_PX
    st.markdown(
        f'<img src="{safe}" alt="figure" '
        f'style="display:block;max-height:{height}px;width:auto;height:auto;'
        f'max-width:100%;object-fit:contain;border-radius:8px;" />',
        unsafe_allow_html=True,
    )


def _force_download_url(url: str) -> str:
    """Prefer the attachment endpoint for local ``/media/`` files."""

    raw = (url or "").strip()
    if "/media-download/" in raw:
        return raw
    marker = "/media/"
    if marker not in raw:
        return raw
    stored = raw.rsplit(marker, 1)[-1].split("?", 1)[0].strip()
    if not stored or "/" in stored:
        return raw
    base = raw.split(marker, 1)[0]
    return f"{base}/media-download/{stored}"


def render_download_link(url: str, label: str | None = None) -> None:
    """Blue underlined link that downloads the file (local media) or opens it."""

    text = (label or "Download file").strip() or "Download file"
    href = _force_download_url(url)
    safe_url = html.escape(href, quote=True)
    safe_label = html.escape(text)
    # download= helps same-origin; media-download sets Content-Disposition.
    st.markdown(
        f'<p style="margin:0.4rem 0;">'
        f'<a href="{safe_url}" download '
        f'rel="noopener noreferrer" '
        f'style="color:#2563eb;text-decoration:underline;font-weight:600;">'
        f"{safe_label}</a></p>",
        unsafe_allow_html=True,
    )


def render_media_item(item: dict[str, Any]) -> None:
    """Render one multimedia payload (video / image / download)."""

    kind = (item.get("kind") or classify_media_url(str(item.get("url") or ""))).lower()
    url = str(item.get("url") or "").strip()
    label = item.get("label")
    if not url:
        return
    if kind == "youtube":
        render_youtube(url)
    elif kind == "video":
        render_video_file(url)
    elif kind == "image":
        render_image_file(url)
    else:
        render_download_link(url, str(label) if label else None)


def render_media_items(items: list[dict[str, Any]]) -> None:
    for item in items:
        render_media_item(item)
        st.write("")


def media_from_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Single media entry from a multimedia block payload."""

    payload = payload or {}
    url = str(payload.get("url") or "").strip()
    if url:
        kind = str(payload.get("kind") or classify_media_url(url)).lower()
        if kind == "file":
            kind = "download"
        return {
            "kind": kind,
            "url": url,
            "label": payload.get("label"),
            "title": payload.get("title"),
        }
    # Legacy multi-item payloads: take the first usable entry.
    for item in payload.get("items") or []:
        if isinstance(item, dict) and item.get("url"):
            kind = str(item.get("kind") or classify_media_url(str(item["url"]))).lower()
            if kind == "file":
                kind = "download"
            return {
                "kind": kind,
                "url": str(item["url"]).strip(),
                "label": item.get("label"),
                "title": payload.get("title") or item.get("title"),
            }
    return None


def media_items_from_payload(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Compatibility wrapper — zero or one item."""

    item = media_from_payload(payload)
    return [item] if item else []


def render_markdown_content(text: str, *, empty_caption: str | None = None) -> None:
    """Render lecture text with visible images and blue underlined links.

    Lecture blocks support standard ``\\includegraphics{…}`` and
    ``\\href{url}{label}`` (plus Markdown equivalents). Video/YouTube belongs
    in a Multimedia block, not inline macros.
    """

    body = prepare_lecture_markdown(text or "")
    if not body.strip():
        if empty_caption:
            st.caption(empty_caption)
        return

    token_pattern = re.compile(
        r"(@@ETOZ_IMAGE:[^@]+@@|!\[[^\]]*\]\([^)]+\)|\[[^\]]+\]\([^)]+\))"
    )
    parts = token_pattern.split(body)
    rendered_any = False
    for part in parts:
        if not part:
            continue
        image_marker = _IMAGE_MARKER.fullmatch(part.strip())
        if image_marker:
            render_image_file(image_marker.group(1).strip())
            rendered_any = True
            continue
        md_image = _MD_IMAGE.fullmatch(part.strip())
        if md_image:
            render_image_file(md_image.group(2).strip())
            rendered_any = True
            continue
        md_link = _MD_LINK.fullmatch(part.strip())
        if md_link:
            render_download_link(md_link.group(2).strip(), md_link.group(1).strip())
            rendered_any = True
            continue
        if part.strip():
            st.markdown(part)
            rendered_any = True
    if not rendered_any and empty_caption:
        st.caption(empty_caption)
