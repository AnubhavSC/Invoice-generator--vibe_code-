# 🧾 AI Invoice Generator

A professional, fully dynamic **Streamlit** web app that generates beautiful PDF invoices using **ReportLab** — with an AI autofill feature powered by the Groq API and Tavily Search.

> 🤖 **Vibe coded** using [Antigravity](https://antigravity.google) powered by **Claude Sonnet 4.6**

---

## ✨ Features

- **Dynamic Invoice Builder** — fill in all invoice parameters via a clean web UI
- **Universal Application** — usable for Services, Products, Subscriptions, Hardware, Consultations, and more
- **Auto-calculated Totals** — subtotal, CGST, SGST, service charge, and grand total update live
- **Amount in Words** — Indian numbering (₹ Rupees, Paise) auto-generated
- **AI Autofill & Web Search** — describe an order in plain English and let AI parse it into invoice rows. It also searches the web using Tavily to automatically fill in the business's real address, GSTIN, and phone number!
- **🎨 Custom Invoice Themes** — pick custom colors for your invoice Accent, Header, and Footer straight from the UI
- **Logo Upload** — upload a PNG/JPG logo displayed in the PDF header
- **Multi-Page PDF** — rows flow automatically onto continuation pages with correct "Page N of M" footer
- **Download Button** — one-click PDF download

---

## 📁 Project Structure

```
Invoice generator/
├── app.py                 # Streamlit UI (main entry point)
├── invoice_generator.py   # ReportLab PDF generation engine
├── utils.py               # Helpers: totals, amount-in-words, AI autofill, Tavily search
├── requirements.txt       # Python dependencies
└── README.md
```

---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/your-username/ai-invoice-generator.git
cd ai-invoice-generator
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

The app opens at **http://localhost:8501**

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `streamlit` | Web UI framework |
| `reportlab` | PDF generation |
| `pandas` | DataFrame for item table |
| `openai` | AI autofill (configured for Groq API) |
| `requests` | Web search integration (Tavily) |
| `dateparser` | Invoice date extraction logic |
| `streamlit-cookies-controller` | Save API keys locally securely |
| `Pillow` | Logo image handling |

---

## 🤖 AI Autofill Setup

1. Get an API key from [Groq](https://console.groq.com) for the `openai/gpt-oss-120b` model.
2. (Optional) Get a [Tavily API Key](https://tavily.com) to enable searching the web for real business details.
3. Paste both keys in the **sidebar → AI Settings** fields.
4. Type your order/service description in the **AI Autofill** panel, e.g.:

> *"Generate invoice for Jane Doe for AC Repair service at $50/hr for 2 hrs by AC Repair Pros in Delhi"*

The AI will search the web for "AC Repair Pros in Delhi", grab their public phone and address, and automatically populate the invoice rows, GST percentages, and business details.

---

## 🎨 Invoice Design

The generated PDF invoice is highly professional and features:
- White header with your logo, business name, address, GSTIN, and Registration No.
- Configurable **Theme Colors** (Accent, Header, Footer) overriding the default dark/orange scheme.
- Clean and modern itemized tables with custom colored headers.
- Grand Total bar matching your chosen Accent color.
- Green/black payment stamp (UPI / Cash / Card).
- Auto page-break with a compact continuation header for long invoices.

---

## 🧑‍💻 Developer

Built with ❤️ by **Anubhav Aka hex47i** — [anubhavnath.dev](https://anubhavnath.dev)

---
