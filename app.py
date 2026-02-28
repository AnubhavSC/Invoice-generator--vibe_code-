"""
app.py – AI Invoice Generator
Run with: streamlit run app.py
"""

from __future__ import annotations

import datetime
import tempfile
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_cookies_controller import CookieController

from invoice_generator import generate_invoice
from utils import ai_autofill, calculate_totals, compute_item_amount, convert_to_words, generate_utr, generate_invoice_number

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Invoice Generator",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS – premium dark-mode look
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [data-testid="stApp"] {
    font-family: 'Inter', sans-serif;
    background: #0F1117;
    color: #E2E8F0;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #1A1A2E !important;
    border-right: 1px solid #2D2D4E;
}

/* Cards / expanders */
[data-testid="stExpander"] {
    background: #1E2030;
    border: 1px solid #2D3250;
    border-radius: 12px;
}

/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] select,
[data-testid="stDateInput"] input,
textarea {
    background: #252842 !important;
    border: 1px solid #3D4166 !important;
    border-radius: 8px !important;
    color: #E2E8F0 !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #E8650A, #FF8C42);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    padding: 0.5rem 1.4rem;
    transition: all 0.2s ease;
    box-shadow: 0 4px 15px rgba(232, 101, 10, 0.3);
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(232, 101, 10, 0.45);
}

.stDownloadButton > button {
    background: linear-gradient(135deg, #1A7F5A, #2ECC71);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    padding: 0.6rem 1.6rem;
    transition: all 0.2s ease;
    box-shadow: 0 4px 15px rgba(46, 204, 113, 0.3);
    width: 100%;
}
.stDownloadButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(46, 204, 113, 0.45);
}

/* Section headers */
.section-header {
    font-size: 1rem;
    font-weight: 600;
    color: #E8650A;
    padding-bottom: 0.4rem;
    border-bottom: 2px solid #E8650A33;
    margin-bottom: 1rem;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* Totals card */
.totals-card {
    background: #1E2030;
    border: 1px solid #2D3250;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
}
.totals-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    font-size: 0.9rem;
    color: #A0AEC0;
}
.totals-row.grand {
    font-size: 1.1rem;
    font-weight: 700;
    color: #E8650A;
    border-top: 1px solid #3D4166;
    margin-top: 6px;
    padding-top: 8px;
}

