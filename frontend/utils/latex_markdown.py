"""Convert educational LaTeX lecture notes into Markdown + KaTeX for Streamlit.

Supports colours (``\\textcolor``, ``\\colorbox``, ``\\definecolor``), callout
boxes (``keypoints``, ``note``, ``formula``, …), TikZ pictures (rendered later
via TikZJax), and KaTeX math (``pmatrix``, ``frac``, …).
"""

from __future__ import annotations

import html
import re
from typing import Callable


# Streamlit palette names → used as :name[text]
_STREAMLIT_COLORS = {
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "violet",
    "gray",
    "grey",
    "rainbow",
    "primary",
}

# Common lecture custom colour aliases → CSS hex
_DEFAULT_COLOR_MAP: dict[str, str] = {
    "red1": "#e11d48",
    "red2": "#f43f5e",
    "blue1": "#2563eb",
    "blue2": "#3b82f6",
    "green1": "#059669",
    "green2": "#10b981",
    "orange1": "#ea580c",
    "yellow1": "#ca8a04",
    "purple1": "#7c3aed",
    "violet1": "#7c3aed",
    "teal1": "#0d9488",
    "pink1": "#db2777",
    "gray1": "#64748b",
    "grey1": "#64748b",
    "black": "#0f172a",
    "white": "#ffffff",
}

_BOX_ENVS = (
    "keypoints",
    "keypoint",
    "formula",
    "note",
    "tip",
    "warning",
    "important",
    "example",
    "definition",
    "theorem",
    "remark",
    "alert",
    "info",
    "caution",
)

_BOX_TITLES = {
    "keypoints": "Key points",
    "keypoint": "Key point",
    "formula": "Formula",
    "note": "Note",
    "tip": "Tip",
    "warning": "Warning",
    "important": "Important",
    "example": "Example",
    "definition": "Definition",
    "theorem": "Theorem",
    "remark": "Remark",
    "alert": "Alert",
    "info": "Info",
    "caution": "Caution",
}


def looks_like_latex(text: str) -> bool:
    """Heuristic: treat as LaTeX document / TeX-heavy content."""

    sample = text[:8000]
    markers = (
        r"\\documentclass\b",
        r"\\begin\{document\}",
        r"\\section\*?\{",
        r"\\subsection\*?\{",
        r"\\begin\{lstlisting\}",
        r"\\begin\{itemize\}",
        r"\\begin\{enumerate\}",
        r"\\begin\{pmatrix\}",
        r"\\begin\{bmatrix\}",
        r"\\begin\{tikzpicture\}",
        r"\\begin\{keypoints\}",
        r"\\textcolor\{",
        r"\\definecolor\{",
    )
    hits = sum(1 for pattern in markers if re.search(pattern, sample))
    return hits >= 1 and ("\\" in sample)


def _read_braced(text: str, open_at: int) -> tuple[str, int] | None:
    """Read ``{...}`` starting at ``open_at`` (must point at '{')."""

    if open_at >= len(text) or text[open_at] != "{":
        return None
    depth = 0
    index = open_at
    while index < len(text):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[open_at + 1 : index], index + 1
        index += 1
    return None


def _replace_command(text: str, command: str, wrapper: str) -> str:
    """Replace \\command{inner} with wrapper.format(inner=...)."""

    needle = "\\" + command + "{"
    output: list[str] = []
    i = 0
    while i < len(text):
        index = text.find(needle, i)
        if index < 0:
            output.append(text[i:])
            break
        output.append(text[i:index])
        braced = _read_braced(text, index + len(command) + 1)
        if braced is None:
            output.append(text[index : index + len(needle)])
            i = index + len(needle)
            continue
        inner, after = braced
        output.append(wrapper.format(inner=inner))
        i = after
    return "".join(output)


def _replace_two_brace_args(
    text: str, command: str, formatter: Callable[[str, str], str]
) -> str:
    """Replace \\command{a}{b} using formatter(a, b) -> str."""

    needle = "\\" + command + "{"
    output: list[str] = []
    i = 0
    while i < len(text):
        index = text.find(needle, i)
        if index < 0:
            output.append(text[i:])
            break
        output.append(text[i:index])
        first = _read_braced(text, index + len(command) + 1)
        if first is None:
            output.append(text[index : index + len(needle)])
            i = index + len(needle)
            continue
        arg1, after_first = first
        second = _read_braced(text, after_first)
        if second is None:
            output.append(text[index:after_first])
            i = after_first
            continue
        arg2, after_second = second
        output.append(formatter(arg1, arg2))
        i = after_second
    return "".join(output)


