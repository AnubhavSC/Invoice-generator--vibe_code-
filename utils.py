"""
utils.py – Helper functions for AI Invoice Generator
"""

from __future__ import annotations
import json
import re
import random
import string
import requests
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
# AI Autofill (OpenAI-compatible) & Tavily Search
# ---------------------------------------------------------------------------

def generate_utr() -> str:
    """Generate a random 12-character alphanumeric UTR."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=12))

def generate_invoice_number() -> str:
    """Generate a random invoice number like INV-123456."""
    return f"INV-{random.randint(100000, 999999)}"


SYSTEM_PROMPT_EXTRACT_QUERY = """You are an assistant that extracts business search queries.
The user will describe an order or service request (e.g. "I hired AC Repair Pros in Delhi..." or "Plumbing service from Bob's Pipes...").
Return a JSON object with two keys:
1. "needs_search": boolean (true if a business name/location is mentioned and we should look it up).
2. "search_query": string (the business name and location to search for, e.g. "AC Repair Pros Delhi").

Example output:
{
  "needs_search": true,
  "search_query": "AC Repair Pros Delhi"
}
"""

SYSTEM_PROMPT_PARSE = """You are an intelligent universal invoice data extraction assistant.
You will be provided with a user's natural language order/service description, and optionally some search context from the web about the business.

Your task is to extract:
1. "business": An object containing the business details.
2. "staff": An object containing staff/handler details (Handled By, Staff/Agent ID).
3. "items": An array of line items ordered or services rendered.

If you cannot find specific identifiers in the context (or if no context is provided), you MUST creatively and autonomously generate plausible looking values for them.
- Phone: 10 digits starting with 7, 8, or 9.
- GSTIN/Tax ID: 15 alphanumeric characters (e.g. 27ABCDE1234F1Z5).
- Registration No (e.g. CIN, MSME): 10-21 characters/digits.
- Staff details: Create a plausible first name for "handled_by" and an alphanumeric "staff_id" (e.g., EMP-402, AGT-11).
- Category: Categorize the item logically (e.g. Service, Product, Subscription, Consultation, Hardware, Software, Food, etc)
- Tax (`gst_pct`): Intelligently decide whether an item should be taxed. If the item is very cheap (like a petty expense, e.g., "50rs motor") or usually non-taxable, set `gst_pct` to 0. Otherwise use a standard tax rate (e.g., 5, 12, or 18%).
- Invoice Date (`invoice_date`): Extract the invoice date from the text. If multiple dates are provided, extract the latest/last date described. If no date is found, use "Today".

Return ONLY a valid JSON object with the following structure – no extra text:

{
  "invoice_date": "Extracted last date or 'Today'",
  "business": {
    "name": "Extracted or inferred name",
    "address": "Extracted or inferred address",
    "phone": "Extracted or generated 10-digit number",
    "gstin": "Extracted or generated 15-char GSTIN or Tax ID",
    "reg_no": "Extracted or generated Registration or License No"
  },
  "staff": {
    "handled_by": "Extracted or generated name",
    "staff_id": "Extracted or generated ID"
  },
  "items": [
    {
      "date": "Extracted date or 'Today'",
      "category": "Extracted or inferred category string (e.g. Service, Product, Maintenance, Labor)",
      "description": "Item or service name",
      "qty": number,
      "unit_price": number,
      "gst_pct": 5
    }
  ]
}
"""


def ai_autofill(prompt: str, api_key: str, tavily_api_key: str = "", base_url: str = "https://api.groq.com/openai/v1") -> dict:
    """
    Call an OpenAI-compatible chat endpoint to parse a natural-language order
    description into structured invoice rows and business details.
    
    If tavily_api_key is provided, optionally performs a web search to enrich business data.

    Returns a dict with "business" and "items".
    Raises RuntimeError with a descriptive message on failure.
    """
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    if not api_key or api_key.strip() == "":
        raise RuntimeError("Please provide a valid API key in the sidebar.")

    client = OpenAI(api_key=api_key.strip(), base_url=base_url)

    # STEP 1: Determine if we need to search for the business
    search_context = ""
    try:
        query_response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_EXTRACT_QUERY},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=300,
        )
        query_raw = query_response.choices[0].message.content or ""
        json_match = re.search(r'\{.*\}', query_raw, re.DOTALL)
        if json_match:
            query_raw = json_match.group(0)
        else:
            query_raw = re.sub(r"```(?:json)?", "", query_raw).strip().rstrip("`").strip()
            
        print(f"Query Extraction Raw JSON: {query_raw}", flush=True)
        query_data = json.loads(query_raw)
        
        needs_search = query_data.get("needs_search", False)
        search_query = query_data.get("search_query", "")
        print(f"Extraction result -> needs_search: {needs_search}, search_query: '{search_query}'", flush=True)
        
        # STEP 2: Use Tavily to search
        if needs_search and search_query and tavily_api_key:
            try:
                tavily_resp = requests.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": tavily_api_key.strip(),
                        "query": f"{search_query} details phone number address GSTIN company",
                        "search_depth": "basic",
                        "include_answer": True,
                        "max_results": 3
                    },
                    timeout=10
                )
                if tavily_resp.status_code == 200:
                    t_data = tavily_resp.json()
                    search_context = f"Tavily Search Answer: {t_data.get('answer', '')}\n"
                    for res in t_data.get("results", []):
                        search_context += f"- {res.get('title')}: {res.get('content')}\n"
                    print("Tavily search successful.", flush=True)
                else:
                    print(f"Tavily API Error {tavily_resp.status_code}: {tavily_resp.text}", flush=True)
            except Exception as e:
                print(f"Tavily search exception: {e}", flush=True)
                
    except Exception as e:
        print(f"Query extraction failed: {e}", flush=True)

    # STEP 3: Final extraction combining user prompt and search context
    final_prompt = f"User Order Description:\n{prompt}\n\n"
    if search_context:
        final_prompt += f"Background search context for the business:\n{search_context}\n"

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_PARSE},
            {"role": "user", "content": final_prompt},
        ],
        temperature=0.2,
        max_tokens=2500,
    )

    raw = response.choices[0].message.content or ""

    # Robust JSON extraction
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        raw = json_match.group(0)
    else:
        # Fallback strip markdown code fences if present
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

    parsed_data = {}
    try:
        parsed_data = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Attempt to auto-repair lightly truncated JSON
        for suffix in ["", "}", "]}", "]}", '"}', '"}]}']:
            try:
                fixed_raw = raw.rstrip(", ") + suffix
                parsed_data = json.loads(fixed_raw)
                break
            except json.JSONDecodeError:
                continue
        else:
            raise RuntimeError(f"AI returned invalid JSON: {exc}\n\nRaw response:\n{raw}")

    items_raw = parsed_data.get("items", [])
    business_raw = parsed_data.get("business", {})
    staff_raw = parsed_data.get("staff", {})

    # Normalise item keys
    normalised_items = []
    for row in items_raw:
        normalised_items.append(
            {
                "date": str(row.get("date", "Today")),
                "category": str(row.get("category", "Service/Product")), # Default or AI extracted
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

    return {
        "invoice_date": parsed_data.get("invoice_date", "Today"),
        "business": business_raw,
        "staff": staff_raw,
        "items": normalised_items
    }
