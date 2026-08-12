"""TikZ document prep / compile helpers."""

from frontend.utils.tikz_render import (
    build_tikz_document,
    compile_tikz_png,
    compile_tikz_svg,
)


SAMPLE = r"""
\begin{tikzpicture}[scale=1.15]
\draw[-{Latex}] (-2.2,0) -- (2.2,0) node[right] {$x$};
\draw[-{Latex}] (0,-1.4) -- (0,2.2) node[above] {$y$};
\draw[teal1,thick] (0,0) circle (1.6);
\draw[-{Latex},red1,very thick] (0,0) -- (120:1.6);
\draw[orange1,thick,domain=0:120] plot ({0.5*cos(\x)},{0.5*sin(\x)});
\node[orange1] at (60:0.75) {$120^\circ$};
\draw[blue1,dashed] (0,0) -- (-1.6,0);
\draw[blue1,thick,domain=180:120] plot ({0.35*cos(\x)},{0.35*sin(\x)});
\node[blue1] at (150:0.55) {$60^\circ$};
\node at (120:1.85) {$\left(\tfrac{2\pi}{3}\text{ rad}\right)$};
\end{tikzpicture}
\end{center}
"""


def test_build_document_injects_colors_and_libraries() -> None:
    doc = build_tikz_document(SAMPLE)
    assert r"\usetikzlibrary{arrows.meta" in doc
    assert r"\definecolor{teal1}{HTML}{0D9488}" in doc
    assert r"\definecolor{red1}{HTML}{E11D48}" in doc
    assert r"node[right] {$x$}" in doc
    assert r"\end{center}" not in doc


def test_compile_user_unit_circle_png() -> None:
    png = compile_tikz_png(SAMPLE)
    assert png is not None
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_compile_user_unit_circle_svg() -> None:
    svg = compile_tikz_svg(SAMPLE)
    assert svg is not None
    assert b"<svg" in svg.lower() or svg.lstrip().startswith(b"<?xml")
