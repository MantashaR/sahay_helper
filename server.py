"""
Sahay — AI Welfare Navigator backend.

Runs offline out-of-the-box with keyword + TF-IDF style scoring.
If ANTHROPIC_API_KEY is set in the environment, also calls Claude to
extract a structured citizen profile from free-text/voice input.
"""

import io
import json
import math
import os
import re
import uuid
from collections import Counter, defaultdict
from pathlib import Path

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).parent
SCHEMES_PATH = BASE_DIR / "schemes.json"
SOURCES_DIR = BASE_DIR / "sources"

app = Flask(__name__, static_folder="static", template_folder="templates")

with SCHEMES_PATH.open(encoding="utf-8") as f:
    SCHEMES = json.load(f)


# ---------------------------------------------------------------------------
# Per-scheme metadata: category (for filter chips) + estimated annual ₹ value
# (for the "total benefit unlocked" animated counter). Values are *indicative*
# headline figures used for the demo — real benefit depends on tier/region.
# ---------------------------------------------------------------------------

CATEGORIES = {
    "pm-kisan":               "Agriculture",
    "pm-kisan-maan-dhan":     "Pension",
    "pmfby":                  "Agriculture",
    "soil-health-card":       "Agriculture",
    "ayushman-bharat":        "Health",
    "janani-suraksha":        "Health",
    "pmjjby":                 "Insurance",
    "pmsby":                  "Insurance",
    "apy":                    "Pension",
    "widow-pension":          "Pension",
    "old-age-pension":        "Pension",
    "ssy":                    "Women & Child",
    "mahila-samman":          "Women & Child",
    "shaadi-shagun":          "Women & Child",
    "ujjwala":                "Women & Child",
    "pmay-g":                 "Housing",
    "pmay-u":                 "Housing",
    "mudra":                  "Loans & Business",
    "stand-up-india":         "Loans & Business",
    "pm-vishwakarma":         "Loans & Business",
    "post-matric-scholarship":"Education",
    "mgnrega":                "Employment",
    "e-shram":                "Employment",
    "jan-dhan":               "Banking",
    "kvp":                    "Food & Ration",
}

EST_VALUE_INR = {
    "pm-kisan":               6000,
    "pm-kisan-maan-dhan":     36000,
    "pmfby":                  50000,
    "soil-health-card":       0,
    "ayushman-bharat":        500000,
    "janani-suraksha":        1400,
    "pmjjby":                 200000,
    "pmsby":                  200000,
    "apy":                    60000,
    "widow-pension":          6000,
    "old-age-pension":        6000,
    "ssy":                    25000,
    "mahila-samman":          30000,
    "shaadi-shagun":          51000,
    "ujjwala":                3600,
    "pmay-g":                 130000,
    "pmay-u":                 267000,
    "mudra":                  100000,
    "stand-up-india":         1000000,
    "pm-vishwakarma":         15000,
    "post-matric-scholarship":24000,
    "mgnrega":                30000,
    "e-shram":                200000,
    "jan-dhan":               200000,
    "kvp":                    24000,
}

# Schemes where citizens are commonly defrauded by agents/middlemen. Every
# central govt scheme below is FREE to apply — but agents routinely charge
# ₹500-5,000 to "help". The risk level signals where vigilance matters most.
MIDDLEMAN_RISK = {
    "pm-kisan":               "high",   # rampant — village agents charge ₹200-500
    "pmay-g":                 "high",
    "pmay-u":                 "high",
    "ayushman-bharat":        "high",   # fake "card-makers" outside hospitals
    "ujjwala":                "high",
    "mudra":                  "high",   # NBFC/agent loan scams
    "stand-up-india":         "high",
    "pm-vishwakarma":         "medium",
    "widow-pension":          "high",
    "old-age-pension":        "high",
    "post-matric-scholarship":"medium",
    "e-shram":                "medium",
    "jan-dhan":               "low",
    "pmjjby":                 "low",
    "pmsby":                  "low",
    "apy":                    "low",
    "ssy":                    "low",
    "mahila-samman":          "low",
    "shaadi-shagun":          "medium",
    "kvp":                    "medium",
    "pmfby":                  "medium",
    "soil-health-card":       "low",
    "janani-suraksha":        "low",
    "mgnrega":                "medium",
    "pm-kisan-maan-dhan":     "high",
}

# Deep links straight to the apply / new-registration / beneficiary page,
# rather than the scheme's marketing homepage. Where no stable deep link
# exists (account opened at a bank/post-office/Gram-Panchayat counter), we
# fall back to source_url and the UI labels it as the official portal.
APPLY_URL = {
    "pm-kisan":                "https://pmkisan.gov.in/RegistrationFormNew.aspx",   # New Farmer Registration
    "ayushman-bharat":         "https://beneficiary.nha.gov.in/",                   # Check eligibility + download card
    "pmjjby":                  "https://www.jansuraksha.gov.in/Forms-PMJJBY.aspx",  # enrolment form
    "pmsby":                   "https://www.jansuraksha.gov.in/Forms-PMSBY.aspx",   # enrolment form
    "apy":                     "https://enps.nsdl.com/eNPS/ApySubRegistration.html",# APY subscriber registration
    "ujjwala":                 "https://www.pmuy.gov.in/ujjwala2.0.html",           # new connection
    "mudra":                   "https://www.udyamimitra.in/",                       # online loan application
    "stand-up-india":          "https://www.standupmitra.in/Login/Register",        # borrower registration
    "pm-vishwakarma":          "https://pmvishwakarma.gov.in/",                     # CSC-assisted registration
    "post-matric-scholarship": "https://scholarships.gov.in/fresh/newstdRegfrmInstruction",  # NSP new registration
    "jan-dhan":                "https://pmjdy.gov.in/account",                      # account opening
    "e-shram":                 "https://register.eshram.gov.in/",                   # self-registration
    "pmfby":                   "https://pmfby.gov.in/farmerLogin",                  # Farmer Corner
    "pmay-g":                  "https://pmayg.nic.in/netiayHome/home.aspx",
    "pmay-u":                  "https://pmaymis.gov.in/",
    "soil-health-card":        "https://soilhealth.dac.gov.in/",
    "pm-kisan-maan-dhan":      "https://maandhan.in/",
    # Counter-based (bank / post office / hospital / Gram Panchayat) — no online apply:
    "widow-pension":           "https://nsap.nic.in/",
    "old-age-pension":         "https://nsap.nic.in/",
    "ssy":                     "https://www.nsiindia.gov.in/InternalPage.aspx?Id_Pk=89",
    "shaadi-shagun":           "https://maef.nic.in/",
    "janani-suraksha":         "https://nhm.gov.in/index1.php?lang=1&level=3&sublinkid=841&lid=309",
    "mgnrega":                 "https://nrega.nic.in/",
    "mahila-samman":           "https://www.indiapost.gov.in/",
    "kvp":                     "https://www.indiapost.gov.in/Financial/Pages/Content/Kisan-Vikas-Patra.aspx",
}

