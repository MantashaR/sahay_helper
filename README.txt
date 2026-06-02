Sahay — AI Welfare Navigator for Bharat
========================================

Helps Indian citizens discover government welfare schemes via voice/text
in Hindi, English, Tamil, or Bengali — with built-in middleman fraud
protection, document readiness checking, and PDF source citations.


HOW TO RUN
==========

You have TWO options. Pick whichever fits your machine.


OPTION A — DOCKER  (easiest, works the same on Windows / Mac / Linux)
---------------------------------------------------------------------

PREREQUISITE:  Docker Desktop installed and running
               https://www.docker.com/products/docker-desktop/

STEPS:
  1. Unzip this file. Open a terminal inside the unzipped folder.

  2. Build and start:

         docker compose up --build

     First build takes 1-2 minutes (downloads Python + installs deps).
     Subsequent runs are instant.

  3. Open  http://localhost:5000  in Chrome or Edge.

STOP:           Ctrl+C, then  docker compose down
RESTART LATER:  docker compose up -d


OPTION B — PYTHON  (if you don't want to install Docker)
--------------------------------------------------------

PREREQUISITE:  Python 3.10 or later
               https://www.python.org/downloads/

STEPS:
  1. Unzip this file. Open a terminal inside the unzipped folder.

  2. Install dependencies:

         pip install -r requirements.txt

  3. Start the server:

         python server.py

  4. Open  http://localhost:5000  in Chrome or Edge.

STOP:  Ctrl+C in the terminal


OPTIONAL — ENABLE REAL HINDI / TAMIL / BENGALI TRANSLATION
==========================================================
By default, non-English responses use offline templates. To enable real
Claude-powered translation, set the ANTHROPIC_API_KEY environment variable
before starting the server.

Docker:
    Edit docker-compose.yml, uncomment the ANTHROPIC_API_KEY line, paste
    your key, then run  docker compose up --build  again.

Python (Windows PowerShell):
    $env:ANTHROPIC_API_KEY = "sk-ant-..."
    python server.py

Python (Mac/Linux):
    export ANTHROPIC_API_KEY="sk-ant-..."
    python server.py


DEMO FLOW (60 seconds)
======================
  1. Click any persona button (Ramesh / Lakshmi / Priya / Irfan)
  2. Watch the thinking overlay -> confetti -> animated rupees counter
  3. Dark fraud-advisory banner appears: "all schemes are FREE, never pay agents"
  4. Click "View official source" on any card -> see the actual paragraph
     retrieved from the official scheme PDF
  5. Toggle theme, language (Hindi / EN / Tamil / Bengali), or speak the input
  6. Switch to "Quick form" tab for the structured eligibility engine


TROUBLESHOOTING
===============
- "Port 5000 already in use" -> another app is using port 5000.
  Docker:  docker run -p 8080:5000 sahay:latest   then open localhost:8080
  Python:  edit server.py last line, change port to 5001

- Voice input button does nothing -> only works in Chrome / Edge (Web Speech API)

- Hindi/Tamil/Bengali summaries feel canned -> you haven't set ANTHROPIC_API_KEY
  (see the optional section above)

- "Docker daemon not running" -> start Docker Desktop, wait 30 seconds


WHAT'S INSIDE
=============
  server.py           Flask backend + matcher + RAG + 6 API endpoints
  schemes.json        25 central govt welfare schemes (curated)
  sources/            4 official scheme guideline excerpts (TF-IDF indexed)
  templates/          single-page UI
  static/             CSS + JS (theme, voice, confetti, etc.)
  Dockerfile          gunicorn production image
  docker-compose.yml  one-command run
  requirements.txt    Flask, pypdf, anthropic, gunicorn


License: prototype for hackathon use.
