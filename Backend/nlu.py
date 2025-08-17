# nlu.py
import os
import re
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.concurrency import run_in_threadpool

# Google Cloud Vision + Vertex AI (Gemini)
from google.cloud import vision
from vertexai import init
from vertexai.preview.generative_models import GenerativeModel

# Firebase Admin
import firebase_admin
from firebase_admin import credentials, firestore

# =========================
# ENV & INITIALIZATION
# =========================
load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
REGION = os.getenv("REGION", "us-central1")
SA_PATH = "/run/secrets/service_account.json" #os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

if not PROJECT_ID:
    raise RuntimeError("GCP_PROJECT_ID env var is required")

# Vertex AI (Gemini)
init(project=PROJECT_ID, location=REGION)
model = GenerativeModel("gemini-2.0-flash") #("gemini-2.5-pro")

# Firebase Admin (use service account if provided, else ADC)
if not firebase_admin._apps:
    if SA_PATH and os.path.exists(SA_PATH):
        cred = credentials.Certificate(SA_PATH)
        firebase_admin.initialize_app(cred)
    else:
        firebase_admin.initialize_app()
db = firestore.client()

# Vision client (ADC or SA via GOOGLE_APPLICATION_CREDENTIALS)
vision_client = vision.ImageAnnotatorClient()

# FastAPI
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class ClaimTextInput(BaseModel):
    ocr_text: str
    user_id: str

class VerifyInput(BaseModel):
    policy_number: str
    claimant_name: Optional[str] = None
    invoice_date: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None

class ChatQueryInput(BaseModel):
    user_id: str
    question: str
    policy_number: Optional[str] = None
    from_date: Optional[str] = None  # "YYYY-MM-DD" recommended
    to_date: Optional[str] = None    # "YYYY-MM-DD" recommended

_CURRENCY_PATTERNS = [
    r'(?:total\s*amount|grand\s*total|amount\s*due|net\s*payable|balance\s*due|total)\s*[:\-]?\s*(?:₹|INR|Rs\.?)\s*([0-9][0-9,]*\.?[0-9]{0,2})',
    r'(?:₹|INR|Rs\.?)\s*([0-9][0-9,]*\.?[0-9]{0,2})'
]

def friendly_reply(message: str) -> dict:
    """Wrap responses in a chat-style envelope."""
    return {"reply": message}

def extract_amount_from_text(text: str) -> Optional[float]:
    if not text:
        return None
    t = text.lower()

    # Keyworded lines first
    m = re.findall(_CURRENCY_PATTERNS[0], t, flags=re.IGNORECASE)
    if m:
        try:
            return float(m[-1].replace(",", ""))
        except Exception:
            pass

    # Any currency token → take max
    m2 = re.findall(_CURRENCY_PATTERNS[1], t, flags=re.IGNORECASE)
    if m2:
        try:
            vals = [float(x.replace(",", "")) for x in m2]
            return max(vals) if vals else None
        except Exception:
            pass
    return None

