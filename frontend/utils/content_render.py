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
_FG_MARKER = re.compile(r"@@ETOZ_FG:([^|]+)\|((?:(?!@@).)*?)@@", re.DOTALL)
_BG_MARKER = re.compile(r"@@ETOZ_BG:([^|]+)\|((?:(?!@@).)*?)@@", re.DOTALL)
_BOX_START = re.compile(r"@@ETOZ_BOX:([^|]+)\|((?:(?!@@).)*?)@@")
_BOX_END = "@@ETOZ_BOX_END@@"
_TIKZ_START = "@@ETOZ_TIKZ@@"
_TIKZ_END = "@@ETOZ_TIKZ_END@@"
_TABLE_START = "@@ETOZ_TABLE@@"
_TABLE_END = "@@ETOZ_TABLE_END@@"

_BOX_STYLES: dict[str, tuple[str, str, str]] = {
    # env: (accent, background, title color)
    "keypoints": ("#2563eb", "#eff6ff", "#1e3a8a"),
    "keypoint": ("#2563eb", "#eff6ff", "#1e3a8a"),
    "formula": ("#7c3aed", "#f5f3ff", "#4c1d95"),
    "note": ("#0d9488", "#f0fdfa", "#115e59"),
    "tip": ("#059669", "#ecfdf5", "#065f46"),
    "info": ("#0284c7", "#f0f9ff", "#075985"),
    "warning": ("#d97706", "#fffbeb", "#92400e"),
    "caution": ("#d97706", "#fffbeb", "#92400e"),
    "important": ("#e11d48", "#fff1f2", "#9f1239"),
    "alert": ("#e11d48", "#fff1f2", "#9f1239"),
    "example": ("#4f46e5", "#eef2ff", "#312e81"),
    "definition": ("#0f766e", "#f0fdfa", "#134e4a"),
    "theorem": ("#6d28d9", "#f5f3ff", "#4c1d95"),
    "remark": ("#64748b", "#f8fafc", "#334155"),
}

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


def _inject_inline_colors(chunk: str) -> str:
    """Turn colour markers into HTML spans Streamlit can render."""

    def fg_repl(match: re.Match[str]) -> str:
        color = html.escape(match.group(1).strip(), quote=True)
        inner = match.group(2)
        return f'<span style="color:{color};font-weight:600;">{inner}</span>'

    def bg_repl(match: re.Match[str]) -> str:
        color = html.escape(match.group(1).strip(), quote=True)
        inner = match.group(2)
        return (
            f'<span style="background:{color};padding:0.1em 0.35em;'
            f'border-radius:0.3em;">{inner}</span>'
        )

    chunk = _FG_MARKER.sub(fg_repl, chunk)
    chunk = _BG_MARKER.sub(bg_repl, chunk)
    return chunk


def _protect_math_segments(text: str) -> tuple[str, list[str]]:
    """Replace ``$...$`` / ``$$...$$`` with placeholders before HTML escaping."""

    protected: list[str] = []

    def stash(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"@@M{len(protected) - 1}@@"

    text = re.sub(r"\$\$(.+?)\$\$", stash, text, flags=re.DOTALL)
    text = re.sub(
        r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)",
        stash,
        text,
        flags=re.DOTALL,
    )
    return text, protected


def _restore_math_segments(text: str, protected: list[str]) -> str:
    for index, value in enumerate(protected):
        text = text.replace(f"@@M{index}@@", value)
    return text


def _inline_markdown_to_html(text: str) -> str:
    """Convert a short markdown/KaTeX fragment to HTML (math left as ``$``)."""

    colored = _inject_inline_colors(text or "")
    plain, math_bits = _protect_math_segments(colored)
    # Escape everything except our colour spans.
    pieces = re.split(r"(<span\b[^>]*>.*?</span>)", plain, flags=re.DOTALL)
    rebuilt: list[str] = []
    for piece in pieces:
        if piece.startswith("<span"):
            rebuilt.append(piece)
        else:
            safe = html.escape(piece)
            safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
            safe = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", safe)
            safe = re.sub(r"`([^`]+)`", r"<code>\1</code>", safe)
            rebuilt.append(safe)
    return _restore_math_segments("".join(rebuilt), math_bits)


