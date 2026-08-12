"""Compile TikZ diagrams via Kroki (used by the public render proxy)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

# Keep in sync with frontend.utils.tikz_render for lecture colours.
_DEFAULT_COLORS: dict[str, str] = {
    "red1": "#E11D48",
    "blue1": "#2563EB",
    "teal1": "#0D9488",
    "orange1": "#EA580C",
    "green1": "#059669",
    "purple1": "#7C3AED",
    "yellow1": "#CA8A04",
    "gray1": "#64748B",
}

_KROKI_URL = "https://kroki.io/"
_TIMEOUT_SECONDS = 90
_ALWAYS_LIBRARIES = (
    "arrows.meta",
    "calc",
    "positioning",
    "patterns",
    "decorations.pathmorphing",
)
_MAX_SOURCE_CHARS = 80_000


def _normalize_tikzpicture(source: str) -> str:
    text = (source or "").strip()
    text = re.sub(r"\\end\{(?:center|figure|minipage)\}", "", text, flags=re.I)
    text = re.sub(
        r"\\begin\{(?:center|figure|minipage)\}(?:\[[^\]]*\])?",
        "",
        text,
        flags=re.I,
    )
    text = text.strip()
    if not text:
        return ""
    if not re.match(r"\\begin\{tikzpicture\}", text, flags=re.I):
        text = "\\begin{tikzpicture}\n" + text + "\n\\end{tikzpicture}"
    return text


def _needed_libraries(tikz: str) -> list[str]:
    libs = list(_ALWAYS_LIBRARIES)
    feature_libs: list[tuple[str, tuple[str, ...]]] = [
        (r"\\pic\b|\{angle\s*=|angle eccentricity|angle radius", ("angles", "quotes")),
        (r"quotes|/tikz/quotes|\"\$", ("quotes",)),
        (r"\\matrix\b|matrix of nodes", ("matrix",)),
        (r"\\fillbetween\b|intersections", ("intersections", "fillbetween")),
        (r"backgrounds|on background layer", ("backgrounds",)),
        (r"fit\s*=|\\node\[fit", ("fit",)),
        (r"shadows|drop shadow", ("shadows",)),
        (r"decorations\.pathreplacing|brace\b", ("decorations.pathreplacing",)),
        (r"shapes\.geometric|ellipse\b|diamond\b", ("shapes.geometric",)),
    ]
    for pattern, needed in feature_libs:
        if re.search(pattern, tikz, flags=re.IGNORECASE):
            for name in needed:
                if name not in libs:
                    libs.append(name)
    for match in re.finditer(r"\\usetikzlibrary\{([^{}]+)\}", tikz):
        for part in match.group(1).split(","):
            name = part.strip()
            if name and name not in libs:
                libs.append(name)
    return libs


def _color_preamble(tikz: str) -> str:
    used = {item.lower() for item in re.findall(r"\b([a-zA-Z][a-zA-Z0-9]*)\b", tikz)}
    lines: list[str] = []
    seen: set[str] = set()
    for name, hex_color in _DEFAULT_COLORS.items():
        if not (name.endswith("1") or name.lower() in used):
            continue
        if name in seen:
            continue
        seen.add(name)
        body = hex_color.lstrip("#").upper()
        lines.append(f"\\definecolor{{{name}}}{{HTML}}{{{body}}}")
    return "\n".join(lines)


def build_tikz_document(source: str) -> str:
    tikz = _normalize_tikzpicture(source)
    if not tikz:
        return ""
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


def compile_tikz(source: str, *, output_format: str = "png") -> bytes | None:
    """Compile a tikzpicture to PNG or SVG bytes via Kroki."""

    if not source or len(source) > _MAX_SOURCE_CHARS:
        return None
    fmt = (output_format or "png").lower().strip()
    if fmt not in {"png", "svg"}:
        return None
    document = build_tikz_document(source)
    if not document:
        return None
    payload = json.dumps(
        {
            "diagram_source": document,
            "diagram_type": "tikz",
            "output_format": fmt,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        _KROKI_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "image/png,image/svg+xml,*/*",
            "User-Agent": "ETOZ-Learning-Platform/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            data = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return None
    if not data:
        return None
    if fmt == "png" and data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if fmt == "svg":
        head = data[:200].lower()
        if b"<svg" not in head and b"<?xml" not in data[:50]:
            return None
    return data
