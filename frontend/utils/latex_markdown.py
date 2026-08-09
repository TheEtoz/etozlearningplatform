"""Convert educational LaTeX lecture notes into Markdown + KaTeX for Streamlit.

Streamlit renders ``$...$`` / ``$$...$$`` with KaTeX, so math environments
(pmatrix, vmatrix, array, cases, frac, …) are preserved inside math delimiters.
Unsupported packages (tcolorbox colours, rotate, custom RGB colour names) are
unwrapped to plain readable content rather than compiled like pdfLaTeX.
"""

from __future__ import annotations

import re


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


def _replace_two_brace_args(text: str, command: str, formatter) -> str:
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
    # Drop nested style macros from titles: \textbf{\Huge Foo} -> Foo
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


def _unwrap_custom_boxes(text: str) -> str:
    """Drop tcolorbox / custom lecture boxes; keep the prose inside."""

    for env in (
        "formula",
        "keypoints",
        "note",
        "tcolorbox",
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

    # Display math \[ ... \]
    text = re.sub(r"\\\[(.*?)\\\]", r"\n\n$$\1$$\n\n", text, flags=re.DOTALL)
    # Inline math \( ... \)
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text, flags=re.DOTALL)
    return text


def _stash_math(text: str) -> tuple[str, list[str]]:
    """Replace math spans with placeholders so prose cleanup cannot destroy them."""

    protected: list[str] = []

    def keep(chunk: str) -> str:
        # Inside math: drop lecture colour wrappers; keep KaTeX-friendly structure.
        chunk = _replace_two_brace_args(chunk, "textcolor", lambda _c, body: body)
        chunk = re.sub(r"\\color\{[^{}]+\}", "", chunk)
        # Common size/style macros KaTeX may not need.
        for cmd in ("footnotesize", "scriptsize", "tiny", "large", "Large", "huge", "Huge"):
            chunk = re.sub(rf"\\{cmd}\b", "", chunk)
        protected.append(chunk)
        return f"@@ETOZ_MATH_{len(protected) - 1}@@"

    # Display math first (greedy-safe non-greedy blocks).
    text = re.sub(
        r"\$\$(.+?)\$\$",
        lambda match: keep(f"$${match.group(1)}$$"),
        text,
        flags=re.DOTALL,
    )
    # Inline math — avoid matching $$ leftovers.
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
                # Drop a leading optional label remnant like [label=...]
                content = re.sub(r"^\[[^\]]*\]\s*", "", content)
                # Keep math placeholders / line breaks; only flatten soft spaces.
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

        # Nested lists: run multiple passes.
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


def _cleanup_tex_prose(chunk: str) -> str:
    """Strip leftover TeX from non-math prose (math already stashed)."""

    protected: list[str] = []

    def stash(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"@@ETOZ_KEEP_{len(protected) - 1}@@"

    chunk = re.sub(r"@@ETOZ_(?:MATH|IMAGE|KEEP)_[^@]+@@", stash, chunk)
    chunk = re.sub(r"@@ETOZ_IMAGE:[^@]+@@", stash, chunk)

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

    # One-arg style / layout macros → keep inner text.
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
        r"huge|Huge|maketitle|tableofcontents|newpage|clearpage|linebreak)\b",
        "",
        chunk,
    )
    # Drop remaining unknown commands but keep braced arguments' text when simple.
    chunk = re.sub(
        r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?",
        lambda match: match.group(1) if match.lastindex else "",
        chunk,
    )
    # Leftover enumitem-style options only (do not touch Markdown [links](url)).
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
    """Best-effort educational LaTeX → Markdown + KaTeX math."""

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

    # Custom boxes / rotate wrappers → keep inner content.
    body = _unwrap_custom_boxes(body)

    # Colours are lecture-PDF only; keep the numbers/words.
    for _ in range(8):
        nxt = _replace_two_brace_args(body, "textcolor", lambda _c, content: content)
        if nxt == body:
            break
        body = nxt
    body = re.sub(r"\\color\{[^{}]+\}", "", body)

    # Code / verbatim first.
    body = _convert_env_blocks(body, "lstlisting", "java")
    body = _convert_env_blocks(body, "verbatim", "")
    body = _convert_tabular(body)

    # Math delimiters → KaTeX, then stash so list/prose cleanup cannot break matrices.
    body = _normalize_math_delimiters(body)
    body, math_blocks = _stash_math(body)

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
    # Convert whenever backslashes appear — not only full documents.
    if looks_like_latex(raw) or "\\" in raw:
        return latex_to_markdown(raw)
    light = _normalize_math_delimiters(raw)
    return _replace_media_commands(light)