def _extract_braced_command(text: str, command: str) -> str | None:
    needle = "\\" + command + "{"
    index = text.find(needle)
    if index < 0:
        return None
    braced = _read_braced(text, index + len(command) + 1)
    if braced is None:
        return None
    inner, _ = braced
    cleaned = inner
    for _ in range(6):
        nxt = re.sub(
            r"\\(?:textbf|textit|emph|Huge|huge|LARGE|Large|large|"
            r"normalsize|small|footnotesize|bfseries|itshape)\s*\{([^{}]*)\}",
            r"\1",
            cleaned,
        )
        nxt = re.sub(r"\\\\(?:\[.*?\])?", " ", nxt)
        if nxt == cleaned:
            break
        cleaned = nxt
    return re.sub(r"\s+", " ", cleaned).strip()


def _rgb_channel(value: str, *, scale_255: bool) -> int:
    raw = float(value.strip())
    if scale_255:
        return max(0, min(255, int(round(raw))))
    return max(0, min(255, int(round(raw * 255))))


def _parse_definecolors(text: str) -> dict[str, str]:
    """Parse ``\\definecolor{name}{model}{spec}`` into name → #hex."""

    colors = dict(_DEFAULT_COLOR_MAP)
    pattern = re.compile(
        r"\\definecolor\{([^{}]+)\}\{([^{}]+)\}\{([^{}]*)\}",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        name = match.group(1).strip()
        model_raw = match.group(2).strip()
        model = model_raw.lower()
        spec = match.group(3).strip()
        try:
            if model == "html":
                hex_body = spec.lstrip("#")
                if re.fullmatch(r"[0-9a-fA-F]{6}", hex_body):
                    colors[name] = f"#{hex_body.lower()}"
            elif model_raw == "RGB":
                parts = [p.strip() for p in spec.split(",")]
                if len(parts) == 3:
                    r, g, b = (_rgb_channel(p, scale_255=True) for p in parts)
                    colors[name] = f"#{r:02x}{g:02x}{b:02x}"
            elif model == "rgb":
                parts = [p.strip() for p in spec.split(",")]
                if len(parts) == 3:
                    r, g, b = (_rgb_channel(p, scale_255=False) for p in parts)
                    colors[name] = f"#{r:02x}{g:02x}{b:02x}"
        except ValueError:
            continue
    return colors


def _resolve_color(name: str, color_map: dict[str, str]) -> tuple[str, str]:
    """Return (kind, value) where kind is 'palette' or 'hex'."""

    key = (name or "").strip()
    lower = key.lower()
    if lower in _STREAMLIT_COLORS:
        return "palette", lower
    if lower in color_map:
        return "hex", color_map[lower]
    if key in color_map:
        return "hex", color_map[key]
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", key):
        return "hex", key if key.startswith("#") else f"#{key}"
    if lower in _DEFAULT_COLOR_MAP:
        return "hex", _DEFAULT_COLOR_MAP[lower]
    # Fallback: treat as CSS named colour.
    return "hex", lower


def _prose_color_span(color_name: str, content: str, color_map: dict[str, str]) -> str:
    kind, value = _resolve_color(color_name, color_map)
    if kind == "palette":
        return f":{value}[{content}]"
    return f"@@ETOZ_FG:{value}|{content}@@"


def _prose_bg_span(color_name: str, content: str, color_map: dict[str, str]) -> str:
    kind, value = _resolve_color(color_name, color_map)
    if kind == "palette":
        return f":{value}-background[{content}]"
    return f"@@ETOZ_BG:{value}|{content}@@"


def _math_textcolor(color_name: str, content: str, color_map: dict[str, str]) -> str:
    kind, value = _resolve_color(color_name, color_map)
    # KaTeX accepts named colours and #hex.
    katex_color = value if kind == "hex" else value
    return rf"\textcolor{{{katex_color}}}{{{content}}}"


def _extract_document_body(text: str) -> tuple[str, str | None, str | None]:
    """Return body, optional title, optional author."""

    title = _extract_braced_command(text, "title")
    author = _extract_braced_command(text, "author")

    begin = re.search(r"\\begin\{document\}", text)
    end = re.search(r"\\end\{document\}", text)
    if begin and end and end.start() > begin.end():
        body = text[begin.end() : end.start()]
    elif begin:
        body = text[begin.end() :]
    else:
        body = text
        body = re.sub(
            r"^\\documentclass(\[[^\]]*\])?\{[^}]*\}\s*",
            "",
            body,
            flags=re.MULTILINE,
        )
        body = re.sub(r"^\\usepackage(\[[^\]]*\])?\{[^}]*\}\s*", "", body, flags=re.M)
        body = re.sub(
            r"^\\(definecolor|geometry|titleformat|tcbuselibrary|newtcolorbox|"
            r"setcounter)\{.*?\}$",
            "",
            body,
            flags=re.M,
        )
    return body, title, author


def _unwrap_env(text: str, env: str) -> str:
    """Replace \\begin{env}[...]...\\end{env} with inner content."""

    pattern = re.compile(
        r"\\begin\{"
        + re.escape(env)
        + r"\}(?:\[[^\]]*\])?(.*?)\\end\{"
        + re.escape(env)
        + r"\}",
        re.DOTALL | re.IGNORECASE,
    )
    return pattern.sub(r"\n\n\1\n\n", text)


def _convert_callout_boxes(text: str) -> str:
    """Turn lecture boxes into render markers with a default title."""

    for env in _BOX_ENVS:
        pattern = re.compile(
            r"\\begin\{"
            + re.escape(env)
            + r"\}(?:\[[^\]]*\])?(.*?)\\end\{"
            + re.escape(env)
            + r"\}",
            re.DOTALL | re.IGNORECASE,
        )
        title = _BOX_TITLES.get(env, env.title())

        def repl(match: re.Match[str], *, env: str = env, title: str = title) -> str:
            inner = match.group(1).strip("\n")
            # If the box starts with a bold heading, use it as the title.
            heading = re.match(
                r"^\s*\\textbf\{([^{}]+)\}\s*",
                inner,
            )
            box_title = title
            if heading:
                box_title = heading.group(1).strip() or title
                inner = inner[heading.end() :]
            return (
                f"\n\n@@ETOZ_BOX:{env}|{box_title}@@\n"
                f"{inner.strip()}\n"
                f"@@ETOZ_BOX_END@@\n\n"
            )

        text = pattern.sub(repl, text)

    # Generic tcolorbox — keep as a note-style callout.
    tcb = re.compile(
        r"\\begin\{tcolorbox\}(?:\[[^\]]*\])?(.*?)\\end\{tcolorbox\}",
        re.DOTALL | re.IGNORECASE,
    )
    text = tcb.sub(
        lambda match: (
            "\n\n@@ETOZ_BOX:note|Note@@\n"
            f"{match.group(1).strip()}\n"
            "@@ETOZ_BOX_END@@\n\n"
        ),
        text,
    )
    return text


def _extract_tikz(text: str) -> str:
    """Replace tikzpicture blocks with opaque markers for later HTML render."""

    pattern = re.compile(
        r"\\begin\{tikzpicture\}(?:\[[^\]]*\])?(.*?)\\end\{tikzpicture\}",
        re.DOTALL | re.IGNORECASE,
    )

    def repl(match: re.Match[str]) -> str:
        # Keep full environment so TikZJax sees valid TikZ.
        full = match.group(0).strip()
        # Escape marker delimiters that could break splitting.
        safe = full.replace("@@", "")
        return f"\n\n@@ETOZ_TIKZ@@\n{safe}\n@@ETOZ_TIKZ_END@@\n\n"

    return pattern.sub(repl, text)


def _unwrap_layout_envs(text: str) -> str:
    for env in (
        "minipage",
        "turn",
        "sideways",
        "center",
        "flushleft",
        "flushright",
    ):
        text = _unwrap_env(text, env)
    return text


def _normalize_math_delimiters(text: str) -> str:
    """Convert LaTeX display/inline delimiters to KaTeX ``$$`` / ``$``."""

    text = re.sub(r"\\\[(.*?)\\\]", r"\n\n$$\1$$\n\n", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text, flags=re.DOTALL)
    return text


def _stash_math(
    text: str, color_map: dict[str, str]
) -> tuple[str, list[str]]:
    """Replace math spans with placeholders so prose cleanup cannot destroy them."""

    protected: list[str] = []

    def keep(chunk: str) -> str:
        # Preserve colours inside math for KaTeX (map custom names → #hex).
        for _ in range(8):
            nxt = _replace_two_brace_args(
                chunk,
                "textcolor",
                lambda color, body, cmap=color_map: _math_textcolor(color, body, cmap),
            )
            if nxt == chunk:
                break
            chunk = nxt

        def color_cmd(match: re.Match[str]) -> str:
            kind, value = _resolve_color(match.group(1), color_map)
            return rf"\color{{{value if kind == 'hex' else value}}}"

        chunk = re.sub(r"\\color\{([^{}]+)\}", color_cmd, chunk)
        for cmd in (
            "footnotesize",
            "scriptsize",
            "tiny",
            "large",
            "Large",
            "huge",
            "Huge",
        ):
            chunk = re.sub(rf"\\{cmd}\b", "", chunk)
        protected.append(chunk)
        return f"@@ETOZ_MATH_{len(protected) - 1}@@"

    text = re.sub(
        r"\$\$(.+?)\$\$",
        lambda match: keep(f"$${match.group(1)}$$"),
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)",
        lambda match: keep(f"${match.group(1)}$"),
        text,
        flags=re.DOTALL,
    )
    return text, protected


