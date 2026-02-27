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

from invoice_generator import generate_invoice
from utils import ai_autofill, calculate_totals, compute_item_amount, convert_to_words

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
MEAL_TYPES = ["Breakfast", "Lunch", "Dinner", "Snacks", "Beverages", "Other"]

def _default_items() -> list[dict]:
    """Return the sample Dine & Spoon order as default rows (fully editable)."""
    raw = [
        # date,       description,                  qty,  unit_price, gst_pct,  meal_type
        ("27 Jan", "Masala Chai",                    3,   50.0,  5.0, "Breakfast"),
        ("27 Jan", "Aloo Paratha (w/ Butter)",       3,  110.0,  5.0, "Breakfast"),
        ("27 Jan", "Poha",                           3,   90.0,  5.0, "Breakfast"),
        ("27 Jan", "Fresh Fruit Curd Bowl",          3,   80.0,  5.0, "Breakfast"),
        ("27 Jan", "Dal Tadka",                      1,  180.0,  5.0, "Lunch"),
        ("27 Jan", "Paneer Matar Sabji",             1,  220.0,  5.0, "Lunch"),
        ("27 Jan", "Jeera Rice",                     2,  120.0,  5.0, "Lunch"),
        ("27 Jan", "Butter Roti",                    6,   25.0,  5.0, "Lunch"),
        ("27 Jan", "Sweet Lassi",                    3,   90.0,  5.0, "Lunch"),
        ("27 Jan", "Gulab Jamun (2 pcs)",            3,   65.0,  5.0, "Lunch"),
        ("27 Jan", "Paneer Tikka (Starter)",         1,  280.0,  5.0, "Dinner"),
        ("27 Jan", "Paneer Butter Masala",           1,  280.0,  5.0, "Dinner"),
        ("27 Jan", "Dal Makhani",                    1,  220.0,  5.0, "Dinner"),
        ("27 Jan", "Butter Naan",                    6,   45.0,  5.0, "Dinner"),
        ("27 Jan", "Raita",                          1,   80.0,  5.0, "Dinner"),
        ("27 Jan", "Masala Cold Drink",              3,   65.0,  5.0, "Dinner"),
        ("28 Jan", "Hara Bhara Kabab",               1,  200.0,  5.0, "Dinner"),
        ("28 Jan", "Kadai Paneer",                   1,  260.0,  5.0, "Dinner"),
        ("28 Jan", "Veg Biryani",                    2,  200.0,  5.0, "Dinner"),
        ("28 Jan", "Garlic Naan",                    4,   50.0,  5.0, "Dinner"),
        ("28 Jan", "Fresh Lime Soda",                3,   60.0,  5.0, "Dinner"),
        ("29 Jan", "Veg Spring Rolls",               1,  180.0,  5.0, "Dinner"),
        ("29 Jan", "Shahi Paneer",                   1,  280.0,  5.0, "Dinner"),
        ("29 Jan", "Veg Manchurian Dry",             1,  200.0,  5.0, "Dinner"),
        ("29 Jan", "Laccha Paratha",                 4,   50.0,  5.0, "Dinner"),
        ("29 Jan", "Masala Chaas",                   3,   55.0,  5.0, "Dinner"),
    ]
    return [
        {
            "date": date,
            "meal_type": meal_type,
            "description": desc,
            "qty": float(qty),
            "unit_price": float(unit_price),
            "gst_pct": float(gst_pct),
            "amount": compute_item_amount(float(qty), float(unit_price), float(gst_pct)),
        }
        for date, desc, qty, unit_price, gst_pct, meal_type in raw
    ]


if "items_df" not in st.session_state:
    st.session_state.items_df = pd.DataFrame(_default_items())

if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None

if "logo_path" not in st.session_state:
    st.session_state.logo_path = None

