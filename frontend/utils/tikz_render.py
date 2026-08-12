"""Compile TikZ to SVG before display (no half-rendered browser preview)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from frontend.utils.latex_markdown import _DEFAULT_COLOR_MAP

_KROKI_URL = "https://kroki.io/"
_TIMEOUT_SECONDS = 60

_ALWAYS_LIBRARIES = (
    "arrows.meta",
    "calc",
    "positioning",
    "patterns",
    "decorations.pathmorphing",
)


def _normalize_tikzpicture(source: str) -> str:
    """Return a clean ``tikzpicture`` environment."""

    text = (source or "").strip()
    # Stray layout closers sometimes survive lecture conversion.
    text = re.sub(r"\\end\{(?:center|figure|minipage)\}", "", text, flags=re.I)
    text = re.sub(r"\\begin\{(?:center|figure|minipage)\}(?:\[[^\]]*\])?", "", text, flags=re.I)
    text = text.strip()
    if not text:
        return ""
    if not re.match(r"\\begin\{tikzpicture\}", text, flags=re.I):
        text = "\\begin{tikzpicture}\n" + text + "\n\\end{tikzpicture}"
    return text


def _needed_libraries(tikz: str) -> list[str]:
    libs = list(_ALWAYS_LIBRARIES)
    if re.search(r"\\begin\{axis\}|\\addplot\b|\\pgfplotsset\b", tikz):
        # Kroki TikZ image may still fail on heavy pgfplots; include if present.
        pass
    # Preserve author-requested libraries.
    for match in re.finditer(r"\\usetikzlibrary\{([^{}]+)\}", tikz):
        for part in match.group(1).split(","):
            name = part.strip()
            if name and name not in libs:
                libs.append(name)
    return libs


def _color_preamble(tikz: str) -> str:
    """Define custom lecture colours referenced by the picture."""

    used = {item.lower() for item in re.findall(r"\b([a-zA-Z][a-zA-Z0-9]*)\b", tikz)}
    lines: list[str] = []
    seen: set[str] = set()
    for name, hex_color in _DEFAULT_COLOR_MAP.items():
        # Always ship the common *1 lecture palette; add others when referenced.
        if not (name.endswith("1") or name.lower() in used):
            continue
        if name in seen:
            continue
        seen.add(name)
        body = hex_color.lstrip("#").upper()
        lines.append(f"\\definecolor{{{name}}}{{HTML}}{{{body}}}")
    return "\n".join(lines)


def build_tikz_document(source: str) -> str:
    """Wrap a tikzpicture in a standalone document ready for Kroki."""

    tikz = _normalize_tikzpicture(source)
    if not tikz:
        return ""
    # Drop libraries already embedded; we re-declare a safe set.
    tikz_body = re.sub(r"\\usetikzlibrary\{[^{}]*\}", "", tikz)
    libs = ",".join(_needed_libraries(tikz))
    colors = _color_preamble(tikz)
    return "\n".join(
        [
            "\\documentclass[border=2pt]{standalone}",
            "\\usepackage{tikz}",
            "\\usepackage{amsmath}",
            "\\usepackage{amssymb}",
            f"\\usetikzlibrary{{{libs}}}",
            colors,
            "\\begin{document}",
            tikz_body,
            "\\end{document}",
        ]
    )


def compile_tikz_svg(source: str) -> bytes | None:
    """Compile TikZ via Kroki and return SVG bytes, or None on failure."""

    document = build_tikz_document(source)
    if not document:
        return None
    payload = json.dumps(
        {
            "diagram_source": document,
            "diagram_type": "tikz",
            "output_format": "svg",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        _KROKI_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "image/svg+xml",
            "User-Agent": "ETOZ-Learning-Platform/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            data = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return None
    if not data or b"<svg" not in data[:200].lower() and b"<?xml" not in data[:50]:
        return None
    return data