def _restore_math(text: str, protected: list[str]) -> str:
    for index, value in enumerate(protected):
        text = text.replace(f"@@ETOZ_MATH_{index}@@", value)
    return text


def _convert_env_blocks(text: str, env: str, fence_lang: str | None) -> str:
    pattern = re.compile(
        r"\\begin\{" + re.escape(env) + r"\}(.*?)\\end\{" + re.escape(env) + r"\}",
        re.DOTALL | re.IGNORECASE,
    )

    def repl(match: re.Match[str]) -> str:
        inner = match.group(1).strip("\n")
        if fence_lang is None:
            return inner
        return f"\n```{fence_lang}\n{inner}\n```\n"

    return pattern.sub(repl, text)


def _convert_lists(text: str) -> str:
    """Convert itemize/enumerate, including optional ``[nosep]`` / ``[label=...]``."""

    for env, ordered in (("itemize", False), ("enumerate", True)):
        pattern = re.compile(
            r"\\begin\{"
            + re.escape(env)
            + r"\}(?:\[[^\]]*\])?(.*?)\\end\{"
            + re.escape(env)
            + r"\}",
            re.DOTALL | re.IGNORECASE,
        )

        def repl(match: re.Match[str], *, ordered: bool = ordered) -> str:
            inner = match.group(1)
            items = re.split(r"\\item\b", inner)
            lines: list[str] = []
            number = 1
            for item in items:
                content = item.strip()
                if not content:
                    continue
                content = re.sub(r"^\[[^\]]*\]\s*", "", content)
                if "@@ETOZ_MATH_" in content or "$$" in content:
                    content = re.sub(r"[ \t]+", " ", content)
                    content = re.sub(r"\n{3,}", "\n\n", content).strip()
                else:
                    content = re.sub(r"\s+", " ", content)
                if ordered:
                    lines.append(f"{number}. {content}")
                    number += 1
                else:
                    lines.append(f"- {content}")
            return "\n\n" + "\n\n".join(lines) + "\n\n"

        for _ in range(4):
            nxt = pattern.sub(repl, text)
            if nxt == text:
                break
            text = nxt
    return text