# Schemes where the citizen applies online directly (deep link is a real
# application form) vs. at a physical counter (deep link is the info portal).
ONLINE_APPLY = {
    "pm-kisan", "ayushman-bharat", "pmjjby", "pmsby", "apy", "ujjwala",
    "mudra", "stand-up-india", "post-matric-scholarship", "jan-dhan",
    "e-shram", "pmfby",
}

OFFICIAL_FEE_INR = 0  # every central scheme listed is FREE to apply

# Inject metadata so every consumer (api/schemes, api/chat) sees it.
for _s in SCHEMES:
    _s["category"]            = CATEGORIES.get(_s["id"], "General")
    _s["est_value_inr"]       = EST_VALUE_INR.get(_s["id"], 0)
    _s["middleman_risk"]      = MIDDLEMAN_RISK.get(_s["id"], "medium")
    _s["apply_url"]           = APPLY_URL.get(_s["id"], _s.get("source_url"))
    _s["online_apply"]        = _s["id"] in ONLINE_APPLY
    _s["official_fee_inr"]    = OFFICIAL_FEE_INR
    _s["fraud_warning"]       = (
        "Applying for this scheme is 100% FREE. "
        "Do NOT pay any agent, dealer, or 'middleman' — apply only through the "
        "official portal, your bank, Gram Panchayat, CSC (Common Service Centre), "
        "or the ministry helpline."
    )


# ---------------------------------------------------------------------------
# Keyword-based matcher (offline, no dependencies)
# ---------------------------------------------------------------------------

