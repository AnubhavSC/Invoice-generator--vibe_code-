

from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Brand colors (matching original script) ──────────────────────────────────
BRAND_ORANGE = colors.HexColor("#E8650A")
BRAND_DARK = colors.HexColor("#1A1A2E")
BRAND_GRAY = colors.HexColor("#F5F5F0")
LIGHT_BORDER = colors.HexColor("#E0DDD6")
TEXT_MUTED = colors.HexColor("#777777")
TEXT_BODY = colors.HexColor("#2D2D2D")
WHITE = colors.white

W, H = A4  # 595.27 × 841.89 pts


# ── Internal drawing helpers ─────────────────────────────────────────────────

def _meta_pair(c: canvas.Canvas, x: float, y: float, label: str, value: str) -> None:
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 7.5)
    c.drawString(x, y + 5 * mm, label)
    c.setFillColor(TEXT_BODY)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y + 1.5 * mm, value)


def _draw_header(c: canvas.Canvas, width: float, height: float, data: dict) -> None:
    """Draw the white header bar with logo, restaurant info and INVOICE label."""
    margin = 18 * mm

    # White header rectangle
    c.setFillColor(WHITE)
    c.rect(0, height - 52 * mm, width, 52 * mm, fill=1, stroke=0)

    # Logo: uploaded image or orange circle fallback
    cx, cy = margin + 12 * mm, height - 26 * mm
    logo_path: str | None = data.get("logo_path")
    if logo_path:
        try:
            logo_size = 46 * mm
            c.drawImage(
                logo_path,
                cx - logo_size / 2,
                cy - logo_size / 2,
                width=logo_size,
                height=logo_size,
                mask="auto",
                preserveAspectRatio=True,
            )
        except Exception:
            logo_path = None  # fall through to circle

    if not logo_path:
        c.setFillColor(BRAND_ORANGE)
        c.circle(cx, cy, 11 * mm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 10)
        initials = "".join(w[0].upper() for w in data.get("restaurant_name", "R").split()[:2])
        c.drawCentredString(cx, cy - 1.5 * mm, initials)

    # Restaurant name – dark on white
    c.setFillColor(BRAND_DARK)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin + 26 * mm, height - 19 * mm, data.get("restaurant_name", ""))

    c.setFont("Helvetica", 8.5)
    c.setFillColor(TEXT_MUTED)
    c.drawString(margin + 26 * mm, height - 27 * mm, data.get("address", ""))
    c.drawString(
        margin + 26 * mm,
        height - 34 * mm,
        f"Ph: {data.get('phone', '')}  |  GSTIN: {data.get('gstin', '')}  |  FSSAI: {data.get('fssai', '')}",
    )

    # INVOICE label (right side) – orange stays, subtitle goes dark-muted
    c.setFillColor(BRAND_ORANGE)
    c.setFont("Helvetica-Bold", 22)
    c.drawRightString(width - margin, height - 20 * mm, "INVOICE")
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawRightString(width - margin, height - 28 * mm, "Tax Invoice (GSTIN)")

    # Orange divider stripe
    c.setFillColor(BRAND_ORANGE)
    c.rect(0, height - 54 * mm, width, 2 * mm, fill=1, stroke=0)


def _draw_meta_box(c: canvas.Canvas, width: float, height: float, data: dict) -> None:
    """Draw the gray invoice-meta info box."""
    margin = 18 * mm
    box_y = height - 78 * mm
    c.setFillColor(BRAND_GRAY)
    c.roundRect(margin, box_y, width - 2 * margin, 21 * mm, 3, fill=1, stroke=0)

    col1 = margin + 5 * mm
    col2 = margin + (width - 2 * margin) * 0.33
    col3 = margin + (width - 2 * margin) * 0.62

    _meta_pair(c, col1, box_y, "INVOICE NUMBER", data.get("invoice_number", ""))
    _meta_pair(c, col2, box_y, "INVOICE DATE", data.get("invoice_date", ""))
    _meta_pair(c, col3, box_y, "STAY / VISIT PERIOD", data.get("visit_period", ""))


