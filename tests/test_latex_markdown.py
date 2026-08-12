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
\begin{figure}[h]
\begin{tikzpicture}
\draw[->] (-1,0) -- (3,0) node[right] {$x$};
\draw (0,0) -- (1,1);
\end{tikzpicture}
\end{figure}
\end{document}
"""
    out = prepare_lecture_markdown(source)
    assert "@@ETOZ_TIKZ@@" in out
    assert r"\begin{tikzpicture}" in out
    assert r"node[right] {$x$}" in out
    assert r"\draw (0,0) -- (1,1);" in out
    assert "@@ETOZ_TIKZ_END@@" in out
    assert "figure" not in out.lower() or "tikzpicture" in out


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


def test_tabular_optional_row_skip_not_leaked() -> None:
    source = r"""
\begin{tabular}{c|ccccc}
$\theta$ & $0^\circ$ & $30^\circ$ & $45^\circ$ & $60^\circ$ & $90^\circ$ \\
\hline
$\sin\theta$ & $0$ & $\tfrac12$ & $\tfrac{\sqrt2}{2}$ & $\tfrac{\sqrt3}{2}$ & $1$ \\[4pt]
$\cos\theta$ & $1$ & $\tfrac{\sqrt3}{2}$ & $\tfrac{\sqrt2}{2}$ & $\tfrac12$ & $0$ \\[4pt]
$\tan\theta$ & $0$ & $\tfrac{1}{\sqrt3}$ & $1$ & $\sqrt3$ & undefined
\end{tabular}
"""
    out = prepare_lecture_markdown(source)
    assert "[4pt]" not in out
    assert "@@ETOZ_TABLE@@" in out
    assert r"$\sin\theta$" in out
    assert r"$\tfrac12$" in out
    assert out.count("|") > 10


def test_keypoints_keep_inline_math_in_list_items() -> None:
    source = r"""
\begin{keypoints}
\textbf{Key points}
\begin{itemize}[nosep]
\item $180^\circ = \pi$ rad, so degrees $\times\, \pi/180 =$ radians.
\item Coterminal angles: add or subtract $360^\circ$ (or $2\pi$).
\end{itemize}
\end{keypoints}
"""
    out = prepare_lecture_markdown(source)
    assert "@@ETOZ_BOX:keypoints|Key points@@" in out
    assert r"$180^\circ = \pi$" in out
    from frontend.utils.content_render import _callout_body_to_html

    body = out.split("@@ETOZ_BOX:keypoints|Key points@@", 1)[1]
    body = body.split("@@ETOZ_BOX_END@@", 1)[0]
    html_body = _callout_body_to_html(body)
    assert "<ul" in html_body
    assert r"$180^\circ = \pi$" in html_body


def test_keypoints_display_math_stays_together() -> None:
    source = r"""
\begin{keypoints}
\textbf{Key points}
\begin{itemize}
\item Display:
\[
\sin\theta = \frac{a}{b}
\]
\item Inline $\tfrac12$.
\end{itemize}
\end{keypoints}
"""
    out = prepare_lecture_markdown(source)
    body = out.split("@@ETOZ_BOX:keypoints|Key points@@", 1)[1]
    body = body.split("@@ETOZ_BOX_END@@", 1)[0]
    from frontend.utils.content_render import _callout_body_to_html

    html_body = _callout_body_to_html(body)
    assert r"\sin\theta = \frac{a}{b}" in html_body
    assert "$$" in html_body
    # Display math must not be broken into raw TeX paragraphs.
    assert "<p" not in html_body or all(
        r"\sin\theta" not in paragraph
        for paragraph in html_body.split("<p")
    )