# Maps surface words (Hindi/Hinglish/English) to canonical "signals" that
# can boost specific schemes. Keep small + hand-curated for explainability.
SIGNAL_MAP = {
    # Farming
    "farmer": ["farmer", "agriculture"],
    "kisan": ["farmer", "agriculture"],
    "kheti": ["farmer", "agriculture"],
    "khet": ["farmer", "agriculture"],
    "fasal": ["farmer", "agriculture", "crop"],
    "crop": ["farmer", "crop"],
    "land": ["farmer", "land"],
    "zameen": ["farmer", "land"],
    "acre": ["farmer", "land"],
    "hectare": ["farmer", "land"],
    "drought": ["crop_loss"],
    "flood": ["crop_loss"],
    "soil": ["soil"],
    "mitti": ["soil"],
    "fertiliser": ["soil"],
    "khaad": ["soil"],

    # Women / girls
    "woman": ["woman"],
    "women": ["woman"],
    "mahila": ["woman"],
    "wife": ["woman"],
    "patni": ["woman"],
    "girl": ["girl"],
    "daughter": ["girl"],
    "beti": ["girl"],
    "ladki": ["girl"],
    "pregnant": ["pregnant"],
    "pregnancy": ["pregnant"],
    "garbhvati": ["pregnant"],
    "baby": ["pregnant", "child"],
    "newborn": ["pregnant", "child"],
    "shaadi": ["marriage"],
    "marriage": ["marriage"],

    # Age / family stage
    "old": ["senior"],
    "senior": ["senior"],
    "elderly": ["senior"],
    "buzurg": ["senior"],
    "pension": ["pension"],
    "retire": ["pension"],
    "retirement": ["pension"],
    "widow": ["widow"],
    "vidhwa": ["widow"],
    "husband died": ["widow"],
    "husband death": ["widow"],
    "pati ki mrityu": ["widow"],
    "pati ka dehant": ["widow"],
    "pati nahi": ["widow"],
    "mrityu ho gayi": ["widow"],
    "dehant ho gaya": ["widow"],

    # Caste / community
    "sc": ["sc_st"],
    "st": ["sc_st"],
    "dalit": ["sc_st"],
    "tribal": ["sc_st"],
    "adivasi": ["sc_st"],
    "obc": ["obc"],
    "minority": ["minority"],
    "muslim": ["minority"],
    "christian": ["minority"],
    "sikh": ["minority"],

    # Money / business
    "loan": ["loan"],
    "business": ["loan", "business"],
    "udyog": ["loan", "business"],
    "dukaan": ["loan", "business"],
    "shop": ["loan", "business"],
    "startup": ["loan", "business"],
    "bank": ["bank"],
    "account": ["bank"],
    "khata": ["bank"],
    "savings": ["bank", "savings"],

    # Health
    "ill": ["health"],
    "sick": ["health"],
    "bimari": ["health"],
    "hospital": ["health"],
    "diabetes": ["health"],
    "cancer": ["health"],
    "surgery": ["health"],
    "treatment": ["health"],
    "medicine": ["health"],
    "ilaaj": ["health"],

    # Work / labour
    "labour": ["worker"],
    "labourer": ["worker"],
    "worker": ["worker"],
    "mazdoor": ["worker"],
    "kaam": ["worker"],
    "job": ["worker"],
    "unemployed": ["worker"],
    "gig": ["worker", "unorganised"],
    "driver": ["worker", "unorganised"],
    "rickshaw": ["worker", "unorganised"],
    "construction": ["worker", "unorganised"],
    "domestic": ["worker", "unorganised"],
    "vendor": ["worker", "unorganised"],
    "artisan": ["artisan"],
    "carpenter": ["artisan"],
    "barhai": ["artisan"],
    "lohar": ["artisan"],
    "blacksmith": ["artisan"],
    "tailor": ["artisan"],
    "darzi": ["artisan"],
    "potter": ["artisan"],
    "kumhar": ["artisan"],
    "weaver": ["artisan"],

    # Housing
    "house": ["housing"],
    "ghar": ["housing"],
    "makaan": ["housing"],
    "home": ["housing"],
    "slum": ["housing", "urban_poor"],
    "homeless": ["housing"],
    "kutcha": ["housing"],

    # Education
    "student": ["education"],
    "study": ["education"],
    "padhai": ["education"],
    "padhna": ["education"],
    "college": ["education"],
    "school": ["education"],
    "scholarship": ["education"],
    "fees": ["education"],
    "tuition": ["education"],

    # Cooking / fuel
    "lpg": ["lpg"],
    "gas": ["lpg"],
    "cylinder": ["lpg"],
    "cooking": ["lpg"],
    "chulha": ["lpg"],

    # Food / ration
    "food": ["food"],
    "ration": ["food"],
    "anna": ["food"],
    "khaana": ["food"],
    "wheat": ["food"],
    "rice": ["food"],
    "gehu": ["food"],
    "chawal": ["food"],

    # Income state
    "poor": ["bpl"],
    "garib": ["bpl"],
    "bpl": ["bpl"],
    "below poverty": ["bpl"],
    "low income": ["bpl"],

    # Insurance
    "insurance": ["insurance"],
    "bima": ["insurance"],
    "accident": ["accident"],
    "death": ["insurance", "widow"],

    # ---- Native-script keywords (Hindi Devanagari) ---------------------------
    # Chrome's hi-IN speech recogniser returns Devanagari, not romanised text,
    # so these are essential for Hindi *voice* input to match anything.
    "किसान": ["farmer", "agriculture"],
    "खेती": ["farmer", "agriculture"],
    "खेत": ["farmer", "land"],
    "फसल": ["farmer", "crop"],
    "जमीन": ["farmer", "land"],
    "ज़मीन": ["farmer", "land"],
    "महिला": ["woman"],
    "औरत": ["woman"],
    "पत्नी": ["woman"],
    "बेटी": ["girl"],
    "लड़की": ["girl"],
    "गर्भवती": ["pregnant"],
    "गर्भ": ["pregnant"],
    "शादी": ["marriage"],
    "विवाह": ["marriage"],
    "बुजुर्ग": ["senior"],
    "बूढ़ा": ["senior"],
    "बुढ़ापा": ["senior", "pension"],
    "पेंशन": ["pension"],
    "विधवा": ["widow"],
    "मजदूर": ["worker"],
    "मज़दूर": ["worker"],
    "काम": ["worker"],
    "बेरोजगार": ["worker"],
    "बेरोज़गार": ["worker"],
    "कारीगर": ["artisan"],
    "बढ़ई": ["artisan"],
    "दर्जी": ["artisan"],
    "लोहार": ["artisan"],
    "कुम्हार": ["artisan"],
    "बुनकर": ["artisan"],
    "लोन": ["loan"],
    "कर्ज": ["loan"],
    "कर्ज़ा": ["loan"],
    "व्यापार": ["loan", "business"],
    "व्यवसाय": ["loan", "business"],
    "दुकान": ["loan", "business"],
    "बैंक": ["bank"],
    "खाता": ["bank"],
    "बीमारी": ["health"],
    "बीमार": ["health"],
    "इलाज": ["health"],
    "अस्पताल": ["health"],
    "मकान": ["housing"],
    "घर": ["housing"],
    "छात्र": ["education"],
    "विद्यार्थी": ["education"],
    "पढ़ाई": ["education"],
    "स्कूल": ["education"],
    "कॉलेज": ["education"],
    "छात्रवृत्ति": ["education"],
    "गैस": ["lpg"],
    "सिलेंडर": ["lpg"],
    "राशन": ["food"],
    "गरीब": ["bpl"],
    "गरीबी": ["bpl"],
    "बीमा": ["insurance"],
    "दुर्घटना": ["accident"],

    # ---- Bengali (bn-IN) -----------------------------------------------------
    "কৃষক": ["farmer", "agriculture"],
    "চাষ": ["farmer", "agriculture"],
    "মহিলা": ["woman"],
    "মেয়ে": ["girl"],
    "বিধবা": ["widow"],
    "বয়স্ক": ["senior"],
    "পেনশন": ["pension"],
    "ঋণ": ["loan"],
    "ব্যবসা": ["loan", "business"],
    "ব্যাংক": ["bank"],
    "ছাত্র": ["education"],
    "পড়াশোনা": ["education"],
    "বাড়ি": ["housing"],
    "স্বাস্থ্য": ["health"],
    "অসুস্থ": ["health"],
    "শ্রমিক": ["worker"],
    "গরিব": ["bpl"],

    # ---- Tamil (ta-IN) -------------------------------------------------------
    "விவசாயி": ["farmer", "agriculture"],
    "விவசாயம்": ["farmer", "agriculture"],
    "பெண்": ["woman"],
    "பெண்குழந்தை": ["girl"],
    "விதவை": ["widow"],
    "முதியோர்": ["senior"],
    "ஓய்வூதியம்": ["pension"],
    "கடன்": ["loan"],
    "வணிகம்": ["loan", "business"],
    "வங்கி": ["bank"],
    "மாணவர்": ["education"],
    "படிப்பு": ["education"],
    "வீடு": ["housing"],
    "உடல்நலம்": ["health"],
    "மருத்துவம்": ["health"],
    "தொழிலாளி": ["worker"],
    "ஏழை": ["bpl"],
}