def _draw_billing_info(c: canvas.Canvas, width: float, height: float, data: dict) -> float:
    """Draw billed-to / served-by block. Returns the y of the separator line."""
    margin = 18 * mm
    bill_y = height - 103 * mm

    # Left – guest info
    c.setFillColor(BRAND_DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, bill_y + 3 * mm, "BILLED TO")
    c.setFillColor(TEXT_BODY)
    c.setFont("Helvetica", 9)
    guest_label = data.get("customer_name", "Walk-in Guest")
    covers = data.get("num_guests", "")
    if covers:
        guest_label += f" ({covers} Covers)"
    c.drawString(margin, bill_y - 2 * mm, guest_label)
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(margin, bill_y - 7 * mm, f"Table / Booking Ref: {data.get('table_ref', '')}")

    # Right – server info
    c.setFillColor(BRAND_DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(width - margin, bill_y + 3 * mm, "SERVED BY")
    c.setFillColor(TEXT_BODY)
    c.setFont("Helvetica", 9)
    served_by = data.get("served_by", "")
    staff_id = data.get("staff_id", "")
    served_str = f"{served_by} (Staff ID: {staff_id})" if staff_id else served_by
    c.drawRightString(width - margin, bill_y - 2 * mm, served_str)
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawRightString(width - margin, bill_y - 7 * mm, "Manager Approved: Yes")

    # Thin separator
    sep_y = height - 115 * mm
    c.setStrokeColor(LIGHT_BORDER)
    c.setLineWidth(0.5)
    c.line(margin, sep_y, width - margin, sep_y)

    return sep_y


def _build_items_table(items: list[dict], num_guests: str = "") -> tuple[Table, set[int]]:
    """
    Build the ReportLab Table, automatically grouping rows by (date, meal_type)
    and inserting styled section-separator rows between each group.
    """
    col_widths = [20 * mm, 83 * mm, 18 * mm, 22 * mm, 18 * mm, 27 * mm]  # must match _TABLE_COL_WIDTHS
    header = ["DATE", "ITEM DESCRIPTION", "QTY", "UNIT (Rs)", "GST%", "AMOUNT (Rs)"]

    # ── Group items by (date, meal_type) preserving insertion order ───────────
    from collections import OrderedDict
    groups: OrderedDict[tuple, list[dict]] = OrderedDict()
    for item in items:
        key = (str(item.get("date", "")), str(item.get("meal_type", "")))
        groups.setdefault(key, []).append(item)

    covers_str = f" ({num_guests} Covers)" if num_guests else ""
    table_data = [header]
    section_row_indices: set[int] = set()

    for (date_str, meal_type), group_items in groups.items():
        # Section label: "— BREAKFAST | 27 Jan (3 Covers) —"
        label_parts = []
        if meal_type:
            label_parts.append(meal_type.upper())
        if date_str:
            label_parts.append(date_str)
        section_label = "  —  ".join(label_parts) + covers_str
        section_label = f"— {section_label} —"

        r_idx = len(table_data)
        section_row_indices.add(r_idx)
        table_data.append([section_label, "", "", "", "", ""])

        first_in_group = True
        for item in group_items:
            qty = float(item.get("qty", 0) or 0)
            row = [
                str(date_str) if first_in_group else "",
                str(item.get("description", "")),
                f"{qty:g}",
                f"{float(item.get('unit_price', 0)):,.2f}",
                f"{item.get('gst_pct', 0)}%",
                f"{float(item.get('amount', 0)):,.2f}",
            ]
            table_data.append(row)
            first_in_group = False

    # ── Base styles ───────────────────────────────────────────────────────────
    style_cmds = [
        # Header row
        ("BACKGROUND",    (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 8),
        ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        # Body rows
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 8),
        ("TEXTCOLOR",     (0, 1), (-1, -1), TEXT_BODY),
        ("TOPPADDING",    (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        # Grid lines
        ("LINEBELOW",     (0, 0), (-1, 0),  0.5, BRAND_ORANGE),
        ("LINEBELOW",     (0, 1), (-1, -1), 0.3, LIGHT_BORDER),
        ("LINEAFTER",     (0, 0), (-1, -1), 0.3, LIGHT_BORDER),
        # Column alignment: date centred, description left, rest centred, amount right
        ("ALIGN",  (0, 1), (0, -1), "CENTER"),   # DATE
        ("ALIGN",  (1, 1), (1, -1), "LEFT"),     # DESCRIPTION
        ("ALIGN",  (2, 1), (2, -1), "CENTER"),   # QTY
        ("ALIGN",  (3, 1), (3, -1), "CENTER"),   # UNIT
        ("ALIGN",  (4, 1), (4, -1), "CENTER"),   # GST%
        ("ALIGN",  (5, 1), (5, -1), "RIGHT"),    # AMOUNT
    ]

    # ── Per-row styles: section headers & alternating background ─────────────
    data_row_counter = 0
    for r in range(1, len(table_data)):
        if r in section_row_indices:
            style_cmds += [
                ("BACKGROUND",    (0, r), (-1, r), colors.HexColor("#FFF3E6")),
                ("TEXTCOLOR",     (0, r), (-1, r), BRAND_ORANGE),
                ("FONTNAME",      (0, r), (-1, r), "Helvetica-BoldOblique"),
                ("FONTSIZE",      (0, r), (-1, r), 7.5),
                ("SPAN",          (0, r), (-1, r)),
                ("ALIGN",         (0, r), (-1, r), "CENTER"),
                ("TOPPADDING",    (0, r), (-1, r), 4),
                ("BOTTOMPADDING", (0, r), (-1, r), 4),
            ]
            data_row_counter = 0          # reset zebra stripe counter per group
        else:
            if data_row_counter % 2 == 1:  # odd data rows get a subtle tint
                style_cmds.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#FAFAF7")))
            data_row_counter += 1

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds))
    return tbl, section_row_indices



def _draw_totals(c: canvas.Canvas, width: float, tot_y: float, totals: dict) -> float:
    """Draw the totals block. Returns y above the payment stamp."""
    margin = 18 * mm
    box_right = width - margin
    box_left = width - margin - 80 * mm
    row_h = 6.5 * mm

    def tot_row(y: float, label: str, value: str, bold: bool = False, highlight: bool = False):
        if highlight:
            c.setFillColor(BRAND_DARK)
            c.rect(box_left - 2, y - 1.5 * mm, box_right - box_left + 4, row_h, fill=1, stroke=0)
            c.setFillColor(WHITE)
        else:
            c.setFillColor(TEXT_BODY)
        font = "Helvetica-Bold" if bold else "Helvetica"
        c.setFont(font, 9 if not highlight else 10)
        c.drawString(box_left + 2 * mm, y + 1.5 * mm, label)
        c.drawRightString(box_right - 2 * mm, y + 1.5 * mm, value)

    subtotal = totals["subtotal"]
    cgst = totals["cgst"]
    sgst = totals["sgst"]
    service_chg = totals["service_charge"]
    grand_total = totals["grand_total"]
    cgst_pct = totals.get("cgst_pct", 2.5)
    sgst_pct = totals.get("sgst_pct", 2.5)
    svc_pct = totals.get("service_charge_pct", 5)

    tot_row(tot_y - 0 * row_h, "Subtotal (excl. extra tax)", f"Rs. {subtotal:,.2f}")
    tot_row(tot_y - 1 * row_h, f"CGST @ {cgst_pct}%",        f"Rs. {cgst:,.2f}")
    tot_row(tot_y - 2 * row_h, f"SGST @ {sgst_pct}%",        f"Rs. {sgst:,.2f}")

    c.setStrokeColor(LIGHT_BORDER)
    c.setLineWidth(0.4)
    c.line(box_left, tot_y - 3 * row_h + 5 * mm, box_right, tot_y - 3 * row_h + 5 * mm)

    tot_row(tot_y - 3 * row_h, f"Service Charge @ {svc_pct}%", f"Rs. {service_chg:,.2f}")

    # Grand total bar – sits one clear row_h below service charge
    gt_bar_bottom = tot_y - 4 * row_h - 2 * mm   # top-of-bar bottom edge
    gt_bar_height = row_h + 2 * mm
    c.setFillColor(BRAND_ORANGE)
    c.rect(box_left - 2, gt_bar_bottom, box_right - box_left + 4, gt_bar_height, fill=1, stroke=0)

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 11)
    gt_text_y = gt_bar_bottom + (gt_bar_height - 3 * mm) / 2   # vertically centred in bar
    c.drawString(box_left + 2 * mm,      gt_text_y, "GRAND TOTAL")
    c.drawRightString(box_right - 2 * mm, gt_text_y, f"Rs. {grand_total:,.2f}")

    # Return y just below the grand total bar with a comfortable gap
    return gt_bar_bottom - 5 * mm



