"""
Receipt parsing: turn raw OCR text into structured expenditure data.

Extracts: merchant, date, line items (name + price), subtotal, tax, total.
Every field carries its own confidence so the UI can show what to trust.
"""

import re
from datetime import datetime

# money like 12.99, $1,204.50, 3,50 (EU comma decimals)
MONEY = re.compile(r"[$€£]?\s?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})\b")

DATE_PATTERNS = [
    (re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"), ("m", "d", "Y")),
    (re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2})\b"), ("m", "d", "y")),
    (re.compile(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b"), ("Y", "m", "d")),
]

TOTAL_KEYWORDS = ("total", "amount due", "balance due", "grand total")
SUBTOTAL_KEYWORDS = ("subtotal", "sub-total", "sub total")
TAX_KEYWORDS = ("tax", "vat", "gst", "hst")
SKIP_KEYWORDS = (
    "change", "cash", "credit", "debit", "visa", "mastercard", "amex",
    "tend", "auth", "approval", "card", "payment",
)


def parse_receipt(text: str, words: list[dict]) -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    low_lines = [ln.lower() for ln in lines]

    merchant = _guess_merchant(lines)
    date = _find_date(text)
    total = _find_labeled_amount(lines, low_lines, TOTAL_KEYWORDS)
    subtotal = _find_labeled_amount(lines, low_lines, SUBTOTAL_KEYWORDS)
    tax = _find_labeled_amount(lines, low_lines, TAX_KEYWORDS)
    items = _find_line_items(lines, low_lines)

    # Sanity check: sum of items vs subtotal/total boosts confidence.
    items_sum = round(sum(i["price"] for i in items), 2)
    checksum_ok = False
    reference = subtotal["value"] if subtotal["value"] else total["value"]
    if reference and items:
        checksum_ok = abs(items_sum - reference) < 0.02

    return {
        "merchant": merchant,
        "date": date,
        "items": items,
        "items_sum": items_sum,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "checksum_ok": checksum_ok,
    }


def _guess_merchant(lines: list[str]) -> dict:
    """Merchant is usually the first prominent non-numeric line."""
    for ln in lines[:5]:
        letters = sum(c.isalpha() for c in ln)
        if letters >= 3 and not MONEY.search(ln):
            return {"value": ln.title(), "confidence": "medium"}
    return {"value": None, "confidence": "low"}


def _find_date(text: str) -> dict:
    for pattern, order in DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        parts = dict(zip(order, m.groups()))
        try:
            year = int(parts.get("Y") or ("20" + parts["y"]))
            date = datetime(year, int(parts["m"]), int(parts["d"]))
            return {"value": date.strftime("%Y-%m-%d"), "confidence": "high"}
        except (ValueError, KeyError):
            continue
    return {"value": None, "confidence": "low"}


def _find_labeled_amount(lines, low_lines, keywords) -> dict:
    """Find e.g. 'TOTAL   23.45'. Search bottom-up: totals live at the bottom."""
    for ln, low in zip(reversed(lines), reversed(low_lines)):
        if any(k in low for k in keywords) and not any(s in low for s in SKIP_KEYWORDS):
            m = MONEY.search(ln)
            if m:
                return {"value": _to_float(m.group(1)), "confidence": "high"}
    return {"value": None, "confidence": "low"}


def _find_line_items(lines, low_lines) -> list[dict]:
    """Lines with a name followed by a price, excluding totals/payment lines."""
    items = []
    for ln, low in zip(lines, low_lines):
        if any(k in low for k in TOTAL_KEYWORDS + SUBTOTAL_KEYWORDS + TAX_KEYWORDS + SKIP_KEYWORDS):
            continue
        m = MONEY.search(ln)
        if not m:
            continue
        name = ln[: m.start()].strip(" .-*#:@")
        if sum(c.isalpha() for c in name) < 2:
            continue
        items.append({
            "name": name.title(),
            "price": _to_float(m.group(1)),
        })
    return items


def _to_float(raw: str) -> float:
    """Normalize '1,204.50' and '3,50' to floats."""
    raw = raw.replace(" ", "")
    if "," in raw and "." in raw:
        raw = raw.replace(",", "")          # 1,204.50 -> 1204.50
    elif "," in raw:
        raw = raw.replace(",", ".")         # 3,50 -> 3.50
    return float(raw)