def _callout_body_to_html(body: str) -> str:
    """Turn converted lecture-box markdown into HTML lists/paragraphs."""

    text = body or ""
    # Keep display-math blocks intact across newlines.
    display_blocks: list[str] = []

    def stash_display(match: re.Match[str]) -> str:
        display_blocks.append(match.group(1).strip())
        return f"\n\n@@DISP{len(display_blocks) - 1}@@\n\n"

    text = re.sub(r"\$\$(.+?)\$\$", stash_display, text, flags=re.DOTALL)

    lines = text.splitlines()
    html_parts: list[str] = []
    list_type: str | None = None

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            html_parts.append(f"</{list_type}>")
            list_type = None

    bullet = re.compile(r"^\s*[-*]\s+(.*)$")
    numbered = re.compile(r"^\s*\d+\.\s+(.*)$")
    disp = re.compile(r"^@@DISP(\d+)@@$")

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_list()
            continue
        disp_match = disp.match(line.strip())
        if disp_match:
            close_list()
            formula = display_blocks[int(disp_match.group(1))]
            # Prefer \(...\) style delimiters KaTeX auto-render always handles.
            html_parts.append(
                '<div style="margin:0.65rem 0;overflow-x:auto;text-align:center;">'
                f"$${html.escape(formula)}$$"
                "</div>"
            )
            continue
        bullet_match = bullet.match(line)
        number_match = numbered.match(line)
        if bullet_match:
            if list_type != "ul":
                close_list()
                html_parts.append(
                    '<ul style="margin:0.35rem 0 0.15rem 1.1rem;padding:0;">'
                )
                list_type = "ul"
            html_parts.append(
                f'<li style="margin:0.35rem 0;line-height:1.55;">'
                f"{_inline_markdown_to_html(bullet_match.group(1))}</li>"
            )
            continue
        if number_match:
            if list_type != "ol":
                close_list()
                html_parts.append(
                    '<ol style="margin:0.35rem 0 0.15rem 1.1rem;padding:0;">'
                )
                list_type = "ol"
            html_parts.append(
                f'<li style="margin:0.35rem 0;line-height:1.55;">'
                f"{_inline_markdown_to_html(number_match.group(1))}</li>"
            )
            continue
        close_list()
        html_parts.append(
            f'<p style="margin:0.4rem 0;line-height:1.55;">'
            f"{_inline_markdown_to_html(line)}</p>"
        )
    close_list()
    return "\n".join(html_parts)


def _markdown_table_to_html(table_md: str) -> str:
    """Convert a pipe markdown table (with ``$math$``) into an HTML table."""

    rows: list[list[str]] = []
    for raw in (table_md or "").splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells):
            continue
        rows.append(cells)
    if not rows:
        return ""
    parts = [
        '<table style="border-collapse:collapse;width:100%;font-size:0.95rem;">'
    ]
    for index, cells in enumerate(rows):
        parts.append("<tr>")
        tag = "th" if index == 0 else "td"
        weight = "700" if index == 0 else "400"
        bg = "#e2e8f0" if index == 0 else ("#fff" if index % 2 else "#f8fafc")
        for cell in cells:
            parts.append(
                f'<{tag} style="border:1px solid #cbd5e1;padding:0.45rem 0.55rem;'
                f'text-align:center;background:{bg};font-weight:{weight};">'
                f"{_inline_markdown_to_html(cell)}</{tag}>"
            )
        parts.append("</tr>")
    parts.append("</table>")
    return "".join(parts)