def _convert_tabular(text: str) -> str:
    pattern = re.compile(
        r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}",
        re.DOTALL | re.IGNORECASE,
    )

    def repl(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        inner = inner.replace("\\hline", "")
        rows = [row.strip() for row in re.split(r"\\\\", inner) if row.strip()]
        md_rows: list[str] = []
        for index, row in enumerate(rows):
            cells = [cell.strip() for cell in row.split("&")]
            md_rows.append("| " + " | ".join(cells) + " |")
            if index == 0:
                md_rows.append("| " + " | ".join("---" for _ in cells) + " |")
        return "\n" + "\n".join(md_rows) + "\n"

    return pattern.sub(repl, text)


def _replace_includegraphics(text: str) -> str:
    pattern = re.compile(
        r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}",
        flags=re.IGNORECASE,
    )

    def repl(match: re.Match[str]) -> str:
        return f"@@ETOZ_IMAGE:{match.group(1).strip()}@@"

    return pattern.sub(repl, text)


def _replace_media_commands(text: str) -> str:
    text = _replace_two_brace_args(
        text,
        "href",
        lambda url, label: f"[{label.strip()}]({url.strip()})",
    )
    text = _replace_command(text, "url", "[{inner}]({inner})")
    text = _replace_includegraphics(text)
    return text