# Total width of all columns – used for centering
_TABLE_COL_WIDTHS = [20 * mm, 83 * mm, 18 * mm, 22 * mm, 18 * mm, 27 * mm]
_TABLE_TOTAL_W   = sum(_TABLE_COL_WIDTHS)         # 188 mm
_TABLE_X         = (W - _TABLE_TOTAL_W) / 2       # left-edge to perfectly centre on A4


def _draw_footer(c: canvas.Canvas, width: float, data: dict,
                 page: int = 1, total_pages: int = 1) -> None:
    """Draw the dark footer bar with dynamic page number."""
    margin = 18 * mm
    footer_lines = [
        f"Thank you for dining at {data.get('restaurant_name', 'us')}! We hope to see you again soon.",
        "All prices are inclusive of applicable taxes as listed. Service charge as per invoice.",
        f"GSTIN: {data.get('gstin', '')}  |  Subject to local jurisdiction.",
        "This is a computer-generated invoice and does not require a physical signature.",
    ]

    c.setFillColor(BRAND_DARK)
    c.rect(0, 0, width, 16 * mm, fill=1, stroke=0)
    c.setFillColor(BRAND_ORANGE)
    c.rect(0, 15.5 * mm, width, 0.5 * mm, fill=1, stroke=0)

    for i, line in enumerate(footer_lines):
        c.setFillColor(colors.HexColor("#AAAAAA") if i > 0 else WHITE)
        c.setFont("Helvetica" if i > 0 else "Helvetica-Bold", 7 if i > 0 else 8)
        c.drawCentredString(width / 2, 12 * mm - i * 3.5 * mm, line)

    c.setFillColor(colors.HexColor("#666666"))
    c.setFont("Helvetica", 7)
    c.drawRightString(
        width - margin,
        3 * mm,
        f"Page {page} of {total_pages}  |  {data.get('restaurant_name', '')}",
    )


