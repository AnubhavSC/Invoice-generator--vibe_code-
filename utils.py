"""
utils.py – Helper functions for AI Invoice Generator
"""

from __future__ import annotations
import json
import re
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Totals calculation
# ---------------------------------------------------------------------------

def calculate_totals(
    items: list[dict],
    cgst_pct: float,
    sgst_pct: float,
    service_charge_pct: float,
) -> dict[str, float]:
    """
    Given a list of item dicts (each with 'qty', 'unit_price', 'gst_pct')
    and the overall charge percentages, return a dict of computed totals.

    Each item's 'amount' = qty * unit_price * (1 + gst_pct / 100)
    """
    subtotal_pre_gst = 0.0
    item_tax_total = 0.0

    for item in items:
        try:
            qty = float(item.get("qty", 0) or 0)
            unit_price = float(item.get("unit_price", 0) or 0)
            gst_pct = float(item.get("gst_pct", 0) or 0)
        except (ValueError, TypeError):
            continue

        base = qty * unit_price
        tax = base * gst_pct / 100
        subtotal_pre_gst += base
        item_tax_total += tax

    subtotal = subtotal_pre_gst + item_tax_total  # inclusive price shown as subtotal
    cgst = subtotal * cgst_pct / 100
    sgst = subtotal * sgst_pct / 100
    service_charge = subtotal * service_charge_pct / 100
    grand_total = subtotal + cgst + sgst + service_charge

    return {
        "subtotal": round(subtotal, 2),
        "cgst": round(cgst, 2),
        "sgst": round(sgst, 2),
        "service_charge": round(service_charge, 2),
        "grand_total": round(grand_total, 2),
        "cgst_pct": cgst_pct,
        "sgst_pct": sgst_pct,
        "service_charge_pct": service_charge_pct,
    }


def compute_item_amount(qty: float, unit_price: float, gst_pct: float) -> float:
    """Return amount for a single item row (base + GST)."""
    return round(qty * unit_price * (1 + gst_pct / 100), 2)


# ---------------------------------------------------------------------------
# Amount → words (Indian numbering)
# ---------------------------------------------------------------------------

ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _words_lt_100(n: int) -> str:
    if n < 20:
        return ONES[n]
    return (TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else "")).strip()


def _words_lt_1000(n: int) -> str:
    if n < 100:
        return _words_lt_100(n)
    return (ONES[n // 100] + " Hundred" + (" " + _words_lt_100(n % 100) if n % 100 else "")).strip()


def convert_to_words(amount: float) -> str:
    """Convert a rupee amount to Indian-English words."""
    rupees = int(amount)
    paise = round((amount - rupees) * 100)

    def _rupee_words(n: int) -> str:
        if n == 0:
            return "Zero"
        parts = []
        if n >= 10_00_000:
            parts.append(_words_lt_1000(n // 10_00_000) + " Crore")
            n %= 10_00_000
        if n >= 1_00_000:
            parts.append(_words_lt_1000(n // 1_00_000) + " Lakh")
            n %= 1_00_000
        if n >= 1000:
            parts.append(_words_lt_1000(n // 1000) + " Thousand")
            n %= 1000
        if n >= 100:
            parts.append(ONES[n // 100] + " Hundred")
            n %= 100
        if n:
            parts.append(_words_lt_100(n))
        return " ".join(parts)

    result = "Rupees " + _rupee_words(rupees)
    if paise:
        result += f" and {paise} Paise"
    return result + " Only"


# ---------------------------------------------------------------------------
# AI Autofill (OpenAI-compatible)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a restaurant invoice assistant.
The user will describe an order in natural language.
Return ONLY a valid JSON array of invoice line items – no extra text.
Each object must have exactly these keys:
  "date": string (e.g. "Today"),
  "description": string,
  "qty": number,
  "unit_price": number,
  "gst_pct": number (use 5 for food items unless stated otherwise)

Example output:
[
  {"date": "Today", "description": "Paneer Tikka", "qty": 1, "unit_price": 280, "gst_pct": 5},
  {"date": "Today", "description": "Butter Naan", "qty": 3, "unit_price": 45, "gst_pct": 5}
]
"""


def ai_autofill(prompt: str, api_key: str, base_url: str = "https://api.openai.com/v1") -> list[dict]:
    """
    Call an OpenAI-compatible chat endpoint to parse a natural-language order
    description into structured invoice rows.

    Returns a list of item dicts ready to be merged into the Streamlit data editor.
    Raises RuntimeError with a descriptive message on failure.
    """
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    if not api_key or api_key.strip() == "":
        raise RuntimeError("Please provide a valid OpenAI API key in the sidebar.")

    client = OpenAI(api_key=api_key.strip(), base_url=base_url)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=800,
    )

    raw = response.choices[0].message.content or ""

    # Strip markdown code fences if present
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

    try:
        items_raw: list[dict] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"AI returned invalid JSON: {exc}\n\nRaw response:\n{raw}")

    # Normalise keys
    normalised = []
    for row in items_raw:
        normalised.append(
            {
                "date": str(row.get("date", "Today")),
                "description": str(row.get("description", "")),
                "qty": float(row.get("qty", 1)),
                "unit_price": float(row.get("unit_price", 0)),
                "gst_pct": float(row.get("gst_pct", 5)),
                "amount": compute_item_amount(
                    float(row.get("qty", 1)),
                    float(row.get("unit_price", 0)),
                    float(row.get("gst_pct", 5)),
                ),
            }
        )

    return normalised