# Map signals -> list of scheme IDs that strongly match. Multiple signals
# can hit the same scheme, score adds up.
SIGNAL_TO_SCHEMES = {
    "farmer":      ["pm-kisan", "pm-kisan-maan-dhan", "pmfby", "soil-health-card"],
    "agriculture": ["pm-kisan", "soil-health-card", "pmfby"],
    "land":        ["pm-kisan", "pmfby", "pm-kisan-maan-dhan"],
    "crop":        ["pmfby", "soil-health-card"],
    "crop_loss":   ["pmfby"],
    "soil":        ["soil-health-card"],

    "woman":       ["ujjwala", "mahila-samman", "stand-up-india", "jan-dhan"],
    "girl":        ["ssy", "shaadi-shagun", "post-matric-scholarship", "mahila-samman"],
    "pregnant":    ["janani-suraksha", "ayushman-bharat"],
    "marriage":    ["shaadi-shagun", "ssy"],

    "senior":      ["old-age-pension", "ayushman-bharat", "apy", "pm-kisan-maan-dhan"],
    "pension":     ["apy", "old-age-pension", "pm-kisan-maan-dhan", "widow-pension"],
    "widow":       ["widow-pension", "pmjjby", "ayushman-bharat", "jan-dhan"],

    "sc_st":       ["post-matric-scholarship", "stand-up-india"],
    "obc":         ["post-matric-scholarship"],
    "minority":    ["shaadi-shagun"],

    "loan":        ["mudra", "stand-up-india"],
    "business":    ["mudra", "stand-up-india", "pm-vishwakarma"],
    "bank":        ["jan-dhan", "pmjjby", "pmsby", "apy"],
    "savings":     ["ssy", "mahila-samman", "jan-dhan"],

    "health":      ["ayushman-bharat", "pmsby"],
    "insurance":   ["pmjjby", "pmsby", "ayushman-bharat", "pmfby"],
    "accident":    ["pmsby", "e-shram"],

    "worker":      ["e-shram", "mgnrega", "apy"],
    "unorganised": ["e-shram", "apy", "pmsby"],
    "artisan":     ["pm-vishwakarma", "mudra"],

    "housing":     ["pmay-g", "pmay-u"],
    "urban_poor":  ["pmay-u"],

    "education":   ["post-matric-scholarship", "shaadi-shagun", "ssy"],

    "lpg":         ["ujjwala"],

    "food":        ["kvp"],  # AAY scheme id
    "bpl":         ["kvp", "old-age-pension", "widow-pension", "ayushman-bharat", "pmay-g", "ujjwala"],
}


# Latin + Devanagari (Hindi) + Bengali + Tamil so spoken/typed input in any of
# the four supported languages tokenizes correctly (Chrome returns native script
# for hi-IN / ta-IN / bn-IN voice input).
WORD_RE = re.compile(r"[a-zA-Zऀ-ॿঀ-৿஀-௿]+")


def extract_signals(text):
    """Turn raw user text into a counted bag of canonical signals + age + gender hints."""
    lower = text.lower()
    signals = Counter()

    # Multi-word phrases first (so "husband died" → widow before tokenising kills it)
    for phrase, sigs in SIGNAL_MAP.items():
        if " " in phrase and phrase in lower:
            for s in sigs:
                signals[s] += 2  # phrases score higher

    tokens = WORD_RE.findall(lower)
    for tok in tokens:
        sigs = SIGNAL_MAP.get(tok)
        if sigs:
            for s in sigs:
                signals[s] += 1

    # Age extraction (e.g. "58 years", "umar 65", "60 saal")
    age = None
    age_match = re.search(r"\b(\d{1,3})\s*(years?|saal|year old|saal ka|saal ki)\b", lower)
    if age_match:
        age = int(age_match.group(1))
    else:
        # Fallback: any plausible age number 10-99 near "age/umar"
        m2 = re.search(r"(age|umar)[^\d]{0,5}(\d{2,3})", lower)
        if m2:
            age = int(m2.group(2))

    if age:
        if age >= 60:
            signals["senior"] += 3
        if 40 <= age <= 79 and "widow" in signals:
            signals["widow"] += 1  # reinforcement

    # Acreage / land size
    land_match = re.search(r"(\d+(?:\.\d+)?)\s*(acre|hectare|bigha)", lower)
    if land_match:
        signals["farmer"] += 2
        signals["land"] += 2

    return signals, age


def match_schemes(text, top_k=8):
    signals, age = extract_signals(text)
    scores = Counter()

    # Signal-based boosts
    for sig, weight in signals.items():
        for scheme_id in SIGNAL_TO_SCHEMES.get(sig, []):
            scores[scheme_id] += weight * 2

    # Tag-based fuzzy match against every scheme's tags
    tokens = set(WORD_RE.findall(text.lower()))
    for scheme in SCHEMES:
        for tag in scheme.get("tags", []):
            if tag in tokens or any(tag in t for t in tokens):
                scores[scheme["id"]] += 1

    # Build results
    by_id = {s["id"]: s for s in SCHEMES}
    ranked = scores.most_common(top_k)

    matches = []
    for scheme_id, score in ranked:
        if score <= 0:
            continue
        s = by_id[scheme_id]
        matches.append({
            **s,
            "score": score,
            "why": build_why(s, signals, age),
        })

    return matches, dict(signals), age