def _draw_continuation_header(c: canvas.Canvas, width: float, data: dict) -> float:
    """
    Draw a compact top-of-page header for continuation pages.
    Returns the y-coordinate just below this header (where the table resumes).
    """
    margin = 18 * mm
    bar_h  = 14 * mm

    # Thin dark bar at top
    c.setFillColor(BRAND_DARK)
    c.rect(0, H - bar_h, width, bar_h, fill=1, stroke=0)

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, H - bar_h + 4 * mm, data.get("restaurant_name", ""))

    c.setFillColor(colors.HexColor("#AAAAAA"))
    c.setFont("Helvetica", 8)
    c.drawRightString(
        width - margin,
        H - bar_h + 4 * mm,
        f"Invoice {data.get('invoice_number', '')}  (continued)",
    )

    # Thin orange stripe
    c.setFillColor(BRAND_ORANGE)
    c.rect(0, H - bar_h - 1 * mm, width, 1 * mm, fill=1, stroke=0)

    return H - bar_h - 3 * mm   # y just below the stripe


# ── Public API ───────────────────────────────────────────────────────────────

def generate_invoice(data: dict) -> bytes:
    """
    Generate a PDF invoice from `data` and return raw bytes.
    Supports multi-page overflow: items that don't fit on page 1 flow
    onto subsequent pages. Totals/payment/footer appear on the last page.

    Expected keys in `data`:
      Restaurant: restaurant_name, address, phone, gstin, fssai, logo_path (optional)
      Invoice:    invoice_number, invoice_date, visit_period
      Customer:   customer_name, table_ref, num_guests
      Staff:      served_by, staff_id
      Items:      items  (list[dict] – date, description, qty, unit_price, gst_pct, amount, meal_type)
      Totals:     totals (dict from calculate_totals())
      Payment:    payment_mode, payment_ref
      Words:      amount_in_words
    """
    buf    = io.BytesIO()
    margin = 18 * mm

    FOOTER_H = 16 * mm   # dark footer bar height
    MIN_GAP  =  4 * mm   # minimum whitespace kept before every page break
    TOTALS_H = 62 * mm   # space needed for totals + payment stamp on last page

    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"{data.get('restaurant_name', 'Invoice')} – Invoice {data.get('invoice_number', '')}")
    c.setAuthor(data.get("restaurant_name", ""))
    c.setSubject(f"Invoice {data.get('invoice_number', '')}")

    # ── Page 1 fixed elements ─────────────────────────────────────────────────
    _draw_header(c, W, H, data)
    _draw_meta_box(c, W, H, data)
    sep_y = _draw_billing_info(c, W, H, data)

    items  = data.get("items", [])
    totals = data.get("totals", {})

    if not items:
        words_y = _draw_totals(c, W, sep_y - 30 * mm, totals)
        _draw_payment_stamp(c, W, words_y, data)
        _draw_footer(c, W, data, page=1, total_pages=1)
        c.save()
        buf.seek(0)
        return buf.getvalue()

    # ── Build the full table once ─────────────────────────────────────────────
    full_tbl, _ = _build_items_table(
        items, num_guests=str(data.get("num_guests", ""))
    )

    # Intermediate pages only need MIN_GAP before footer – fill rows as far as possible
    page1_avail = sep_y - 2 * mm - FOOTER_H - MIN_GAP

    cont_top   = H - 14 * mm - 3 * mm   # just below continuation header stripe
    cont_avail = cont_top - FOOTER_H - MIN_GAP

    # ── Split table across pages ──────────────────────────────────────────────
    remaining_tbls: list[Table] = []
    chunks = full_tbl.split(_TABLE_TOTAL_W, page1_avail)

    if len(chunks) == 1:
        # Everything fits on page 1
        remaining_tbls = []
        page1_tbl = chunks[0]
    else:
        # First chunk goes on page 1; keep splitting the rest for continuation
        page1_tbl = chunks[0]
        leftover  = chunks[1]
        while True:
            pieces = leftover.split(_TABLE_TOTAL_W, cont_avail)
            remaining_tbls.append(pieces[0])
            if len(pieces) == 1:
                break
            leftover = pieces[1]

    total_pages = 1 + len(remaining_tbls)

    # ── Draw page 1 table (centered) ─────────────────────────────────────────
    doc_y = sep_y - 2 * mm
    _, tbl_h = page1_tbl.wrap(_TABLE_TOTAL_W, doc_y)
    page1_tbl.drawOn(c, _TABLE_X, doc_y - tbl_h)
    cur_bot_y = doc_y - tbl_h          # y at bottom of table on page 1

    page_num = 1
    if remaining_tbls:
        _draw_footer(c, W, data, page=1, total_pages=1)  # page count finalised later
        page_num = 2

        for tbl_chunk in remaining_tbls:
            c.showPage()
            top_y = _draw_continuation_header(c, W, data)
            _, ch = tbl_chunk.wrap(_TABLE_TOTAL_W, cont_avail)
            tbl_chunk.drawOn(c, _TABLE_X, top_y - ch)
            cur_bot_y = top_y - ch
            _draw_footer(c, W, data, page=page_num, total_pages=1)
            page_num += 1
    else:
        _draw_footer(c, W, data, page=1, total_pages=1)

    # ── Totals: if not enough room below last table chunk, start a new page ───
    if cur_bot_y - FOOTER_H < TOTALS_H:
        c.showPage()
        _draw_continuation_header(c, W, data)
        _draw_footer(c, W, data, page=page_num, total_pages=1)
        cur_bot_y = cont_top   # full continuation page height available

    tot_y = cur_bot_y - 6 * mm
    words_y = _draw_totals(c, W, tot_y, totals)

    # Amount in words
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(margin, words_y, f"Amount in words: {data.get('amount_in_words', '')}")

    _draw_payment_stamp(c, W, words_y, data)

    c.save()
    buf.seek(0)
    return buf.getvalue()


def _draw_payment_stamp(c: canvas.Canvas, width: float, words_y: float, data: dict) -> None:
    """Draw the green PAID / payment mode stamp below the amount-in-words line."""
    margin = 18 * mm
    row_h  = 6.5 * mm
    stamp_y = words_y - 1.5 * row_h

    c.setFillColor(colors.HexColor("#ffffff"))
    c.roundRect(margin, stamp_y - 4 * mm, 80 * mm, 10 * mm, 2, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#ffffff"))
    c.setLineWidth(0.8)
    c.roundRect(margin, stamp_y - 4 * mm, 80 * mm, 10 * mm, 2, fill=0, stroke=1)

    c.setFillColor(colors.HexColor("#000000"))
    c.setFont("Helvetica-Bold", 9)
    payment_mode = data.get("payment_mode", "PAID")
    payment_ref  = data.get("payment_ref", "")
    c.drawString(margin + 3 * mm, stamp_y + 2 * mm, payment_mode.upper())

    ref_str = f"  Ref: {payment_ref}" if payment_ref else ""
    c.setFont("Helvetica", 8)
    c.drawString(margin + 18 * mm, stamp_y + 2 * mm, f"| {ref_str}")
