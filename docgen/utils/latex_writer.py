# coding: utf-8
"""
latex_writer.py — Renders a LaTeX template with dynamic values and compiles
                  it to a production-quality PDF using XeLaTeX.

Pipeline:
  1. Read template .tex source.
  2. Inject absolute paths (FONTS / IMAGES / LAYOUTS placeholders).
  3. Render brand_preamble_rendered.tex into the work directory.
  4. If a custom preamble_path is provided (Branding Engine):
       - Strip the template's own preamble block.
       - Replace it with the custom brand preamble (fonts/images injected).
       - Substitute T2L asset filenames in the body with profile PNGs.
  5. LaTeX-escape all {{FIELD}} values and substitute them.
  6. Clear residual unfilled optional {{FIELD}} tokens.
  7. Write rendered .tex into the template work directory.
  8. Run XeLaTeX passes 1 and 2 (TikZ needs two passes).
  9. Copy compiled PDF to caller-requested output_pdf path.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# XeLaTeX runner
# ---------------------------------------------------------------------------

def _run_xelatex(tex_path: str, work_dir: str, pass_num: int) -> None:
    """Run a single XeLaTeX pass and raise RuntimeError on failure."""
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
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        log_snippet = result.stdout[-4000:] if result.stdout else "(no output)"
        raise RuntimeError(
            f"xelatex pass {pass_num} failed (exit {result.returncode}).\n"
            f"--- LaTeX log (last 4000 chars) ---\n{log_snippet}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_latex(
    template_path: str,
    output_tex: str,
    output_pdf: str,
    values: dict,
    preamble_path: str | None = None,
) -> None:
    """
    Render *template_path* with *values*, compile to PDF, and write the
    result to *output_pdf*.

    Parameters
    ----------
    template_path : str
        Path to the source .tex template (relative or absolute).
    output_tex : str
        Desired path for the rendered .tex file (compilation source).
        The file is always placed in the template directory regardless
        of this path's directory component — the basename is used.
    output_pdf : str
        Final destination for the compiled .pdf.
    values : dict
        Mapping of ``{{KEY}}`` placeholder names to replacement strings.
        Values are LaTeX-escaped before substitution (except CP_* keys
        which get lighter treatment to preserve special LaTeX tokens).
    preamble_path : str | None
        Optional absolute path to a custom brand preamble .tex file
        (supplied by the Branding Engine).  When provided the template's
        built-in preamble is swapped out for the custom one.
        When None, existing T2L branding behaviour is preserved.
    """
    template_path = os.path.abspath(template_path)
    output_tex    = os.path.abspath(output_tex)
    output_pdf    = os.path.abspath(output_pdf)

    # Work directory = template directory so \graphicspath and \input resolve
    work_dir = os.path.dirname(template_path)

    # Compute absolute paths for all resource directories
    _base = os.path.dirname(template_path)   # docgen/templates/
    images_dir  = os.path.normpath(os.path.join(_base, "..", "images")).replace("\\", "/") + "/"
    fonts_dir   = os.path.normpath(os.path.join(_base, "..", "fonts")).replace("\\", "/") + "/"
    layouts_dir = os.path.normpath(os.path.join(_base, "..", "layouts")).replace("\\", "/") + "/"

    # ── 1. Read template ─────────────────────────────────────────────────────
    with open(template_path, "r", encoding="utf-8") as fh:
        tex = fh.read()

    # ── 2. Inject absolute resource paths ────────────────────────────────────
    tex = tex.replace(r"\graphicspath{{IMAGES_DIR_PLACEHOLDER}}",
                      r"\graphicspath{{" + images_dir + r"}}")
    tex = tex.replace("FONTS_DIR_PLACEHOLDER",   fonts_dir)
    tex = tex.replace("LAYOUTS_DIR_PLACEHOLDER", layouts_dir)

    # ── 3. Render brand_preamble into work_dir (Turn2Law default mode) ───────
    _t2l_preamble_src = os.path.join(layouts_dir.rstrip("/"), "brand_preamble.tex")
    if os.path.exists(_t2l_preamble_src):
        with open(_t2l_preamble_src, "r", encoding="utf-8") as fh:
            _preamble_raw = fh.read()
        _preamble_rendered = (
            _preamble_raw
            .replace("FONTS_DIR_PLACEHOLDER",  fonts_dir)
            .replace("IMAGES_DIR_PLACEHOLDER", images_dir)
        )
        # Write into the work directory (next to the template)
        _rendered_path = os.path.join(work_dir, "brand_preamble_rendered.tex")
        with open(_rendered_path, "w", encoding="utf-8") as fh:
            fh.write(_preamble_rendered)
        # Redirect the template's \input to the rendered copy
        tex = tex.replace(
            r"\input{" + layouts_dir + r"brand_preamble}",
            r"\input{" + layouts_dir + r"brand_preamble_rendered}",
        )

    # ── 4. Custom preamble swap (Branding Engine) ─────────────────────────────
    if preamble_path is not None:
        _custom_abs  = os.path.abspath(preamble_path)
        _profile_dir = os.path.dirname(_custom_abs).replace("\\", "/") + "/"

        # Read and inject paths into the custom preamble
        with open(_custom_abs, "r", encoding="utf-8") as fh:
            _cp_tex = fh.read()
        _cp_tex = (
            _cp_tex
            .replace("FONTS_DIR_PLACEHOLDER",  fonts_dir)
            .replace("IMAGES_DIR_PLACEHOLDER", images_dir)
        )

        # Map T2L asset names → processed PNGs in the profile directory
        _asset_map: dict[str, str] = {
            "header_decoration":      _profile_dir + "header.png",
            "footer_decoration":      _profile_dir + "footer.png",
            "sample_asset_0_xref_36": _profile_dir + "logo.png"
                                      if os.path.isfile(_profile_dir + "logo.png")
                                      else _profile_dir + "watermark.png",
            "watermark_logo_n":       _profile_dir + "watermark.png",
            "footer_icon_xref47":     _profile_dir + "logo.png",
            "sample_asset_1_xref_47": _profile_dir + "logo.png",
            "sample_asset_2_xref_36": _profile_dir + "watermark.png",
            "sample_asset_3_xref_63": _profile_dir + "logo.png",
        }

        # Split at \begin{document}
        _parts = tex.split(r"\begin{document}", 1)
        if len(_parts) == 2:
            _body = r"\begin{document}" + _parts[1]

            # Substitute or blank out each T2L asset reference
            for _name, _dest in _asset_map.items():
                _pat_inc = (
                    r"\\includegraphics(?:\[[^\]]*\])?\s*\{"
                    + re.escape(_name)
                    + r"(?:\.[a-zA-Z]+)?\}"
                )
                if os.path.isfile(_dest):
                    _body = re.sub(
                        _pat_inc,
                        lambda m, d=_dest: m.group(0).rsplit("{", 1)[0] + "{" + d + "}",
                        _body,
                        flags=re.DOTALL,
                    )
                else:
                    _body = re.sub(_pat_inc, r"\\mbox{}", _body, flags=re.DOTALL)

            # Extract the \documentclass line
            _dc_match = re.match(r"(\s*\\documentclass[^\n]*\n)", tex)
            _dc = _dc_match.group(1) if _dc_match else "\\documentclass[10pt]{article}\n"

            tex = _dc + "\n" + _cp_tex + "\n" + _body

    # ── 5. Substitute {{FIELD}} tokens ───────────────────────────────────────
    # CP_Signature_Image: raw filename, no escaping at all
    _NO_ESCAPE = {"CP_Signature_Image"}

    # CP_* text fields: only escape & → \& (names, titles, addresses)
    _AMP_ONLY = {
        "CP_Company_Name", "CP_Signatory_Name", "CP_Designation",
        "CP_Company_Address", "CP_Company_Email", "CP_Company_Phone",
        "CP_Company_Website", "CP_Title_Suffix",
    }

    for key, raw_value in values.items():
        placeholder = "{{" + key + "}}"
        if key in _NO_ESCAPE:
            tex = tex.replace(placeholder, str(raw_value))
        elif key in _AMP_ONLY:
            tex = tex.replace(placeholder, str(raw_value).replace("&", r"\&"))
        else:
            tex = tex.replace(placeholder, _escape_latex(str(raw_value)))

    # ── 6. Clear residual unfilled optional tokens ───────────────────────────
    tex = re.sub(r"\{\{[A-Za-z_]+\}\}", "", tex)

    # ── 7. Write rendered .tex into work directory ───────────────────────────
    rendered_tex = os.path.join(work_dir, os.path.basename(output_tex))
    with open(rendered_tex, "w", encoding="utf-8") as fh:
        fh.write(tex)

    # ── 8. Compile (2 passes for TikZ overlays) ──────────────────────────────
    try:
        _run_xelatex(rendered_tex, work_dir, pass_num=1)
        _run_xelatex(rendered_tex, work_dir, pass_num=2)
    except RuntimeError:
        # Keep rendered_tex for post-mortem debugging
        raise

    # ── 9. Copy compiled PDF to caller-requested destination ─────────────────
    compiled_pdf = os.path.splitext(rendered_tex)[0] + ".pdf"
    if not os.path.exists(compiled_pdf):
        raise FileNotFoundError(
            f"XeLaTeX reported success but output PDF not found: {compiled_pdf}"
        )

    output_pdf_dir = os.path.dirname(output_pdf)
    if output_pdf_dir:
        os.makedirs(output_pdf_dir, exist_ok=True)

    if os.path.abspath(compiled_pdf) != os.path.abspath(output_pdf):
        shutil.copy2(compiled_pdf, output_pdf)

    logger.info("PDF written to: %s", output_pdf)


# ---------------------------------------------------------------------------
# LaTeX string escaping
# ---------------------------------------------------------------------------

def _escape_latex(value: str) -> str:
    """
    Escape special LaTeX characters in a user-supplied string.

    Processes character-by-character to prevent double-escaping.
    """
    result: list[str] = []
    for ch in value:
        if   ch == '\\': result.append(r'\textbackslash{}')
        elif ch == '&':  result.append(r'\&')
        elif ch == '%':  result.append(r'\%')
        elif ch == '$':  result.append(r'\$')
        elif ch == '#':  result.append(r'\#')
        elif ch == '_':  result.append(r'\_')
        elif ch == '{':  result.append(r'\{')
        elif ch == '}':  result.append(r'\}')
        elif ch == '~':  result.append(r'\textasciitilde{}')
        elif ch == '^':  result.append(r'\textasciicircum{}')
        else:            result.append(ch)
    return ''.join(result)