def _katex_document(body_html: str, *, height: int) -> None:
    """Show a finished HTML fragment with KaTeX already wired up."""

    components.html(
        f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
  <script defer
    src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
  <script defer
    src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
    onload="renderMathInElement(document.body, {{
      delimiters: [
        {{left: '$$', right: '$$', display: true}},
        {{left: '$', right: '$', display: false}}
      ],
      throwOnError: false
    }});"></script>
  <style>
    html, body {{
      margin: 0; padding: 0.15rem 0;
      font-family: "Source Sans Pro", system-ui, sans-serif;
      color: #0f172a;
      background: transparent;
    }}
    .katex {{ font-size: 1.05em; }}
  </style>
</head>
<body>
{body_html}
</body>
</html>
""",
        height=height,
        scrolling=True,
    )


def _render_math_table(table_md: str) -> None:
    try:
        html_table = _markdown_table_to_html(table_md)
        if not html_table:
            return
        rows = max(1, table_md.count("\n") + 1)
        height = min(640, max(120, 48 + rows * 36))
        _katex_document(html_table, height=height)
    except Exception:
        st.caption("Table unavailable.")


def _render_callout_box(env: str, title: str, body: str) -> None:
    """Render a keypoints/note/… card as one compiled HTML+KaTeX block."""

    try:
        accent, background, title_color = _BOX_STYLES.get(
            env.lower(),
            ("#334155", "#f8fafc", "#0f172a"),
        )
        safe_title = html.escape(title or env.title())
        body_html = _callout_body_to_html(body)
        # Rough height from content so the iframe is not cropped.
        line_count = max(1, len([line for line in (body or "").splitlines() if line.strip()]))
        char_count = len(body or "")
        height = min(1000, max(130, 80 + line_count * 52 + char_count // 10))

        components.html(
            f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
  <script defer
    src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
  <script defer
    src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
    onload="renderMathInElement(document.body, {{
      delimiters: [
        {{left: '$$', right: '$$', display: true}},
        {{left: '$', right: '$', display: false}}
      ],
      throwOnError: false
    }});"></script>
  <style>
    html, body {{
      margin: 0; padding: 0;
      font-family: "Source Sans Pro", system-ui, sans-serif;
      color: #0f172a;
      background: transparent;
    }}
    .box {{
      border-left: 4px solid {accent};
      background: {background};
      padding: 0.85rem 1rem;
      border-radius: 0 0.55rem 0.55rem 0;
    }}
    .title {{
      font-weight: 800;
      letter-spacing: 0.02em;
      color: {title_color};
      font-size: 0.95rem;
      margin: 0 0 0.35rem 0;
    }}
    .body {{ font-size: 0.98rem; }}
    .body ul, .body ol {{ margin-top: 0.25rem; }}
    .katex {{ font-size: 1.05em; }}
  </style>
</head>
<body>
  <div class="box">
    <div class="title">{safe_title}</div>
    <div class="body">
      {body_html}
    </div>
  </div>
</body>
</html>
""",
            height=height,
            scrolling=True,
        )
    except Exception:
        # Soft fallback — still never crash the page.
        with st.container(border=True):
            st.markdown(f"**{title or env.title()}**")
            if body.strip():
                try:
                    st.markdown(body)
                except Exception:
                    st.caption("Content unavailable.")


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def _cached_tikz_png(source: str) -> bytes | None:
    """Compile once to PNG — safe for Streamlit ``st.image`` / PIL."""

    from frontend.utils.tikz_render import compile_tikz_png

    return compile_tikz_png(source)


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def _cached_tikz_svg(source: str) -> bytes | None:
    """SVG fallback when PNG is unavailable."""

    from frontend.utils.tikz_render import compile_tikz_svg

    return compile_tikz_svg(source)


def _show_svg_bytes(svg: bytes) -> None:
    """Embed finished SVG without going through PIL."""

    import base64

    encoded = base64.b64encode(svg).decode("ascii")
    components.html(
        f"""
<div style="width:100%;text-align:center;background:#fff;padding:0.5rem 0;">
  <img alt="diagram" style="max-width:100%;height:auto;"
       src="data:image/svg+xml;base64,{encoded}" />
</div>
""",
        height=420,
        scrolling=True,
    )


