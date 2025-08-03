import os
import json
import io
import re
import uvicorn
from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from PIL import Image
from dotenv import load_dotenv

from google.cloud import vision
from google.oauth2 import service_account

from vertexai import init
from vertexai.preview.generative_models import GenerativeModel

# === ENV SETUP ===
load_dotenv()

# === GOOGLE CLOUD PROJECT ===
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
REGION = "us-central1"
init(project=PROJECT_ID, location=REGION)

# === GEMINI MODEL ===
model = GenerativeModel("gemini-2.5-pro")

# === FASTAPI INIT ===
app = FastAPI()

# === GOOGLE VISION CLIENT ===
creds = service_account.Credentials.from_service_account_file("service_account.json")
vision_client = vision.ImageAnnotatorClient(credentials=creds)

# === SCHEMA ===
class ClaimTextInput(BaseModel):
    ocr_text: str

# === UTILS: Extract JSON from Gemini output ===
def extract_json_from_gemini(raw_response: str):
    try:
        match = re.search(r"```json\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
        if not match:
            match = re.search(r"(\{.*\})", raw_response, re.DOTALL)
        if not match:
            raise ValueError("No JSON found.")
        return json.loads(match.group(1))
    except Exception as e:
        print("❌ Failed to extract JSON:", e)
        return {"error": "Gemini response was not valid JSON", "raw": raw_response}

# === GEMINI FIELD EXTRACTOR ===
def gpt_extract_fields_from_text(text: str) -> dict:
    prompt = f"""
You are an insurance claims AI. Extract the following fields from this invoice text and return JSON:

- name
- policy_number (optional)
- hospital or pharmacy name
- invoice date
- total_claim_amount (as number)
- itemized_list: name, quantity, unit_price, total

Text:
{text}
"""
    try:
        response = model.generate_content(prompt)
        content = response.text
        print("🔍 Gemini Response:\n", content)
        return extract_json_from_gemini(content)
    except Exception as e:
        return {"error": str(e), "raw": text}

# === CLAIM VALIDATION ===
def validate_claim(fields: dict) -> dict:
    errors = []

    if "total_claim_amount" in fields:
        try:
            amount = float(fields["total_claim_amount"])
            if amount > 50000:
                errors.append("Claim amount exceeds ₹50,000.")
        except:
            errors.append("Invalid total_claim_amount value.")

    if "admit_date" in fields and "discharge_date" in fields:
        if fields["admit_date"] > fields["discharge_date"]:
            errors.append("Admit date is after discharge date.")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "fields": fields
    }

# === ROUTES ===
@app.get("/")
def read_root():
    return {"message": "✅ Claims Processing API (Gemini + Vision OCR) is live!"}

@app.post("/parse_claim")
async def parse_claim(data: ClaimTextInput):
    fields = gpt_extract_fields_from_text(data.ocr_text)
    result = validate_claim(fields)
    return result

@app.post("/upload_claim_image")
async def upload_claim_image(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        image = vision.Image(content=image_bytes)
        response = vision_client.text_detection(image=image)

        ocr_text = response.text_annotations[0].description if response.text_annotations else ""

        fields = gpt_extract_fields_from_text(ocr_text)
        result = validate_claim(fields)

        return {
            "ocr_text": ocr_text,
            **result
        }

    except Exception as e:
        return {"error": str(e)}

# === RUN APP LOCALLY ===
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
