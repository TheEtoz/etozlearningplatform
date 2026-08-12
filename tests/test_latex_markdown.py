"""LaTeX → Markdown/KaTeX conversion for lectures."""

from frontend.utils.latex_markdown import latex_to_markdown, prepare_lecture_markdown


def test_href_and_url_become_markdown_links() -> None:
    source = r"""
\documentclass{article}
\begin{document}
\section{Links}
See \href{https://example.com/docs}{the docs} and \url{https://example.com}.
\end{document}
"""
    out = latex_to_markdown(source)
    assert "[the docs](https://example.com/docs)" in out
    assert "[https://example.com](https://example.com)" in out


def test_includegraphics_becomes_image_marker() -> None:
    source = r"""
\documentclass{article}
\begin{document}
\includegraphics{https://cdn.example.com/a.png}
\href{http://127.0.0.1:8000/media/sheet.pdf}{Worksheet}
\end{document}
"""
    out = latex_to_markdown(source)
    assert "@@ETOZ_IMAGE:https://cdn.example.com/a.png@@" in out
    assert "[Worksheet](http://127.0.0.1:8000/media/sheet.pdf)" in out


def test_display_math_and_pmatrix_preserved_for_katex() -> None:
    source = r"""
\documentclass{article}
\begin{document}
\subsection{Example}
\[
A+2B = \begin{pmatrix} 3 & 3 & 0 \\ 8 & 0 & -7 \end{pmatrix}
\]
Also $m \times n$ and $A^T$.
\end{document}
"""
    out = prepare_lecture_markdown(source)
    assert r"\begin{pmatrix}" in out
    assert r"\end{pmatrix}" in out
    assert "3 & 3 & 0" in out
    assert r"\times" in out
    assert "$$" in out
    assert "8 & 0 & -7" in out


def test_enumerate_options_and_keypoints_box() -> None:
    source = r"""
\documentclass{article}
\begin{document}
\begin{keypoints}
\textbf{Key points}
\begin{itemize}[nosep]
\item Addition requires matching shapes.
\item A scalar multiplies every entry.
\end{itemize}
\end{keypoints}
\begin{enumerate}[nosep]
\item First practice question.
\item Second practice question.
\end{enumerate}
\end{document}
"""
    out = prepare_lecture_markdown(source)
    assert "@@ETOZ_BOX:keypoints|Key points@@" in out
    assert "@@ETOZ_BOX_END@@" in out
    assert "Addition requires matching shapes" in out
    assert "1. First practice question" in out
    assert "[nosep]" not in out


def test_textcolor_preserved_in_math_with_custom_names() -> None:
    source = r"""
\documentclass{article}
\definecolor{red1}{HTML}{E11D48}
\definecolor{blue1}{HTML}{2563EB}
\begin{document}
\[
\begin{pmatrix} \textcolor{red1}{1} & \textcolor{blue1}{3} \end{pmatrix}
\]
\end{document}
"""
    out = prepare_lecture_markdown(source)
    assert r"\textcolor{#e11d48}{1}" in out
    assert r"\textcolor{#2563eb}{3}" in out
    assert r"\begin{pmatrix}" in out


def test_prose_textcolor_and_colorbox() -> None:
    source = r"""
\documentclass{article}
\begin{document}
\textcolor{red}{Important} and \colorbox{yellow}{highlight}.
\end{document}
"""
    out = prepare_lecture_markdown(source)
    assert ":red[Important]" in out
    assert ":yellow-background[highlight]" in out


def test_tikzpicture_becomes_marker() -> None:
    source = r"""
\documentclass{article}
\begin{document}
\begin{tikzpicture}
\draw (0,0) -- (1,1);
\end{tikzpicture}
\end{document}
"""
    out = prepare_lecture_markdown(source)
    assert "@@ETOZ_TIKZ@@" in out
    assert r"\begin{tikzpicture}" in out
    assert r"\draw (0,0) -- (1,1);" in out
    assert "@@ETOZ_TIKZ_END@@" in out


def test_note_and_warning_boxes() -> None:
    source = r"""
\begin{note}
Remember the order of operations.
\end{note}
\begin{warning}
Do not divide by zero.
\end{warning}
"""
    out = prepare_lecture_markdown(source)
    assert "@@ETOZ_BOX:note|Note@@" in out
    assert "@@ETOZ_BOX:warning|Warning@@" in out
    assert "Do not divide by zero" in out