def _render_tikz(source: str) -> None:
    """Compile TikZ fully, then show only the finished figure (never a traceback)."""

    safe = (source or "").strip()
    if not safe:
        return

    try:
        png: bytes | None = None
        svg: bytes | None = None
        with st.spinner("Compiling diagram…"):
            try:
                png = _cached_tikz_png(safe)
            except Exception:
                png = None
            if not png:
                try:
                    svg = _cached_tikz_svg(safe)
                except Exception:
                    svg = None

        if png:
            st.image(png, use_container_width=True)
            return
        if svg:
            _show_svg_bytes(svg)
            return

        st.caption("Diagram unavailable.")
    except Exception:
        # Absolute last resort — never surface stack traces to learners/teachers.
        st.caption("Diagram unavailable.")


def _render_markdown_segments(body: str) -> bool:
    """Render one prepared markdown chunk (no outer box/tikz splitting)."""

    token_pattern = re.compile(
        r"(@@ETOZ_IMAGE:[^@]+@@|!\[[^\]]*\]\([^)]+\)|\[[^\]]+\]\([^)]+\))"
    )
    parts = token_pattern.split(body)
    rendered_any = False
    for part in parts:
        if not part:
            continue
        try:
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
                colored = _inject_inline_colors(part)
                st.markdown(colored, unsafe_allow_html=True)
                rendered_any = True
        except Exception:
            continue
    return rendered_any


def render_markdown_content(text: str, *, empty_caption: str | None = None) -> None:
    """Render lecture text with images, colours, callouts, and TikZ.

    Errors are swallowed so Streamlit never shows a red traceback to users.
    """

    try:
        body = prepare_lecture_markdown(text or "")
    except Exception:
        if empty_caption:
            st.caption(empty_caption)
        else:
            st.caption("Content unavailable.")
        return

    if not body.strip():
        if empty_caption:
            st.caption(empty_caption)
        return

    try:
        rendered_any = False
        cursor = 0
        block_pattern = re.compile(
            r"(@@ETOZ_TIKZ@@.*?@@ETOZ_TIKZ_END@@|"
            r"@@ETOZ_BOX:[^@]+@@.*?@@ETOZ_BOX_END@@|"
            r"@@ETOZ_TABLE@@.*?@@ETOZ_TABLE_END@@)",
            re.DOTALL,
        )
        for match in block_pattern.finditer(body):
            before = body[cursor : match.start()]
            if before.strip():
                rendered_any = _render_markdown_segments(before) or rendered_any
            block = match.group(1)
            try:
                if block.startswith(_TIKZ_START):
                    tikz_src = block[len(_TIKZ_START) : -len(_TIKZ_END)].strip()
                    _render_tikz(tikz_src)
                    rendered_any = True
                elif block.startswith(_TABLE_START):
                    table_md = block[len(_TABLE_START) : -len(_TABLE_END)].strip()
                    _render_math_table(table_md)
                    rendered_any = True
                else:
                    header = _BOX_START.match(block)
                    if header:
                        env = header.group(1).strip()
                        title = header.group(2).strip()
                        inner = block[header.end() :]
                        if inner.endswith(_BOX_END):
                            inner = inner[: -len(_BOX_END)]
                        _render_callout_box(env, title, inner.strip())
                        rendered_any = True
                    else:
                        rendered_any = (
                            _render_markdown_segments(block) or rendered_any
                        )
            except Exception:
                st.caption("Part of this section could not be shown.")
            cursor = match.end()

        tail = body[cursor:]
        if tail.strip():
            rendered_any = _render_markdown_segments(tail) or rendered_any

        if not rendered_any and empty_caption:
            st.caption(empty_caption)
    except Exception:
        st.caption(empty_caption or "Content unavailable.")