def build_why(scheme, signals, age):
    """Human-readable explanation of *why* this scheme was suggested."""
    reasons = []
    tag_set = set(scheme.get("tags", []))

    if "farmer" in signals and tag_set & {"farmer", "kisan", "agriculture"}:
        reasons.append("you mentioned farming / land")
    if "woman" in signals and tag_set & {"woman", "mahila", "girl"}:
        reasons.append("scheme is for women")
    if "girl" in signals and tag_set & {"girl", "beti", "ladki"}:
        reasons.append("scheme is for the girl child / daughters")
    if "senior" in signals and tag_set & {"old age", "senior", "pension", "buzurg"}:
        reasons.append("scheme is for senior citizens")
    if "widow" in signals and "widow" in tag_set:
        reasons.append("scheme is for widows")
    if "health" in signals and tag_set & {"health", "hospital", "insurance"}:
        reasons.append("you mentioned a health / medical need")
    if "loan" in signals and "loan" in tag_set:
        reasons.append("you asked about a loan / business")
    if "housing" in signals and tag_set & {"house", "housing", "ghar"}:
        reasons.append("you mentioned needing a house")
    if "education" in signals and tag_set & {"education", "scholarship", "student"}:
        reasons.append("you mentioned studies / a student")
    if "lpg" in signals and tag_set & {"lpg", "gas", "cylinder"}:
        reasons.append("you mentioned cooking gas")
    if "bpl" in signals or "worker" in signals:
        reasons.append("targets low-income / unorganised families")
    if age and age >= 60 and "old age" in tag_set:
        reasons.append(f"you are {age} — qualifies as a senior citizen")

    if not reasons:
        reasons.append("matches keywords in your description")
    return reasons


# ---------------------------------------------------------------------------
# Optional Claude enrichment
# ---------------------------------------------------------------------------

LANG_NAME = {
    "en-IN": "English",
    "hi-IN": "Hindi (Devanagari script)",
    "ta-IN": "Tamil",
    "bn-IN": "Bengali",
}

# Offline summary templates per language (used when no API key).
OFFLINE_SUMMARY = {
    "en-IN": "Based on what you told me, I found {n} schemes that may apply to you. The strongest match is **{top}**. Every one is FREE — tap any card for full details.",
    "hi-IN": "आपकी जानकारी के आधार पर मुझे {n} योजनाएँ मिली हैं जो आप पर लागू हो सकती हैं। सबसे बेहतर मिलान है — **{top}**। हर योजना मुफ़्त है — किसी एजेंट को पैसे न दें।",
    "ta-IN": "நீங்கள் தந்த தகவலின் அடிப்படையில் {n} திட்டங்கள் கிடைத்துள்ளன. சிறந்த பொருத்தம் — **{top}**. அனைத்தும் இலவசம் — யாருக்கும் கட்டணம் தர வேண்டாம்.",
    "bn-IN": "আপনার তথ্যের ভিত্তিতে আমি {n} টি প্রকল্প পেয়েছি যা আপনার জন্য প্রযোজ্য হতে পারে। সবচেয়ে ভালো মিল — **{top}**। সবগুলোই বিনামূল্যে — কাউকে টাকা দেবেন না।",
}
OFFLINE_NOMATCH = {
    "en-IN": "I couldn't confidently match a scheme yet. Try adding details — age, occupation, family situation, income, or specific needs.",
    "hi-IN": "मैं अभी कोई योजना मिला नहीं पाया। कृपया अधिक जानकारी दें — उम्र, काम, परिवार, या ज़रूरत।",
    "ta-IN": "சரியான பொருத்தம் கண்டுபிடிக்க முடியவில்லை. தயவு செய்து கூடுதல் விவரங்கள் தரவும்.",
    "bn-IN": "এখনও কোনো সঠিক প্রকল্প পাইনি। দয়া করে আরও বিস্তারিত তথ্য দিন।",
}