def safe_extract_json(raw: str) -> Dict[str, Any]:
    """Extract a single JSON object from LLM output (no eval, be strict)."""
    if not raw:
        return {}
    m = re.search(r"```json\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if not m:
        m = re.search(r"(\{.*\})", raw, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        cleaned = m.group(1).replace("\n", " ").replace("\r", " ")
        try:
            return json.loads(cleaned)
        except Exception:
            return {}

def normalize_fields(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map LLM JSON into consistent keys used in Firestore.
    """
    if not isinstance(d, dict):
        d = {}

    out: Dict[str, Any] = {}

    def pick(*keys, default=None):
        for k in keys:
            if k in d and d[k] not in (None, "", []):
                return d[k]
        return default

    out["claimant_name"] = pick("name", "claimant_name", "claimant", default=None)
    out["policy_number"] = pick("policy_number", "policyNo", "policy", default=None)
    out["provider"] = pick("hospital", "hospital_name", "pharmacy", "pharmacy_name", "provider", default=None)
    out["invoice_date"] = pick("invoice_date", "date", default=None)

    total = pick("total_claim_amount", "total", "amount", default=None)
    if isinstance(total, str):
        try:
            total = float(
                total.replace(",", "").replace("₹", "").replace("INR", "").replace("Rs.", "").strip()
            )
        except Exception:
            total = None
    out["total_claim_amount"] = total

    items = pick("itemized_list", "items", default=None)
    if isinstance(items, list):
        norm_items = []
        for it in items:
            if not isinstance(it, dict):
                continue
            norm_items.append({
                "name": it.get("name"),
                "quantity": it.get("quantity"),
                "unit_price": it.get("unit_price"),
                "total": it.get("total"),
            })
        out["items"] = norm_items
    else:
        out["items"] = None

    return out

async def llm_extract_fields(text: str) -> Dict[str, Any]:
    """Ask Gemini to return structured JSON for claim fields."""
    prompt = f"""
You are an insurance claims assistant. Extract and normalize details from this invoice text and respond ONLY in JSON:

Required keys:
- "name" (string)
- "policy_number" (string or null)
- "hospital" or "pharmacy" (string; use one)
- "invoice_date" (string)
- "total_claim_amount" (number)
- "itemized_list" (array of objects with keys: name, quantity, unit_price, total)

Text:
{text}
"""
    #resp = model.generate_content(prompt)
    resp = await run_in_threadpool(model.generate_content, prompt)
    parsed = safe_extract_json(resp.text)
    return parsed

def extract_claim_fields(ocr_text: str) -> Dict[str, Any]:
    """LLM extraction + regex fallback for total amount."""
    fields_raw = llm_extract_fields(ocr_text)
    fields = normalize_fields(fields_raw)

    # fallback total if missing
    if fields.get("total_claim_amount") in (None, "", "N/A"):
        amt = extract_amount_from_text(ocr_text)
        if amt is not None:
            fields["total_claim_amount"] = amt

    return fields

def store_claim(user_id: str, claim_data: dict):
    clean = {k: v for k, v in claim_data.items() if v not in [None, ""]}
    clean["timestamp"] = datetime.utcnow().isoformat()
    db.collection("claims").add({"user_id": user_id, **clean})

def retrieve_claims(user_id: str) -> List[Dict[str, Any]]:
    docs = db.collection("claims").where("user_id", "==", user_id).order_by("timestamp").limit(20).stream()
    return [doc.to_dict() | {"id": doc.id} for doc in docs]

def summarize_claims(claims: list) -> str:
    if not claims:
        return "I couldn’t find any claims for you."
    lines = ["Here’s what I found about your claims:"]
    for c in claims:
        date = c.get("invoice_date", "Unknown date")
        amt = c.get("total_claim_amount")
        amt_disp = f"₹{amt:,.2f}" if isinstance(amt, (int, float)) else "₹N/A"
        place = c.get("provider") or c.get("hospital") or c.get("pharmacy") or "Unknown place"
        lines.append(f"- **{date}** — {amt_disp} at {place}")
    lines.append("\nAnything else you’d like to check?")
    return "\n".join(lines)

# =========================
# ROUTES
# =========================

@app.get("/")
def root():
    return friendly_reply("Hey there! 👋 Your Claims Processing Chat API is live and ready.")

# Store claim from raw text (OCR text already available)
@app.post("/store_claim_text")
async def store_claim_text(data: ClaimTextInput):
    fields = extract_claim_fields(data.ocr_text)
    if not fields:
        return friendly_reply("Hmm... I couldn’t read claim details from that text.")
    store_claim(data.user_id, fields)
    amt = fields.get("total_claim_amount")
    amt_disp = f"₹{amt:,.2f}" if isinstance(amt, (int, float)) else "₹N/A"
    date_disp = fields.get("invoice_date", "an unknown date")
    return friendly_reply(f"Got it! I’ve stored your claim for {date_disp}. Amount recorded: {amt_disp}.")

# Store claim from image (uses Vision OCR → Gemini → Firestore)
@app.post("/store_claim_image")
async def store_claim_image(user_id: str = Query(...), file: UploadFile = File(...)):
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file upload")

    image = vision.Image(content=image_bytes)
    ocr_result = vision_client.text_detection(image=image)
    ocr_text = ocr_result.text_annotations[0].description if ocr_result.text_annotations else ""
    if not ocr_text.strip():
        return friendly_reply("I couldn’t read any text from that image. Can you try another?")

    fields = extract_claim_fields(ocr_text)
    store_claim(user_id, fields)
    amt = fields.get("total_claim_amount")
    amt_disp = f"₹{amt:,.2f}" if isinstance(amt, (int, float)) else "₹N/A"
    return friendly_reply(f"Claim stored! 📄 Amount recorded: {amt_disp}.")

# Summarize a user's claims (chatty)
@app.get("/get_claims")
async def get_claims(user_id: str):
    claims = retrieve_claims(user_id)
    return friendly_reply(summarize_claims(claims))

# Q&A over claims (GET form) – kept for backward compatibility
@app.get("/query_claims")
async def query_claims(user_id: str, question: str):
    claims = retrieve_claims(user_id)
    if not claims:
        return friendly_reply("No claims found for you.")
    claims_text = json.dumps(claims, ensure_ascii=False)
    prompt = f"""You are a friendly assistant. Answer the user's question about their claims.
Question: {question}
Claims JSON: {claims_text}

Rules:
- Be concise and helpful.
- If the question needs a specific claim, reference it by date and amount.
- If data is missing, say what’s missing.
- Do NOT invent values.
- End with a short follow-up like: “Anything else you want to check?”
"""
    resp = model.generate_content(prompt)
    return friendly_reply((resp.text or "").strip() or "Sorry, I couldn’t generate a response.")

# NEW: Free-form chat endpoint (JSON body; great for webhooks like Inya)
@app.post("/chat_query")
async def chat_query(body: ChatQueryInput):
    col = db.collection("claims").where("user_id", "==", body.user_id)
    if body.policy_number:
        col = col.where("policy_number", "==", body.policy_number)

    docs = list(col.stream())
    claims = [d.to_dict() | {"id": d.id} for d in docs]

    # Optional date window (string compare works if you store ISO dates)
    if body.from_date or body.to_date:
        lo = body.from_date or ""
        hi = body.to_date or "9999-12-31"
        def in_range(c):
            d = (c.get("invoice_date") or "").strip()
            return bool(d) and (lo <= d <= hi)
        claims = [c for c in claims if in_range(c)]

    if not claims:
        return friendly_reply("I don’t see any claims that match that. Want to try different filters?")

    claims_json = json.dumps(claims, ensure_ascii=False)
    prompt = f"""
You are a friendly claims assistant. Answer the user's question about their claims.

User question: {body.question}

Claims JSON:
{claims_json}

Guidelines:
- Be concise, clear, and helpful.
- If you reference a specific claim, mention its invoice date and amount.
- If info is missing (e.g., no policy number), say what's missing.
- If the question needs a calculation, do it and show the result.
- Do NOT invent values not present in the claims JSON.
- End with a short follow-up like: “Anything else you want to check?”
"""
    resp = model.generate_content(prompt)
    answer = (resp.text or "").strip() or "Sorry, I couldn’t generate a response."
    return friendly_reply(answer)

# Verify claims (basic matching filters)
@app.post("/claims/verify")
def verify_claim(q: VerifyInput):
    col = db.collection("claims").where("policy_number", "==", q.policy_number).limit(50)
    candidates = [{"id": d.id, **d.to_dict()} for d in col.stream()]

    def matches(c):
        ok = True
        if q.claimant_name:
            got = (c.get("claimant_name") or "").lower()
            ok = ok and (q.claimant_name.lower() in got)
        if q.invoice_date:
            ok = ok and (q.invoice_date == (c.get("invoice_date") or ""))
        amt = c.get("total_amount") or c.get("total_claim_amount")
        if q.min_amount is not None:
            ok = ok and (isinstance(amt, (int, float)) and amt >= q.min_amount)
        if q.max_amount is not None:
            ok = ok and (isinstance(amt, (int, float)) and amt <= q.max_amount)
        return ok

    matches_list = [c for c in candidates if matches(c)]
    return {"count": len(matches_list), "matches": matches_list}

@app.post("/inya_webhook")
async def inya_webhook(request: Request):
    data = await request.json()
    print("Incoming event from Inya:", data)
    
    # Example: send back chatbot reply
    return {
        "reply": "This is my chatbot's voice-enabled response!"
    }

@app.get("/config")
def get_config():
    return {"agent_id": os.getenv("AGENT_ID")}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("nlu:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
