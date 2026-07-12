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
        encoding="utf-8",
        errors="replace",
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
        Desired path for the rendered .tex file (used as the compilation
        source; placed inside the template's directory so images resolve).
    output_pdf : str
        Final destination for the compiled .pdf.
    values : dict
        Mapping of ``{{KEY}}`` placeholder names to replacement strings.
        Values are LaTeX-escaped before substitution.
    preamble_path : str | None
        Optional absolute path to a custom brand preamble .tex file
        (supplied by the Branding Engine).  When provided, the
        ``\\input{...brand_preamble...}`` token in the template is
        replaced with a reference to this file.  When None (default),
        existing behaviour is preserved.
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
    layouts_dir = os.path.join(os.path.dirname(template_path), "..", "layouts")
    layouts_dir = os.path.abspath(layouts_dir).replace("\\", "/") + "/"

    # Read template
    with open(template_path, "r", encoding="utf-8") as f:
        tex = f.read()

    # Inject absolute paths
    tex = tex.replace(
        r"\graphicspath{{IMAGES_DIR_PLACEHOLDER}}",
        r"\graphicspath{{" + images_dir + r"}}",
    )
    tex = tex.replace("FONTS_DIR_PLACEHOLDER", fonts_dir)
    tex = tex.replace("LAYOUTS_DIR_PLACEHOLDER", layouts_dir)

    # Also inject paths into the brand_preamble if it is being compiled
    # as a standalone file (it uses the same placeholders)
    _t2l_preamble_path = os.path.join(layouts_dir.rstrip("/"), "brand_preamble.tex")
    if os.path.exists(_t2l_preamble_path):
        with open(_t2l_preamble_path, "r", encoding="utf-8") as f:
            preamble = f.read()
        rendered_preamble = preamble.replace("FONTS_DIR_PLACEHOLDER", fonts_dir)
        rendered_preamble = rendered_preamble.replace("IMAGES_DIR_PLACEHOLDER", images_dir)
        rendered_preamble_path = os.path.join(
            os.path.dirname(template_path), "..", "layouts", "brand_preamble_rendered.tex"
        )
        rendered_preamble_path = os.path.abspath(rendered_preamble_path)
        with open(rendered_preamble_path, "w", encoding="utf-8") as f:
            f.write(rendered_preamble)
        # Point \input to the rendered version
        tex = tex.replace(
            r"\input{" + layouts_dir + r"brand_preamble}",
            r"\input{" + layouts_dir + r"brand_preamble_rendered}",
        )

    # If a custom preamble_path is supplied by the Branding Engine,
    # the templates embed T2L assets directly in their preamble — there is no
    # \input{brand_preamble} token to replace.  Instead we:
    #   1. Strip the entire LaTeX preamble from the template (everything before
    #      \begin{document}) and replace it with the custom brand preamble.
    #   2. Substitute T2L asset filenames inside \begin{document}...\end{document}
    #      with the profile's processed PNGs if they exist, or blank them out safely.
    if preamble_path is not None:
        import re as _re

        _custom_preamble_abs = os.path.abspath(preamble_path)
        _profile_dir = os.path.dirname(_custom_preamble_abs).replace("\\", "/") + "/"

        # Read and render the custom preamble (inject font/image dir tokens)
        with open(_custom_preamble_abs, "r", encoding="utf-8") as _fh:
            _custom_preamble_tex = _fh.read()
        _custom_preamble_tex = _custom_preamble_tex.replace("FONTS_DIR_PLACEHOLDER", fonts_dir)
        _custom_preamble_tex = _custom_preamble_tex.replace("IMAGES_DIR_PLACEHOLDER", images_dir)

        # Build mapping: T2L asset name → replacement path (or None if missing)
        _asset_map = {
            "header_decoration":    _profile_dir + "header.png",
            "footer_decoration":    _profile_dir + "footer.png",
            "sample_asset_0_xref_36": _profile_dir + "watermark.png",
            "watermark_logo_n":     _profile_dir + "watermark.png",
            "footer_icon_xref47":   _profile_dir + "logo.png",
        }
        # Also check logo.png separately for logo asset
        _logo_path = _profile_dir + "logo.png"
        if os.path.isfile(_logo_path):
            _asset_map["sample_asset_0_xref_36"] = _logo_path  # logo in body textblock

        # Split template at \begin{document}
        _split = tex.split(r"\begin{document}", 1)
        if len(_split) == 2:
            _doc_body = r"\begin{document}" + _split[1]

            # For each T2L asset name, substitute paths if file exists.
            # The pattern matches {assetname} or {assetname.ext} inside
            # \includegraphics arguments — simple and reliable.
            for _t2l_name, _dest_path in _asset_map.items():
                _pat = r"\{" + _re.escape(_t2l_name) + r"(\.[a-zA-Z]+)?\}"
                if os.path.isfile(_dest_path):
                    _doc_body = _re.sub(_pat, "{" + _dest_path + "}", _doc_body)
                else:
                    # Asset doesn't exist in this profile.
                    # Replace the entire \includegraphics[...]{assetname} call
                    # with an empty \mbox{} so the surrounding textblock/node
                    # doesn't choke XeLaTeX.
                    _inc_pat = (
                        r"\\includegraphics(?:\[[^\]]*\])?\s*\{"
                        + _re.escape(_t2l_name)
                        + r"(\.[a-zA-Z]+)?\}"
                    )
                    _doc_body = _re.sub(_inc_pat, r"\\mbox{}", _doc_body, flags=_re.DOTALL)

            # Rebuild with custom preamble replacing the original template preamble
            _doc_class_match = _re.match(r"(\s*\\documentclass[^\n]*\n)", tex)
            _doc_class = (
                _doc_class_match.group(1) if _doc_class_match
                else "\\documentclass[10pt]{article}\n"
            )
            tex = _doc_class + "\n" + _custom_preamble_tex + "\n" + _doc_body

    # Replace all {{KEY}} placeholders with escaped values.
    # Optional fields not provided by the caller are replaced with empty string
    # so that \ifthenelse{\equal{...}{}}{}{...} guards in templates work correctly.
    from schema import DOCUMENT_SCHEMAS  # late import avoids circular dep
    all_optional = set()
    for schema in DOCUMENT_SCHEMAS.values():
        all_optional.update(schema.get("optional", []))

    for key, raw_value in values.items():
        tex = tex.replace(f"{{{{{key}}}}}", _escape_latex(raw_value))

    # Replace any remaining {{KEY}} (optional fields not supplied) with ""
    import re
    tex = re.sub(r"\{\{[A-Za-z_]+\}\}", "", tex)

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