/* AI panel */
.ai-panel {
    background: linear-gradient(135deg, #1A1A2E, #252842);
    border: 1px solid #E8650A44;
    border-radius: 12px;
    padding: 1.2rem;
}

/* Page title */
.page-title {
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(135deg, #E8650A, #FF8C42);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
</style>
""",
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Session state defaults
# ─────────────────────────────────────────────────────────────────────────────
CATEGORIES = ["Product", "Service", "Subscription", "Consultation", "Labor", "Hardware", "Software", "Food", "Other"]

def _default_items() -> list[dict]:
    """Return a generic sample order as default rows (fully editable)."""
    raw = [
        # date,       description,                  qty,  unit_price, gst_pct,  category
        ("15 Oct", "Consulting Services (Hours)",      5,  1500.0, 18.0, "Service"),
        ("15 Oct", "Software License (Annual)",        1, 12000.0, 18.0, "Software"),
        ("16 Oct", "Hardware Setup & Installation",    1,  5000.0, 18.0, "Service"),
        ("16 Oct", "Network Router (AC3200)",          2,  3500.0, 18.0, "Hardware"),
        ("18 Oct", "Monthly Maintenance Subscription", 1,  2500.0, 18.0, "Subscription"),
    ]
    return [
        {
            "date": date,
            "category": category,
            "description": desc,
            "qty": float(qty),
            "unit_price": float(unit_price),
            "gst_pct": float(gst_pct),
            "amount": compute_item_amount(float(qty), float(unit_price), float(gst_pct)),
        }
        for date, desc, qty, unit_price, gst_pct, category in raw
    ]


if "items_df" not in st.session_state:
    st.session_state.items_df = pd.DataFrame(_default_items())

if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None

if "logo_path" not in st.session_state:
    st.session_state.logo_path = None

if "ai_message" not in st.session_state:
    st.session_state.ai_message = ""

if "utr_code" not in st.session_state:
    st.session_state.utr_code = generate_utr()

if "invoice_number" not in st.session_state:
    st.session_state.invoice_number = generate_invoice_number()

# Defaults for business inputs to be managed by session_state
defaults = {
    "business_name": "",
    "business_address": "",
    "business_phone": "",
    "business_gstin": "",
    "business_reg_no": "",
    "handled_by": "",
    "staff_id": "",
    "theme_accent": "#E8650A",
    "theme_header": "#1A1A2E",
    "theme_footer": "#1A1A2E",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

cookie_controller = CookieController()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _refresh_amounts(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute the 'amount' column based on qty, unit_price, gst_pct."""
    df = df.copy()
    df["amount"] = df.apply(
        lambda r: compute_item_amount(
            float(r.get("qty", 0) or 0),
            float(r.get("unit_price", 0) or 0),
            float(r.get("gst_pct", 0) or 0),
        ),
        axis=1,
    )
    return df


def _items_to_dicts(df: pd.DataFrame) -> list[dict]:
    return df.to_dict(orient="records")


# ─────────────────────────────────────────────────────────────────────────────
# ── SIDEBAR: Business Details ───────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="page-title">🧾 AI Invoice</div>', unsafe_allow_html=True)
    st.caption("Generator · v3.2.5")
    st.divider()

    st.markdown('<div class="section-header">🏢 Business Details</div>', unsafe_allow_html=True)

    business_name = st.text_input("Business Name", value=st.session_state.business_name)
    address = st.text_input("Address", value=st.session_state.business_address)
    phone = st.text_input("Phone", value=st.session_state.business_phone)
    gstin = st.text_input("GSTIN / Tax ID", value=st.session_state.business_gstin)
    reg_no = st.text_input("Registration No.", value=st.session_state.business_reg_no)

    # Sync manual edits back to session state so they persist across reruns
    st.session_state.business_name = business_name
    st.session_state.business_address = address
    st.session_state.business_phone = phone
    st.session_state.business_gstin = gstin
    st.session_state.business_reg_no = reg_no

    logo_file = st.file_uploader("Upload Logo (PNG / JPG)", type=["png", "jpg", "jpeg"])
    if logo_file:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(logo_file.name).suffix)
        tmp.write(logo_file.read())
        tmp.flush()
        st.session_state.logo_path = tmp.name
        st.image(logo_file, width=80)
    else:
        st.session_state.logo_path = None

    st.divider()
    st.markdown('<div class="section-header">🎨 Invoice Theme</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        accent_color = st.color_picker("Accent", value=st.session_state.theme_accent)
    with c2:
        header_color = st.color_picker("Header", value=st.session_state.theme_header)
    with c3:
        footer_color = st.color_picker("Footer", value=st.session_state.theme_footer)
        
    st.session_state.theme_accent = accent_color
    st.session_state.theme_header = header_color
    st.session_state.theme_footer = footer_color

    st.divider()
    st.markdown('<div class="section-header">🔑 AI Settings</div>', unsafe_allow_html=True)
    
    saved_groq_key = cookie_controller.get('groq_api_key') or ""
    openai_api_key = st.text_input("Groq / Custom API Key", type="password", value=saved_groq_key, placeholder="gsk-...")
    if openai_api_key and openai_api_key != saved_groq_key:
        cookie_controller.set('groq_api_key', openai_api_key)
        
    openai_base_url = st.text_input(
        "API Base URL",
        value="https://api.groq.com/openai/v1",
        help="Change for compatible providers (e.g. Groq, OpenRouter).",
    )
    
    saved_tavily_key = cookie_controller.get('tavily_api_key') or ""
    tavily_api_key = st.text_input("Tavily API Key (Optional)", type="password", value=saved_tavily_key, placeholder="tvly-...", help="Used to locate business details on the web.")
    if tavily_api_key and tavily_api_key != saved_tavily_key:
        cookie_controller.set('tavily_api_key', tavily_api_key)


# ─────────────────────────────────────────────────────────────────────────────
# ── MAIN CONTENT ──────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="page-title">AI Invoice Generator</div>', unsafe_allow_html=True)
st.markdown(
    "Fill in the details below, add your items, and click **Generate Invoice** to download a professional PDF.",
    unsafe_allow_html=False,
)
st.divider()

# ── AI Autofill ───────────────────────────────────────────────────────────────
with st.expander("🤖 AI Autofill – Describe your order in plain English", expanded=False):
    st.markdown(
        '<div class="ai-panel">'
        '<p style="color:#A0AEC0;font-size:0.9rem;margin:0 0 8px;">Example: '
        '"Generate invoice for Jane Doe for AC Repair service at $50/hr for 2 hrs and 1 gas refill at $20"</p>'
        "</div>",
        unsafe_allow_html=True,
    )
    ai_prompt = st.text_area(
        "Order description",
        placeholder="e.g. Acme Corp bought 5 enterprise software licenses at $200 each and 1 day of setup for $500",
        height=80,
        label_visibility="collapsed",
    )
    if st.button("✨ Autofill Items from AI", use_container_width=True):
        if not ai_prompt.strip():
            st.warning("Please enter an order description first.")
        else:
            with st.spinner("Asking AI to parse your order…"):
                try:
                    ai_result = ai_autofill(ai_prompt, openai_api_key, tavily_api_key, openai_base_url)
                    
                    # Update items
                    ai_items = ai_result.get("items", [])
                    if ai_items:
                        new_df = pd.DataFrame(ai_items)
                        st.session_state.items_df = new_df
                        
                    # Update business details
                    bus_info = ai_result.get("business", {})
                    if bus_info:
                        if bus_info.get("name"): st.session_state.business_name = bus_info["name"]
                        if bus_info.get("address"): st.session_state.business_address = bus_info["address"]
                        if bus_info.get("phone"): st.session_state.business_phone = bus_info["phone"]
                        if bus_info.get("gstin"): st.session_state.business_gstin = bus_info["gstin"]
                        if bus_info.get("reg_no"): st.session_state.business_reg_no = bus_info["reg_no"]

                    # Update staff details
                    staff_info = ai_result.get("staff", {})
                    if staff_info:
                        if staff_info.get("handled_by"): st.session_state.handled_by = staff_info["handled_by"]
                        if staff_info.get("staff_id"): st.session_state.staff_id = staff_info["staff_id"]
                        
                    # Update Invoice Date manually if provided
                    extracted_date = ai_result.get("invoice_date", "Today")
                    if extracted_date and str(extracted_date).lower() != "today":
                        import dateparser
                        parsed = dateparser.parse(str(extracted_date))
                        if parsed:
                            st.session_state.invoice_date = parsed.date()

                    st.session_state.ai_message = f"✅ {len(ai_items)} item(s) added and details updated from AI."
                    st.rerun()
                except RuntimeError as e:
                    st.error(str(e))

    if st.session_state.ai_message:
        st.success(st.session_state.ai_message)
        st.session_state.ai_message = ""

st.divider()

# ── Invoice & Customer Details ─────────────────────────────────   ───────────────
col_inv, col_cust, col_staff = st.columns(3)

with col_inv:
    st.markdown('<div class="section-header">📄 Invoice Details</div>', unsafe_allow_html=True)
    # Auto Invoice Number Code Layout
    i_col1, i_col2 = st.columns([4, 1])
    with i_col1:
         invoice_number = st.text_input("Invoice Number", value=st.session_state.invoice_number)
         st.session_state.invoice_number = invoice_number
    with i_col2:
         st.markdown("<br>", unsafe_allow_html=True) # alignment spacer
         if st.button("🔄", help="Generate new Invoice #", use_container_width=True, key="btn_inv"):
             st.session_state.invoice_number = generate_invoice_number()
             st.rerun()
             
    if "invoice_date" not in st.session_state:
        st.session_state.invoice_date = datetime.date.today()
    invoice_date = st.date_input("Invoice Date", value=st.session_state.invoice_date)
    st.session_state.invoice_date = invoice_date
    
    visit_period = st.text_input("Service / Project Period", value="", placeholder="e.g. 27 Jan – 29 Jan 2026")

with col_cust:
    st.markdown('<div class="section-header">👤 Customer Details</div>', unsafe_allow_html=True)
    customer_name = st.text_input("Customer Name", value="Walk-in Client")
    customer_ref = st.text_input("Customer/Project Ref", value="REF-01")
    customer_qty = st.number_input("Customer Qty / Pax", min_value=1, value=1, step=1)

with col_staff:
    st.markdown('<div class="section-header">👨‍💼 Staff/Agent Details</div>', unsafe_allow_html=True)
    handled_by = st.text_input("Handled By", value=st.session_state.handled_by)
    staff_id = st.text_input("Staff/Agent ID", value=st.session_state.staff_id)
    
    st.session_state.handled_by = handled_by
    st.session_state.staff_id = staff_id
    
    st.write("")  # spacer

st.divider()

# ── Items Table ───────────────────────────────────────────────────────────────
_hdr_col, _reset_col, _clear_col = st.columns([4, 1, 1])
with _hdr_col:
    st.markdown('<div class="section-header">📦 Invoice Items</div>', unsafe_allow_html=True)
with _reset_col:
    if st.button("↺ Reset to Sample", use_container_width=True, help="Restore the original sample order"):
        st.session_state.items_df = pd.DataFrame(_default_items())
        st.rerun()
with _clear_col:
    if st.button("🗑 Clear All", use_container_width=True, help="Remove all rows and start with a blank table"):
        st.session_state.items_df = pd.DataFrame([{
            "date": datetime.date.today().strftime("%d %b"),
            "category": "Service",
            "description": "",
            "qty": 1.0,
            "unit_price": 0.0,
            "gst_pct": 5.0,
            "amount": 0.0,
        }])
        st.rerun()

edited_df = st.data_editor(
    st.session_state.items_df,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "date": st.column_config.TextColumn("Date", width="small"),
        "category": st.column_config.SelectboxColumn(
            "Category",
            options=CATEGORIES,
            default="Service",
            width="small",
            required=True,
        ),
        "description": st.column_config.TextColumn("Item Description", width="large"),
        "qty": st.column_config.NumberColumn("Qty", min_value=0, step=0.5, format="%.2f", width="small"),
        "unit_price": st.column_config.NumberColumn(
            "Unit Price (₹)", min_value=0, format="%.2f", width="small"
        ),
        "gst_pct": st.column_config.NumberColumn(
            "GST %", min_value=0, max_value=100, step=0.5, format="%.1f", width="small"
        ),
        "amount": st.column_config.NumberColumn(
            "Amount (₹)", disabled=True, format="%.2f", width="small"
        ),
    },
    key="items_editor",
)

# Recompute amounts whenever user edits
edited_df = _refresh_amounts(edited_df)
st.session_state.items_df = edited_df

st.divider()

# ── Tax / Charges & Payment ───────────────────────────────────────────────────
col_tax, col_pay, col_totals = st.columns([1, 1, 1.2])

with col_tax:
    st.markdown('<div class="section-header">🧮 Tax & Charges</div>', unsafe_allow_html=True)
    cgst_pct = st.number_input("CGST %", min_value=0.0, max_value=50.0, value=2.5, step=0.5, format="%.2f")
    sgst_pct = st.number_input("SGST %", min_value=0.0, max_value=50.0, value=2.5, step=0.5, format="%.2f")
    service_charge_pct = st.number_input(
        "Service Charge %", min_value=0.0, max_value=50.0, value=5.0, step=0.5, format="%.2f"
    )

with col_pay:
    st.markdown('<div class="section-header">💳 Payment Details</div>', unsafe_allow_html=True)
    payment_mode = st.selectbox(
        "Payment Mode",
        ["Cash", "UPI", "Card", "Net Banking", "Cheque", "Other"],
        index=1,
    )
    
    # Auto UTR Generation Code Layout
    u_col1, u_col2 = st.columns([5, 1])
    with u_col1:
         payment_ref = st.text_input("Payment Reference / UTR", value=st.session_state.utr_code)
         st.session_state.utr_code = payment_ref
    with u_col2:
         st.markdown("<br>", unsafe_allow_html=True) # alignment spacer
         if st.button("🔄", help="Generate new UTR code", use_container_width=True):
             st.session_state.utr_code = generate_utr()
             st.rerun()

# Compute totals
items_list = _items_to_dicts(edited_df)
totals = calculate_totals(items_list, cgst_pct, sgst_pct, service_charge_pct)

with col_totals:
    st.markdown('<div class="section-header">💰 Summary</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="totals-card">
            <div class="totals-row"><span>Subtotal</span><span>₹ {totals['subtotal']:,.2f}</span></div>
            <div class="totals-row"><span>CGST @ {cgst_pct}%</span><span>₹ {totals['cgst']:,.2f}</span></div>
            <div class="totals-row"><span>SGST @ {sgst_pct}%</span><span>₹ {totals['sgst']:,.2f}</span></div>
            <div class="totals-row"><span>Service Charge @ {service_charge_pct}%</span><span>₹ {totals['service_charge']:,.2f}</span></div>
            <div class="totals-row grand"><span>GRAND TOTAL</span><span>₹ {totals['grand_total']:,.2f}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# ── Generate & Download ───────────────────────────────────────────────────────
gen_col, dl_col = st.columns([1, 1])

with gen_col:
    if st.button("🧾 Generate Invoice", use_container_width=True):
        with st.spinner("Generating professional PDF…"):
            invoice_data = {
                # Business
                "business_name": business_name,
                "address": address,
                "phone": phone,
                "gstin": gstin,
                "reg_no": reg_no,
                "logo_path": st.session_state.logo_path,
                # Invoice
                "invoice_number": invoice_number,
                "invoice_date": invoice_date.strftime("%d %B %Y"),
                "visit_period": visit_period or invoice_date.strftime("%d %B %Y"),
                # Theme
                "theme": {
                    "accent_color": accent_color,
                    "header_color": header_color,
                    "footer_color": footer_color,
                },
                # Customer
                "customer_name": customer_name,
                "customer_ref": customer_ref,
                "customer_qty": str(int(customer_qty)),
                # Staff
                "handled_by": handled_by,
                "staff_id": staff_id,
                # Items & Totals
                "items": items_list,
                "totals": totals,
                # Payment
                "payment_mode": payment_mode,
                "payment_ref": payment_ref,
                # Words
                "amount_in_words": convert_to_words(totals["grand_total"]),
            }
            try:
                pdf_bytes = generate_invoice(invoice_data)
                st.session_state.pdf_bytes = pdf_bytes
                st.success("✅ Invoice generated successfully!")
            except Exception as e:
                st.error(f"PDF generation failed: {e}")

with dl_col:
    if st.session_state.pdf_bytes:
        safe_name = (
            invoice_number.replace(" ", "_").replace("/", "-")
            + f"_{business_name.replace(' ', '_')}.pdf"
        )
        st.download_button(
            label="⬇️  Download PDF Invoice",
            data=st.session_state.pdf_bytes,
            file_name=safe_name,
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.info("👈 Click **Generate Invoice** to create your PDF.")

st.divider()

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div style="text-align:center; color:#555; font-size:0.8rem; padding: 1rem 0;">
    Built with ❤️ using <strong>Streamlit</strong> &amp; <strong>ReportLab</strong> · 
    <a href="https://anubhavnath.dev" target="_blank" style="color:#E8650A;text-decoration:none;">
        Developed by Anubhav Aka hex47i
    </a>
</div>
""",
    unsafe_allow_html=True,
)