if "ai_message" not in st.session_state:
    st.session_state.ai_message = ""


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
# ── SIDEBAR: Restaurant Details ───────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="page-title">🧾 AI Invoice</div>', unsafe_allow_html=True)
    st.caption("Generator · v1.0")
    st.divider()

    st.markdown('<div class="section-header">🏪 Restaurant Details</div>', unsafe_allow_html=True)

    restaurant_name = st.text_input("Restaurant Name", value="")
    address = st.text_input(
        "Address",
        value="",
    )
    phone = st.text_input("Phone", value="")
    gstin = st.text_input("GSTIN", value="")
    fssai = st.text_input("FSSAI", value="")

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
    st.markdown('<div class="section-header">🔑 AI Settings</div>', unsafe_allow_html=True)
    openai_api_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")
    openai_base_url = st.text_input(
        "API Base URL",
        value="https://api.openai.com/v1",
        help="Change for compatible providers (e.g. Groq, Azure).",
    )


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
        '"Generate invoice for 3 guests who had paneer tikka, butter naan, and sweet lassi"</p>'
        "</div>",
        unsafe_allow_html=True,
    )
    ai_prompt = st.text_area(
        "Order description",
        placeholder="e.g. 2 guests had dal makhani, 3 butter naans and 2 mango lassis",
        height=80,
        label_visibility="collapsed",
    )
    if st.button("✨ Autofill Items from AI", use_container_width=True):
        if not ai_prompt.strip():
            st.warning("Please enter an order description first.")
        else:
            with st.spinner("Asking AI to parse your order…"):
                try:
                    ai_items = ai_autofill(ai_prompt, openai_api_key, openai_base_url)
                    new_df = pd.DataFrame(ai_items)
                    st.session_state.items_df = new_df
                    st.session_state.ai_message = f"✅ {len(ai_items)} item(s) added from AI."
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
    invoice_number = st.text_input("Invoice Number", value="")
    invoice_date = st.date_input("Invoice Date", value=datetime.date.today())
    visit_period = st.text_input("Visit / Stay Period", value="", placeholder="e.g. 27 Jan – 29 Jan 2026")

with col_cust:
    st.markdown('<div class="section-header">👤 Customer Details</div>', unsafe_allow_html=True)
    customer_name = st.text_input("Customer Name", value="Walk-in Guest")
    table_ref = st.text_input("Table Reference", value="TBL-01 / WALK-IN")
    num_guests = st.number_input("Number of Guests", min_value=1, value=2, step=1)

with col_staff:
    st.markdown('<div class="section-header">👨‍🍳 Staff Details</div>', unsafe_allow_html=True)
    served_by = st.text_input("Served By", value="")
    staff_id = st.text_input("Staff ID", value="")
    st.write("")  # spacer

st.divider()

# ── Items Table ───────────────────────────────────────────────────────────────
_hdr_col, _reset_col, _clear_col = st.columns([4, 1, 1])
with _hdr_col:
    st.markdown('<div class="section-header">🍽️ Invoice Items</div>', unsafe_allow_html=True)
with _reset_col:
    if st.button("↺ Reset to Sample", use_container_width=True, help="Restore the original Dine & Spoon demo order"):
        st.session_state.items_df = pd.DataFrame(_default_items())
        st.rerun()
with _clear_col:
    if st.button("🗑 Clear All", use_container_width=True, help="Remove all rows and start with a blank table"):
        st.session_state.items_df = pd.DataFrame([{
            "date": datetime.date.today().strftime("%d %b"),
            "meal_type": "Dinner",
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
        "meal_type": st.column_config.SelectboxColumn(
            "Meal",
            options=MEAL_TYPES,
            default="Dinner",
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
    payment_ref = st.text_input("Payment Reference / UTR", value="")

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
                # Restaurant
                "restaurant_name": restaurant_name,
                "address": address,
                "phone": phone,
                "gstin": gstin,
                "fssai": fssai,
                "logo_path": st.session_state.logo_path,
                # Invoice
                "invoice_number": invoice_number,
                "invoice_date": invoice_date.strftime("%d %B %Y"),
                "visit_period": visit_period or invoice_date.strftime("%d %B %Y"),
                # Customer
                "customer_name": customer_name,
                "table_ref": table_ref,
                "num_guests": str(int(num_guests)),
                # Staff
                "served_by": served_by,
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
            + f"_{restaurant_name.replace(' ', '_')}.pdf"
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