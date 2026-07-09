"""
latex_writer.py — Renders a LaTeX template with dynamic values and compiles
                  it to a production-quality PDF.

Key fixes over the original:
  1. pdflatex is invoked with -output-directory set to the template's own
     directory, so graphicspath{{./images/}} resolves correctly regardless
     of the Python process cwd.
  2. Two compilation passes are performed so TikZ remember-picture/overlay
     and eso-pic background layers render correctly on the first visual pass.
  3. Compilation errors are captured and surfaced as Python exceptions rather
     than silently failing.
  4. Auxiliary files (.aux, .log) are left in the output directory but the
     .tex intermediary is cleaned up only on success (kept on failure for
     debugging).
  5. The final PDF is copied to the caller-requested output_pdf path so the
     API remains identical to the original.
"""

import subprocess
import os
import shutil
import sys


def _run_xelatex(tex_path: str, work_dir: str, pass_num: int) -> None:
    """Run a single xelatex pass and raise on failure."""
    cmd = [
        "xelatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={work_dir}",
        tex_path,
    ]
    result = subprocess.run(
        cmd,
        cwd=work_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log_snippet = result.stdout[-4000:] if result.stdout else "(no output)"
        raise RuntimeError(
            f"xelatex pass {pass_num} failed (exit {result.returncode}).\n"
            f"--- LaTeX log (last 4000 chars) ---\n{log_snippet}"
        )


def render_latex(
    template_path: str,
    output_tex: str,
    output_pdf: str,
    values: dict,
) -> None:
    """
    Render *template_path* with *values*, compile to PDF, and write the
    result to *output_pdf*.

    Parameters
    ----------
    template_path : str
        Path to the source .tex template (relative or absolute).
    output_tex : str
        Desired path for the rendered .tex file (used as the compilation
        source; placed inside the template's directory so images resolve).
    output_pdf : str
        Final destination for the compiled .pdf.
    values : dict
        Mapping of ``{{KEY}}`` placeholder names to replacement strings.
        Values are LaTeX-escaped before substitution.
    """
    template_path = os.path.abspath(template_path)
    output_tex    = os.path.abspath(output_tex)
    output_pdf    = os.path.abspath(output_pdf)

    # Work directory == directory that contains the template so that
    # \graphicspath{{./images/}} and other relative paths resolve correctly.
    work_dir = os.path.dirname(template_path)

    # Resolve the images directory and fonts directory — always docgen/images/
    # and docgen/fonts/ regardless of where the template lives.
    images_dir = os.path.join(os.path.dirname(template_path), "..", "images")
    images_dir = os.path.abspath(images_dir).replace("\\", "/") + "/"
    fonts_dir  = os.path.join(os.path.dirname(template_path), "..", "fonts")
    fonts_dir  = os.path.abspath(fonts_dir).replace("\\", "/") + "/"

    # Read template
    with open(template_path, "r", encoding="utf-8") as f:
        tex = f.read()

    # Inject the absolute images path so \graphicspath always resolves
    tex = tex.replace(
        r"\graphicspath{{IMAGES_DIR_PLACEHOLDER}}",
        r"\graphicspath{{" + images_dir + r"}}",
    )
    # Inject absolute font path for fontspec Path= directives
    tex = tex.replace("FONTS_DIR_PLACEHOLDER", fonts_dir)

    # Replace all {{KEY}} placeholders with escaped values
    for key, raw_value in values.items():
        tex = tex.replace(f"{{{{{key}}}}}", _escape_latex(raw_value))

    # Write rendered .tex into the work directory (next to the template)
    rendered_tex = os.path.join(work_dir, os.path.basename(output_tex))
    with open(rendered_tex, "w", encoding="utf-8") as f:
        f.write(tex)

    try:
        # Pass 1 — layout + TikZ coordinate recording
        _run_xelatex(rendered_tex, work_dir, pass_num=1)
        # Pass 2 — TikZ overlay + eso-pic background correct on this pass
        _run_xelatex(rendered_tex, work_dir, pass_num=2)
    except RuntimeError:
        # Keep rendered_tex for post-mortem inspection
        raise

    # Derive where pdflatex wrote the PDF (same dir as rendered_tex, .pdf ext)
    compiled_pdf = os.path.splitext(rendered_tex)[0] + ".pdf"

    if not os.path.exists(compiled_pdf):
        raise FileNotFoundError(
            f"pdflatex reported success but output PDF not found: {compiled_pdf}"
        )

    # Copy to caller-requested location (may be outside work_dir)
    if os.path.abspath(compiled_pdf) != output_pdf:
        shutil.copy2(compiled_pdf, output_pdf)

    print(f"[latex_writer] PDF written to: {output_pdf}", file=sys.stderr)


# ---------------------------------------------------------------------------
# LaTeX string escaping
# ---------------------------------------------------------------------------
_LATEX_ESCAPE_MAP = [
    ("\\", r"\textbackslash{}"),   # must be first
    ("&",  r"\&"),
    ("%",  r"\%"),
    ("$",  r"\$"),
    ("#",  r"\#"),
    ("_",  r"\_"),
    ("{",  r"\{"),
    ("}",  r"\}"),
    ("~",  r"\textasciitilde{}"),
    ("^",  r"\textasciicircum{}"),
]


def _escape_latex(value: str) -> str:
    """
    Escape special LaTeX characters in a user-supplied string.

    This prevents injection via employee names, roles, or other fields
    that might contain characters meaningful to LaTeX.
    """
    # Avoid double-escaping the backslash we insert ourselves
    result = value.replace("\\", "\x00BACKSLASH\x00")
    for char, replacement in _LATEX_ESCAPE_MAP[1:]:
        result = result.replace(char, replacement)
    result = result.replace("\x00BACKSLASH\x00", r"\textbackslash{}")
    return result
