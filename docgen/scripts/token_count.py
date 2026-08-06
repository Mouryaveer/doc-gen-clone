# coding: utf-8
"""
token_count.py — Estimate Gemini API tokens consumed per document generation.

The document generation pipeline calls Gemini exactly ONCE per request:
  • classify_document() — sends the first 3000 chars of extracted text to
    Gemini and receives a short label back (e.g. "NDA").

This script counts the tokens in the classification prompt for each
document template by simulating what classify.py sends, then prints a
summary table showing prompt tokens, estimated response tokens, and
the total per document type.

Run from the docgen/ directory:
    python scripts/token_count.py

Requirements:
    pip install google-genai python-dotenv
"""

from __future__ import annotations

import os
import re
import sys

# ── make sure docgen/ is on sys.path so local imports work ──────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
DOCGEN_DIR = os.path.abspath(os.path.join(HERE, ".."))
if DOCGEN_DIR not in sys.path:
    sys.path.insert(0, DOCGEN_DIR)

from config import GEMINI_API_KEY, MODEL_NAME  # noqa: E402  (after path fix)
from google import genai                        # noqa: E402

# ── template locations ───────────────────────────────────────────────────────
TEMPLATES_DIR = os.path.join(DOCGEN_DIR, "templates")
ALLOWED_TYPES = (
    "NDA",
    "Offer_Letter",
    "Contract",
    "MOU",
    "IP_Agreement",
    "Onboarding_Letter",
)
TEMPLATE_FILES = {
    "NDA":               "nda_template.tex",
    "Offer_Letter":      "offer_letter_template.tex",
    "Contract":          "contract_template.tex",
    "MOU":               "mou_template.tex",
    "IP_Agreement":      "ip_agreement_template.tex",
    "Onboarding_Letter": "onboarding_template.tex",
}

# ── helpers ──────────────────────────────────────────────────────────────────

def _strip_latex(tex: str) -> str:
    """Roughly strip LaTeX markup to approximate plain text sent to Gemini."""
    tex = re.sub(r"%.*", " ", tex)                              # comments
    tex = re.sub(r"\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})*", " ", tex)  # commands
    tex = re.sub(r"[{}]", " ", tex)                             # braces
    tex = re.sub(r"\s+", " ", tex).strip()
    return tex


def _build_prompt(doc_type: str) -> str:
    """Reproduce the exact prompt that classify.py sends to Gemini."""
    tex_file = os.path.join(TEMPLATES_DIR, TEMPLATE_FILES[doc_type])
    with open(tex_file, "r", encoding="utf-8") as fh:
        raw_tex = fh.read()
    plain_text = _strip_latex(raw_tex)[:3000]
    return (
        f"Classify this document into exactly one of:\n"
        f"{', '.join(ALLOWED_TYPES)}.\n\n"
        f"Do NOT return Other.\n"
        f"Choose the closest match.\n"
        f"Return only the label.\n\n"
        f"Document:\n{plain_text}"
    )


def _count_tokens(client: genai.Client, model: str, text: str) -> int:
    """Call the Gemini token-counting API and return total_tokens."""
    response = client.models.count_tokens(model=model, contents=text)
    return response.total_tokens


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    client = genai.Client(api_key=GEMINI_API_KEY)

    print(f"\nModel : {MODEL_NAME}")
    print(f"{'─' * 72}")
    print(f"{'Document Type':<22} {'Prompt chars':>13} {'Prompt tokens':>14} {'Resp tokens':>12} {'TOTAL':>8}")
    print(f"{'─' * 72}")

    # Typical response is a single label (5–15 tokens).
    # We count tokens for the longest label for a conservative estimate.
    label_tokens: dict[str, int] = {}
    for label in ALLOWED_TYPES:
        label_tokens[label] = _count_tokens(client, MODEL_NAME, label)

    grand_total_prompt = 0
    grand_total_all = 0

    for doc_type in ALLOWED_TYPES:
        prompt = _build_prompt(doc_type)
        prompt_tok = _count_tokens(client, MODEL_NAME, prompt)
        resp_tok = label_tokens[doc_type]          # actual response for this label
        total_tok = prompt_tok + resp_tok

        grand_total_prompt += prompt_tok
        grand_total_all    += total_tok

        print(
            f"{doc_type:<22} {len(prompt):>13,} {prompt_tok:>14,} {resp_tok:>12,} {total_tok:>8,}"
        )

    print(f"{'─' * 72}")
    print(f"{'TOTAL (all 6 docs)':<22} {'':>13} {grand_total_prompt:>14,} {'':>12} {grand_total_all:>8,}")
    print(f"{'Average per doc':<22} {'':>13} {grand_total_prompt//6:>14,} {'':>12} {grand_total_all//6:>8,}")
    print()

    # ── Cost estimate at Gemini 2.5 Flash pricing ────────────────────────────
    # Input:  $0.075 / 1M tokens  (text)
    # Output: $0.30  / 1M tokens  (text, non-thinking)
    INPUT_RATE  = 0.075 / 1_000_000   # $ per token
    OUTPUT_RATE = 0.300 / 1_000_000   # $ per token

    print("Cost estimate (Gemini 2.5 Flash, per-generation):")
    print(f"{'─' * 72}")
    print(f"{'Document Type':<22} {'Input $':>12} {'Output $':>12} {'Total $':>12}")
    print(f"{'─' * 72}")

    for doc_type in ALLOWED_TYPES:
        prompt = _build_prompt(doc_type)
        prompt_tok = _count_tokens(client, MODEL_NAME, prompt)
        resp_tok   = label_tokens[doc_type]
        cost_in    = prompt_tok * INPUT_RATE
        cost_out   = resp_tok   * OUTPUT_RATE
        cost_total = cost_in + cost_out
        print(
            f"{doc_type:<22} ${cost_in:>11.6f} ${cost_out:>11.6f} ${cost_total:>11.6f}"
        )

    print(f"{'─' * 72}")
    print()
    print("Note: The pipeline calls Gemini only for classification (once per")
    print("      request). Template rendering is pure LaTeX — zero AI tokens.")
    print("      Digital signing uses pyHanko locally — zero AI tokens.")
    print()


if __name__ == "__main__":
    main()
