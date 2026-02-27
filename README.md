# 🧾 AI Invoice Generator

A professional, fully dynamic **Streamlit** web app that generates beautiful PDF invoices using **ReportLab** — with an AI autofill feature powered by the OpenAI API.

> 🤖 **Vibe coded** using [Antigravity](https://antigravity.google) powered by **Claude Sonnet 4.6**

---

## ✨ Features

- **Dynamic Invoice Builder** — fill in all invoice parameters via a clean web UI
- **Multi-Day / Multi-Meal Support** — items grouped by date & meal type (Breakfast / Lunch / Dinner / Snacks etc.)
- **Auto-calculated Totals** — subtotal, CGST, SGST, service charge, and grand total update live
- **Amount in Words** — Indian numbering (₹ Rupees, Paise) auto-generated
- **AI Autofill** — describe an order in plain English and let AI parse it into invoice rows
- **Logo Upload** — upload a PNG/JPG logo displayed in the PDF header
- **Multi-Page PDF** — rows flow automatically onto continuation pages with correct "Page N of M" footer
- **Centered Table Layout** — pixel-perfect A4 centering using ReportLab
- **Download Button** — one-click PDF download

---

## 📁 Project Structure

```
Invoice generator/
├── app.py                 # Streamlit UI (main entry point)
├── invoice_generator.py   # ReportLab PDF generation engine
├── utils.py               # Helpers: totals, amount-in-words, AI autofill
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
| `openai` | AI autofill (optional) |
| `Pillow` | Logo image handling |

---

## 🤖 AI Autofill Setup (Optional)

1. Get an API key from [OpenAI](https://platform.openai.com) or any compatible provider (Groq, Azure, etc.)
2. Paste it in the **sidebar → AI Settings → OpenAI API Key** field
3. Type your order in plain English in the **AI Autofill** panel, e.g.:

> *"3 guests had paneer tikka, butter naan, and sweet lassi"*

The AI will parse and populate the item rows automatically.

---

## 🎨 Invoice Design

The PDF invoice features:
- White header with restaurant logo, name, address, GSTIN, FSSAI
- Orange accent colour (`#E8650A`) throughout
- Dark navy footer with restaurant details
- Meal-type section separators (Breakfast / Lunch / Dinner)
- Grand Total bar in orange
- Green payment stamp (UPI / Cash / Card)
- Auto page-break with compact continuation header

---

## 🧑‍💻 Developer

Built with ❤️ by **Anubhav Aka hex47i** — [anubhavnath.dev](https://anubhavnath.dev)

---