def claude_enrich(user_text, lang="en-IN"):
    """If ANTHROPIC_API_KEY is set, ask Claude for a summary in target language."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic  # lazy import
    except ImportError:
        return None

    lang_name = LANG_NAME.get(lang, "English")
    client = anthropic.Anthropic(api_key=api_key)
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=(
                "You help Indian citizens discover government welfare schemes. "
                "Given the user's description (which may mix Hindi/English/regional), reply "
                f"in 2-3 short, warm sentences IN {lang_name}: (1) summarise their situation, "
                "(2) reassure them how many schemes likely apply, (3) remind them all schemes "
                "are FREE and they should never pay agents/middlemen. "
                "Do not list specific schemes — the app shows those separately. "
                "Use simple, everyday words an unschooled villager would understand."
            ),
            messages=[{"role": "user", "content": user_text}],
        )
        return msg.content[0].text.strip()
    except Exception as exc:  # noqa: BLE001
        return f"(Claude enrichment skipped: {exc})"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/schemes")
def list_schemes():
    return jsonify(SCHEMES)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    text = (data.get("message") or "").strip()
    if not text:
        return jsonify({"error": "empty message"}), 400

    lang = data.get("language") or "en-IN"
    matches, signals, age = match_schemes(text)
    matches = _attach_sources(matches, text)
    ai_summary = claude_enrich(text, lang=lang)

    # Fallback summary if no Claude key — pick template for chosen language
    if not ai_summary:
        if matches:
            tpl = OFFLINE_SUMMARY.get(lang, OFFLINE_SUMMARY["en-IN"])
            ai_summary = tpl.format(n=len(matches), top=matches[0]["name"])
        else:
            ai_summary = OFFLINE_NOMATCH.get(lang, OFFLINE_NOMATCH["en-IN"])

    # Middleman risk summary across matched schemes
    high_risk = [m["name"] for m in matches if m.get("middleman_risk") == "high"]
    fraud_advisory = {
        "headline": "All these schemes are FREE — never pay any agent.",
        "detail": (
            f"{len(high_risk)} of your {len(matches)} matches are commonly targeted by "
            "fraud agents. Apply only via the official portal, your bank, Gram Panchayat, "
            "or CSC (Common Service Centre)."
        ) if high_risk else (
            "Apply only via the official portal, your bank, Gram Panchayat, or CSC."
        ),
        "high_risk_schemes": high_risk,
    }

    return jsonify({
        "summary": ai_summary,
        "matches": matches,
        "signals_detected": signals,
        "age_detected": age,
        "fraud_advisory": fraud_advisory,
        "language": lang,
    })


# ---------------------------------------------------------------------------
# PDF-to-Knowledge: TF-IDF over pre-bundled scheme guidelines (and uploads)
# ---------------------------------------------------------------------------

# Maps source filename → list of scheme IDs the source is relevant to.
SOURCE_SCHEME_MAP = {
    "pm-kisan-guidelines.txt":   ["pm-kisan", "pm-kisan-maan-dhan", "pmfby", "soil-health-card"],
    "ayushman-bharat-pmjay.txt": ["ayushman-bharat", "janani-suraksha"],
    "widow-pension-nsap.txt":    ["widow-pension", "old-age-pension"],
    "ujjwala-yojana.txt":        ["ujjwala"],
}

# NOTE: tokenize() below reuses the multilingual WORD_RE defined above. (A
# previous ASCII-only redefinition here silently broke Hindi/Tamil/Bengali
# tokenization for the signal matcher — keep it multilingual.)

STOPWORDS = set("""
a an and the of in on at to from for by with as is are was were be been being
this that these those it its he she they them his her their our your you we us
or but not no if when which who whom whose what why how
also can may shall will should would could
""".split())


def tokenize(text):
    return [w.lower() for w in WORD_RE.findall(text) if len(w) > 2 and w.lower() not in STOPWORDS]


class TFIDFIndex:
    """Tiny in-memory TF-IDF retriever. Chunks docs by paragraph."""

    def __init__(self):
        self.chunks = []   # list of dicts: {id, doc_id, doc_name, page, text, tokens, tf}
        self.df = Counter()
        self.N = 0

    def add_document(self, doc_id, doc_name, text):
        # Split into paragraphs; treat each blank-line-separated block as a chunk.
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        for i, para in enumerate(paragraphs, start=1):
            tokens = tokenize(para)
            if not tokens:
                continue
            tf = Counter(tokens)
            chunk = {
                "id":       f"{doc_id}#{i}",
                "doc_id":   doc_id,
                "doc_name": doc_name,
                "page":     i,        # we treat paragraph index as "page" for the UI
                "text":     para,
                "tokens":   tokens,
                "tf":       tf,
            }
            self.chunks.append(chunk)
            for term in tf:
                self.df[term] += 1
        self.N = len(self.chunks)

    def search(self, query, top_k=3, restrict_doc_ids=None):
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        # IDF weights for query terms only
        idf = {t: math.log((1 + self.N) / (1 + self.df.get(t, 0))) + 1.0 for t in set(q_tokens)}
        scored = []
        for ch in self.chunks:
            if restrict_doc_ids and ch["doc_id"] not in restrict_doc_ids:
                continue
            score = 0.0
            for t in set(q_tokens):
                tf = ch["tf"].get(t, 0)
                if tf:
                    score += (1 + math.log(tf)) * idf[t]
            if score > 0:
                scored.append((score, ch))
        scored.sort(key=lambda x: -x[0])
        return [
            {
                "doc_name": ch["doc_name"],
                "page":     ch["page"],
                "text":     ch["text"],
                "score":    round(s, 3),
            }
            for s, ch in scored[:top_k]
        ]


INDEX = TFIDFIndex()

# Map scheme_id -> list of doc_ids that ground that scheme
SCHEME_DOCS = defaultdict(list)


def _load_bundled_sources():
    if not SOURCES_DIR.exists():
        return
    for fname, scheme_ids in SOURCE_SCHEME_MAP.items():
        fpath = SOURCES_DIR / fname
        if not fpath.exists():
            continue
        text = fpath.read_text(encoding="utf-8")
        INDEX.add_document(doc_id=fname, doc_name=fname, text=text)
        for sid in scheme_ids:
            SCHEME_DOCS[sid].append(fname)


_load_bundled_sources()


def _attach_sources(matches, query):
    """For each matched scheme, attach the top retrieved chunk from its source PDF."""
    for m in matches:
        doc_ids = SCHEME_DOCS.get(m["id"]) or []
        if not doc_ids:
            m["source_excerpt"] = None
            continue
        # Use scheme name + benefit + eligibility as query so retrieval is contextual
        q = f"{query} {m.get('name','')} {m.get('benefit','')}"
        hits = INDEX.search(q, top_k=1, restrict_doc_ids=doc_ids)
        m["source_excerpt"] = hits[0] if hits else None
    return matches


@app.route("/api/scheme-source/<scheme_id>")
def scheme_source(scheme_id):
    """Return top 3 source chunks for a given scheme."""
    doc_ids = SCHEME_DOCS.get(scheme_id) or []
    if not doc_ids:
        return jsonify({"scheme_id": scheme_id, "sources": [], "available": False})
    # Search over all chunks in those docs (use scheme id as a weak query — returns most informative paragraph)
    by_id = {s["id"]: s for s in SCHEMES}
    sch = by_id.get(scheme_id, {})
    q = f"{sch.get('name','')} eligibility benefits apply"
    hits = INDEX.search(q, top_k=5, restrict_doc_ids=doc_ids)
    return jsonify({"scheme_id": scheme_id, "sources": hits, "available": True})


@app.route("/api/upload-pdf", methods=["POST"])
def upload_pdf():
    """Accept a PDF (or txt), extract text, add to the live index."""
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400
    f = request.files["file"]
    raw = f.read()
    name = f.filename or "uploaded.pdf"
    text = ""

    if name.lower().endswith(".txt"):
        try:
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
    else:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
        except ImportError:
            return jsonify({"error": "pypdf not installed — run: pip install pypdf"}), 500
        except Exception as exc:
            return jsonify({"error": f"failed to parse PDF: {exc}"}), 400

    if not text.strip():
        return jsonify({"error": "no readable text in document"}), 400

    doc_id = f"upload-{uuid.uuid4().hex[:8]}-{name}"
    INDEX.add_document(doc_id=doc_id, doc_name=name, text=text)
    return jsonify({
        "ok":         True,
        "doc_id":     doc_id,
        "doc_name":   name,
        "chars":      len(text),
        "chunks":     sum(1 for c in INDEX.chunks if c["doc_id"] == doc_id),
        "total_index_size": INDEX.N,
    })


# ---------------------------------------------------------------------------
# Structured eligibility engine — hard rules per scheme
# ---------------------------------------------------------------------------

def _to_int(val, default=None):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def match_form(form):
    """
    Given a structured citizen profile dict, return ranked schemes that the
    citizen HARD-qualifies for, with explicit pass/fail reasoning.

    Expected (all optional) keys:
        age, gender, annual_income, caste, state, area (urban/rural),
        occupation, has_disability, is_widow, is_pregnant,
        has_pucca_house, has_bank_account, land_acres, is_student,
        is_minority, is_senior_citizen
    """
    age          = _to_int(form.get("age"))
    gender       = (form.get("gender") or "").lower()
    income       = _to_int(form.get("annual_income"))
    caste        = (form.get("caste") or "").lower()
    area         = (form.get("area") or "").lower()
    occupation   = (form.get("occupation") or "").lower()
    has_disab    = bool(form.get("has_disability"))
    is_widow     = bool(form.get("is_widow"))
    is_pregnant  = bool(form.get("is_pregnant"))
    has_pucca    = bool(form.get("has_pucca_house"))
    has_bank     = form.get("has_bank_account")
    if has_bank is None:
        has_bank = True  # most people do
    has_bank     = bool(has_bank)
    land_acres   = form.get("land_acres")
    try:
        land_acres = float(land_acres) if land_acres not in (None, "") else None
    except ValueError:
        land_acres = None
    is_student   = bool(form.get("is_student"))
    is_minority  = bool(form.get("is_minority"))
    is_senior    = (age is not None and age >= 60) or bool(form.get("is_senior_citizen"))
    is_woman     = gender in ("female", "f", "woman", "girl")

    def add(out, scheme_id, reasons, score=10):
        out[scheme_id] = {"score": score, "reasons": list(reasons)}

    qualified = {}

    # Farmer schemes
    if occupation in ("farmer", "agriculture") or (land_acres and land_acres > 0):
        r = ["you are a farmer"]
        if land_acres is not None: r.append(f"{land_acres} acres of land")
        add(qualified, "pm-kisan", r + ["land ≤ 2 hectare qualifies"], 15)
        add(qualified, "pmfby", r + ["covers crop loss from natural calamity"], 12)
        add(qualified, "soil-health-card", r + ["free soil testing for any farmer"], 8)
        if age is not None and 18 <= age <= 40:
            add(qualified, "pm-kisan-maan-dhan", r + [f"age {age} qualifies for small-farmer pension"], 10)

    # Health
    income_bpl = income is not None and income <= 200000
    if income_bpl or (age is not None and age >= 70):
        r = []
        if income_bpl: r.append(f"income ₹{income:,} qualifies as low-income")
        if age and age >= 70: r.append(f"age {age} qualifies under senior expansion")
        add(qualified, "ayushman-bharat", r + ["covers ₹5 lakh/yr hospital expenses"], 16)

    if is_pregnant:
        add(qualified, "janani-suraksha", ["pregnancy registered", "cash assistance for institutional delivery"], 14)
        add(qualified, "ayushman-bharat", ["pregnancy + low-income coverage"], 11)

    # Insurance (anyone with bank account)
    if has_bank and age is not None:
        if 18 <= age <= 50:
            add(qualified, "pmjjby", [f"age {age} qualifies (18-50)", "₹2 lakh life cover @ ₹436/yr"], 9)
        if 18 <= age <= 70:
            add(qualified, "pmsby", [f"age {age} qualifies (18-70)", "₹2 lakh accident cover @ ₹20/yr"], 9)
        if 18 <= age <= 40:
            add(qualified, "apy", [f"age {age} qualifies for guaranteed pension"], 10)

    # Pensions
    if is_widow and age is not None and age >= 40 and income_bpl:
        add(qualified, "widow-pension", [f"widow, age {age}", "BPL household"], 16)
    elif is_widow and age is not None and age >= 40:
        add(qualified, "widow-pension", [f"widow, age {age}", "verify BPL status with Panchayat"], 12)

    if age is not None and age >= 60 and income_bpl:
        add(qualified, "old-age-pension", [f"age {age} (≥60)", "BPL household"], 15)

    # Women & girl child
    if is_woman:
        add(qualified, "mahila-samman", ["women-only savings scheme @ 7.5%"], 8)
        if income_bpl or caste in ("sc", "st", "obc"):
            add(qualified, "ujjwala", ["adult woman from low-income household", "free LPG + first refill"], 11)

    if form.get("has_daughter_under_10"):
        add(qualified, "ssy", ["girl child under 10", "8.2% tax-free savings"], 14)

    if is_minority and form.get("girl_graduated"):
        add(qualified, "shaadi-shagun", ["minority woman", "graduated", "₹51,000 marriage gift"], 12)

    # Housing
    if not has_pucca:
        if area == "rural":
            add(qualified, "pmay-g", ["no pucca house, rural", "up to ₹1.3 lakh grant"], 14)
        elif area == "urban":
            add(qualified, "pmay-u", ["no pucca house, urban", "interest subsidy up to ₹2.67 lakh"], 14)
        else:
            add(qualified, "pmay-g", ["no pucca house", "PMAY-G if rural, PMAY-U if urban"], 10)

    # Loans / business / artisan
    if occupation in ("business", "self-employed", "shopkeeper", "small business"):
        add(qualified, "mudra", ["small business", "collateral-free loan up to ₹20 lakh"], 13)
        if is_woman or caste in ("sc", "st"):
            add(qualified, "stand-up-india", ["SC/ST/Woman entrepreneur", "₹10L-₹1Cr greenfield loan"], 14)

    if occupation in ("artisan", "carpenter", "tailor", "potter", "blacksmith", "weaver", "barber"):
        add(qualified, "pm-vishwakarma", ["traditional artisan trade", "₹15K toolkit + ₹3L loan @ 5%"], 16)
        add(qualified, "mudra", ["self-employed in a trade", "collateral-free working capital"], 11)

    # Education
    if is_student and caste in ("sc", "st", "obc"):
        add(qualified, "post-matric-scholarship", [f"{caste.upper()} student", "tuition + monthly allowance"], 14)

    # Worker schemes
    if occupation in ("gig", "delivery rider", "domestic", "construction", "unorganised", "vendor", "rickshaw"):
        add(qualified, "e-shram", ["unorganised worker", "₹2 lakh accidental insurance free"], 14)
        add(qualified, "pmsby", ["unorganised worker — ₹20/yr accident cover"], 8)

    # Universal
    if not has_bank:
        add(qualified, "jan-dhan", ["no bank account", "zero-balance account + ₹2L insurance"], 12)

    if age is not None and age >= 18 and area == "rural":
        add(qualified, "mgnrega", [f"rural adult age {age}", "100 days guaranteed wage employment"], 9)

    if income_bpl:
        add(qualified, "kvp", ["low-income household", "subsidised 35kg foodgrains/month under AAY"], 10)

    # ---- Build final response ------------------------------------------------
    by_id = {s["id"]: s for s in SCHEMES}
    matches = []
    for sid, meta in sorted(qualified.items(), key=lambda kv: -kv[1]["score"]):
        sch = by_id.get(sid)
        if not sch:
            continue
        matches.append({**sch, "score": meta["score"], "why": meta["reasons"]})

    return matches


@app.route("/api/match-form", methods=["POST"])
def match_form_endpoint():
    form = request.get_json(silent=True) or {}
    matches = match_form(form)
    query = " ".join(str(v) for v in form.values() if v not in (None, "", False))
    matches = _attach_sources(matches, query)

    if matches:
        top = matches[0]["name"]
        total_val = sum(m.get("est_value_inr", 0) for m in matches)
        summary = (
            f"Based on your details, you are eligible for **{len(matches)} schemes** "
            f"worth up to **₹{total_val:,}/year**. The strongest match is **{top}**. "
            f"Every single one is FREE to apply — never pay an agent."
        )
    else:
        summary = "We couldn't find a confident match. Fill in more details and try again."

    high_risk = [m["name"] for m in matches if m.get("middleman_risk") == "high"]
    fraud_advisory = {
        "headline": "All these schemes are FREE — never pay any agent.",
        "detail": (
            f"{len(high_risk)} of your {len(matches)} matches are commonly targeted by "
            "fraud agents. Apply only via the official portal, your bank, Gram Panchayat, or CSC."
        ) if high_risk else "Apply only via the official portal, your bank, Gram Panchayat, or CSC.",
        "high_risk_schemes": high_risk,
    }

    return jsonify({
        "summary": summary,
        "matches": matches,
        "fraud_advisory": fraud_advisory,
        "profile_echo": form,
    })


@app.route("/api/personas")
def personas():
    return jsonify([
        {
            "id": "ramesh",
            "name": "Ramesh, 58 — Bihar farmer",
            "prompt": (
                "My name is Ramesh. I am 58 years old farmer in Bihar with 1.5 acres of land. "
                "My wife has diabetes and needs hospital treatment. My daughter is 17 and wants "
                "to study engineering but we have no money. We don't have a pucca house."
            ),
        },
        {
            "id": "lakshmi",
            "name": "Lakshmi, 42 — UP widow",
            "prompt": (
                "Main Lakshmi hoon, 42 saal ki. Mere pati ki pichle saal mrityu ho gayi. "
                "Mere paas 2 chote bachche hain aur main ghar mein silai ka kaam karti hoon. "
                "Ration card hai lekin koi pension nahi milti."
            ),
        },
        {
            "id": "priya",
            "name": "Priya, 23 — Mumbai gig worker",
            "prompt": (
                "I'm Priya, 23, working as a delivery rider in Mumbai. No company benefits, "
                "no insurance. I want to start my own tailoring business but need a small loan. "
                "I live in a chawl with my parents."
            ),
        },
        {
            "id": "irfan",
            "name": "Irfan, 35 — Lucknow carpenter",
            "prompt": (
                "Mera naam Irfan hai, main Lucknow mein barhai (carpenter) ka kaam karta hoon. "
                "Apne hi tools se kaam karta hoon, koi formal training nahi. Beti graduate ho gayi "
                "hai, uski shaadi karni hai. Bank account hai, EPF nahi."
            ),
        },
    ])


if __name__ == "__main__":
    host  = os.environ.get("SAHAY_HOST", "127.0.0.1")
    port  = int(os.environ.get("SAHAY_PORT", "5000"))
    debug = os.environ.get("SAHAY_DEBUG", "1") not in ("0", "false", "False", "")
    shown_host = "0.0.0.0 (all interfaces)" if host == "0.0.0.0" else host
    print("\n  Sahay - AI Welfare Navigator")
    print("  " + "-" * 30)
    print(f"  Loaded {len(SCHEMES)} schemes")
    print(f"  Claude API: {'ENABLED' if os.environ.get('ANTHROPIC_API_KEY') else 'offline mode (keyword matcher only)'}")
    print(f"  Binding   : http://{shown_host}:{port}\n")
    app.run(debug=debug, host=host, port=port)