def _apply_prose_colors(text: str, color_map: dict[str, str]) -> str:
    for _ in range(8):
        nxt = _replace_two_brace_args(
            text,
            "textcolor",
            lambda color, body, cmap=color_map: _prose_color_span(color, body, cmap),
        )
        if nxt == text:
            break
        text = nxt
    for _ in range(8):
        nxt = _replace_two_brace_args(
            text,
            "colorbox",
            lambda color, body, cmap=color_map: _prose_bg_span(color, body, cmap),
        )
        if nxt == text:
            break
        text = nxt

    # \fcolorbox{frame}{bg}{text} — keep background highlight.
    needle = r"\\fcolorbox\{"
    while True:
        match = re.search(needle, text)
        if not match:
            break
        frame = _read_braced(text, match.end() - 1)
        if frame is None:
            break
        _frame_color, after_frame = frame
        bg = _read_braced(text, after_frame)
        if bg is None:
            break
        bg_color, after_bg = bg
        body = _read_braced(text, after_bg)
        if body is None:
            break
        content, after_body = body
        replacement = _prose_bg_span(bg_color, content, color_map)
        text = text[: match.start()] + replacement + text[after_body:]

    # Lone \color{name} in prose → drop (stream of colour not practical in MD).
    text = re.sub(r"\\color\{[^{}]+\}", "", text)
    return text


