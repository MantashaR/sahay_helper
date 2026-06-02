# सहाय · Sahay — AI Welfare Navigator for Bharat

> **Tell Sahay your story — in Hindi or English, by voice or text — and watch every government scheme you deserve appear in 60 seconds.**

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white">
  <img alt="Flask" src="https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white">
  <img alt="Status" src="https://img.shields.io/badge/status-prototype-ff6b35">
  <img alt="Made in Bharat" src="https://img.shields.io/badge/Made%20for-Bharat%20%F0%9F%87%AE%F0%9F%87%B3-138808">
</p>

---

## The problem

India runs **3,000+ government welfare schemes** — PM-KISAN, Ayushman Bharat, MUDRA, widow pensions, scholarships — worth lakhs of crores. Yet **fewer than 30% of eligible citizens ever claim them**, because:

- They don't know the schemes exist.
- Forms are in English, often online-only.
- Eligibility rules are buried in 40-page PDFs.
- Local middlemen charge ₹500–2,000 to "help" apply — for schemes that are **100% free**.

> A farmer's widow in UP is entitled to ₹3 lakh under PM Jeevan Jyoti Bima Yojana — and may never know.

**Sahay** closes that gap: describe your situation in plain Hindi/Hinglish/English (typed or spoken), and it instantly matches you to the schemes you qualify for, with eligibility, documents, fraud warnings, and a **deep link straight to the official application page**.

---

## What it does

| Feature | Description |
|---|---|
| 🗣️ **Natural-language matching** | Free-text or voice input in Hindi / Hinglish / English. A signal-based matcher maps phrases like *"pati ki mrityu"* → widow, *"chota dukaan, loan chahiye"* → MUDRA. |
| 🎯 **Ranked, explained results** | Every scheme card shows a fit score and a plain-language *"why this was suggested."* |
| 🔗 **Deep-linked apply pages** | Cards link directly to the real registration page (e.g. PM-KISAN *New Farmer Registration*, Ayushman *beneficiary* portal) — not just the homepage. |
| 🛡️ **Middleman-fraud protection** | A persistent advisory plus per-scheme risk pills: *all central schemes are FREE — apply only via the official portal, your bank, Gram Panchayat, or CSC.* |
| 📄 **Document Readiness Checker** | Aggregates every document across your matched schemes, tracks a progress ring, and tells you which schemes you can apply for *right now*. |
| 📸 **Document verification (mock OCR)** | Upload a photo of a document — Sahay detects its type and flags blurry/oversized scans. |
| 🧠 **Teach-a-scheme (live RAG)** | Drop an official scheme PDF; it's TF-IDF indexed instantly and quoted live via the source-citation modal. |
| 💰 **Animated benefit counter** | Sums the indicative annual ₹ value unlocked across all matches. |
| 📋 **Quick-form mode** | A structured eligibility engine for exact matches instead of keyword guesses. |
| 🌗 **Polished UX** | Dark/light theme, animated background, confetti, WhatsApp/copy/print share, text-to-speech read-aloud. |

---

## Quick start

### Option A — Python
```bash
pip install -r requirements.txt
python server.py
# open http://localhost:5000  (Chrome or Edge)
```

### Option B — Docker
```bash
docker compose up --build
# open http://localhost:5000
```

> **Optional — real Hindi/Tamil/Bengali translation via Claude:**
> Set `ANTHROPIC_API_KEY` before starting. Without it, Sahay runs fully offline using the built-in keyword matcher and templated responses.
> ```powershell
> $env:ANTHROPIC_API_KEY = "sk-ant-..."   # PowerShell
> python server.py
> ```

---

## 60-second demo flow

1. Click a **persona** — Ramesh (Bihar farmer), Lakshmi (UP widow), Priya (gig worker), Irfan (carpenter).
2. Watch the thinking overlay → confetti → animated ₹ counter.
3. Read the dark **fraud-advisory** banner.
4. Expand a card → hit the green **"Apply online — official registration"** button.
5. Click **"View official source"** → see the actual paragraph retrieved from the scheme's PDF.
6. Toggle theme / language, or tap 🎙 and **speak** your situation.

---

## Architecture

```
┌────────────────────────┐     POST /api/chat            ┌──────────────────────────┐
│  Single-page web UI     │ ───────────────────────────▶ │  Flask backend (server.py) │
│  templates/ + static/   │                               │                            │
│  voice · theme · RAG UI │ ◀─────────────────────────── │  • signal-based matcher    │
└────────────────────────┘     ranked matches + why       │  • TF-IDF source retrieval │
                                                          │  • optional Claude enrich  │
                                                          └────────────┬───────────────┘
                                                                       │
                                              schemes.json (25 schemes) + sources/ (PDFs)
```

**API routes:** `/` · `/api/schemes` · `/api/chat` · `/api/match-form` · `/api/personas` · `/api/scheme-source/<id>` · `/api/upload-pdf`

---

## What's inside

```
server.py            Flask backend — matcher + TF-IDF RAG + 7 API routes
schemes.json         25 real central welfare schemes (eligibility, docs, apply links)
sources/             4 official scheme-guideline excerpts (indexed for citations)
templates/index.html single-page UI
static/app.js        chat, voice, theme, filters, doc-checker, confetti
static/style.css     saffron/green themed, animated, dark-mode UI
Dockerfile           gunicorn production image
docker-compose.yml   one-command run
requirements.txt     Flask · pypdf · anthropic · gunicorn
```

---

## Roadmap (production vision)

- **Bhashini API** for all 22 official languages.
- **DigiLocker** integration to auto-fill applications and verify documents.
- **WhatsApp bot** for last-mile distribution to feature phones.
- Live scraping of **myScheme.gov.in** and ministry portals for 3,000+ schemes.

---

## Disclaimer

A hackathon prototype. The 25 schemes and ₹ values are curated, indicative headline figures — real eligibility and benefit amounts depend on tier, state, and category. Always confirm on the official portal. **Every scheme listed is free to apply for; never pay an agent.**

<p align="center"><em>Har scheme, har Bharatiya tak.</em> 🇮🇳</p>