def _cleanup_tex_prose(chunk: str) -> str:
    """Strip leftover TeX from non-math prose (math already stashed)."""

    protected: list[str] = []

    def stash(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"@@ETOZ_KEEP_{len(protected) - 1}@@"

    # Protect multi-line / structured markers before generic @@…@@ matching.
    chunk = re.sub(r"@@ETOZ_TIKZ@@.*?@@ETOZ_TIKZ_END@@", stash, chunk, flags=re.DOTALL)
    chunk = re.sub(r"@@ETOZ_FG:[^|]+\|(?:(?!@@).)*?@@", stash, chunk, flags=re.DOTALL)
    chunk = re.sub(r"@@ETOZ_BG:[^|]+\|(?:(?!@@).)*?@@", stash, chunk, flags=re.DOTALL)
    chunk = re.sub(r"@@ETOZ_BOX:[^@]+@@", stash, chunk)
    chunk = re.sub(r"@@ETOZ_BOX_END@@", stash, chunk)
    chunk = re.sub(r"@@ETOZ_IMAGE:[^@]+@@", stash, chunk)
    chunk = re.sub(r"@@ETOZ_MATH_\d+@@", stash, chunk)
    # Streamlit colour directives :red[…] / :blue-background[…]
    chunk = re.sub(
        r":[a-zA-Z-]+?\[[^\]]*\]",
        stash,
        chunk,
    )

    chunk = chunk.replace("\\%", "%")
    chunk = chunk.replace("\\&", "&")
    chunk = chunk.replace("\\_", "_")
    chunk = chunk.replace("\\{", "{")
    chunk = chunk.replace("\\}", "}")
    chunk = chunk.replace("~", " ")
    chunk = chunk.replace("\\,", " ")
    chunk = chunk.replace("\\;", " ")
    chunk = chunk.replace("\\!", "")
    chunk = chunk.replace("\\quad", " ")
    chunk = chunk.replace("\\qquad", " ")
    chunk = chunk.replace("\\\\", "\n")

    for command in (
        "textbf",
        "textit",
        "emph",
        "texttt",
        "underline",
        "textrm",
        "textsf",
        "paragraph",
        "subparagraph",
    ):
        chunk = _replace_command(chunk, command, "{inner}")

    chunk = re.sub(r"\\hspace\{[^}]*\}", " ", chunk)
    chunk = re.sub(r"\\vspace\{[^}]*\}", "\n", chunk)
    chunk = re.sub(r"\\label\{[^}]*\}", "", chunk)
    chunk = re.sub(r"\\ref\{[^}]*\}", "", chunk)
    chunk = re.sub(r"\\cite\{[^}]*\}", "", chunk)
    chunk = re.sub(r"\\setcounter\{[^}]*\}\{[^}]*\}", "", chunk)
    chunk = re.sub(r"\\vfill\b", "\n", chunk)
    chunk = re.sub(
        r"\\(?:hfill|bigskip|medskip|smallskip|noindent|centering|raggedright|"
        r"raggedleft|bfseries|itshape|ttfamily|rmfamily|sffamily|"
        r"footnotesize|scriptsize|tiny|small|normalsize|large|Large|LARGE|"
        r"huge|Huge|maketitle|tableofcontents|newpage|clearpage|linebreak|"
        r"usetikzlibrary|tikzstyle|definecolor)\b",
        "",
        chunk,
    )
    chunk = re.sub(
        r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?",
        lambda match: match.group(1) if match.lastindex else "",
        chunk,
    )
    chunk = re.sub(
        r"\[(?:nosep|itemsep=[^\]]*|label=[^\]]*)\]",
        "",
        chunk,
        flags=re.IGNORECASE,
    )

    for index, value in enumerate(protected):
        chunk = chunk.replace(f"@@ETOZ_KEEP_{index}@@", value)
    return chunk


def latex_to_markdown(text: str) -> str:
    """Best-effort educational LaTeX → Markdown + KaTeX math + render markers."""

    color_map = _parse_definecolors(text)
    body, title, author = _extract_document_body(text)
    parts: list[str] = []
    if title:
        parts.append(f"# {title}")
    if author:
        parts.append(f"*{author}*")
    if parts:
        parts.append("")

    body = re.sub(r"\\maketitle\b", "", body)
    body = re.sub(r"\\tableofcontents\b", "", body)
    body = re.sub(r"\\newpage\b", "\n\n---\n\n", body)
    body = re.sub(r"\\clearpage\b", "\n\n---\n\n", body)
    body = re.sub(r"\\setcounter\{[^}]*\}\{[^}]*\}", "", body)
    body = re.sub(r"\\definecolor\{[^{}]+\}\{[^{}]+\}\{[^{}]*\}", "", body)
    body = re.sub(r"\\usetikzlibrary\{[^{}]*\}", "", body)

    # TikZ first (opaque), then callout boxes, then layout unwraps.
    body = _extract_tikz(body)
    body = _convert_callout_boxes(body)
    body = _unwrap_layout_envs(body)

    body = _convert_env_blocks(body, "lstlisting", "java")
    body = _convert_env_blocks(body, "verbatim", "")
    body = _convert_tabular(body)

    # Math first so prose colour conversion cannot rewrite math textcolor.
    body = _normalize_math_delimiters(body)
    body, math_blocks = _stash_math(body, color_map)

    # Prose colours → Streamlit directives / colour markers.
    body = _apply_prose_colors(body, color_map)

    body = _convert_lists(body)
    body = _replace_media_commands(body)

    for command, level in (
        ("section*", "## "),
        ("section", "## "),
        ("subsection*", "### "),
        ("subsection", "### "),
        ("subsubsection*", "#### "),
        ("subsubsection", "#### "),
        ("paragraph", "##### "),
        ("subparagraph", "###### "),
    ):
        body = _replace_command(body, command, level + "{inner}\n\n")

    for command, wrapper in (
        ("textbf", "**{inner}**"),
        ("textit", "*{inner}*"),
        ("emph", "*{inner}*"),
        ("texttt", "`{inner}`"),
        ("underline", "{inner}"),
    ):
        body = _replace_command(body, command, wrapper)

    pieces = re.split(r"(```.*?```)", body, flags=re.DOTALL)
    cleaned: list[str] = []
    for index, piece in enumerate(pieces):
        if index % 2 == 1 and piece.startswith("```"):
            cleaned.append(piece)
        else:
            cleaned.append(_cleanup_tex_prose(piece))
    body = "".join(cleaned)
    body = _restore_math(body, math_blocks)

    body = re.sub(r"\n{3,}", "\n\n", body)
    body = body.strip()
    parts.append(body)
    return "\n".join(parts).strip()


def prepare_lecture_markdown(text: str) -> str:
    """Return Markdown/KaTeX suitable for Streamlit rendering.

    Any TeX-looking source is compiled first so students never see raw
    ``\\command`` markup in the page.
    """

    raw = (text or "").strip()
    if not raw:
        return ""
    if looks_like_latex(raw) or "\\" in raw:
        return latex_to_markdown(raw)
    light = _normalize_math_delimiters(raw)
    return _replace_media_commands(light)


def escape_html(value: str) -> str:
    """Public helper for renderers."""

    return html.escape(value or "", quote=True)
