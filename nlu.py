from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import os, json, re
from dotenv import load_dotenv
from google.cloud import vision
from google.oauth2 import service_account
from vertexai import init
from vertexai.preview.generative_models import GenerativeModel

# === ENV SETUP ===
load_dotenv()
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
REGION = "us-central1"
init(project=PROJECT_ID, location=REGION)

model = GenerativeModel("gemini-2.5-pro")
app = FastAPI()

creds = service_account.Credentials.from_service_account_file("service_account.json")
vision_client = vision.ImageAnnotatorClient(credentials=creds)

class ClaimTextInput(BaseModel):
    ocr_text: str

def extract_json_from_gemini(raw_response: str):
    try:
        match = re.search(r"```json\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
        if not match:
            match = re.search(r"(\{.*\})", raw_response, re.DOTALL)
        return json.loads(match.group(1)) if match else {}
    except:
        return {}

def gpt_extract_fields_from_text(text: str) -> dict:
    prompt = f"""
You are an insurance claims assistant. Extract these fields as JSON:
- name
- policy_number
- hospital or pharmacy name
- invoice date
- total_claim_amount
- itemized_list: name, quantity, unit_price, total

Text:
{text}
"""
    response = model.generate_content(prompt)
    return extract_json_from_gemini(response.text)

def validate_claim(fields: dict) -> (bool, list):
    errors = []
    try:
        amount = float(fields.get("total_claim_amount", 0))
        if amount > 50000:
            errors.append("Claim amount exceeds ₹50,000.")
    except:
        errors.append("Invalid amount format.")
    return len(errors) == 0, errors

def generate_chat_response(fields: dict, is_valid: bool, errors: list) -> str:
    if not fields:
        return "I couldn’t extract details from the document. Please upload a clearer image or try again."

    lines = []
    if is_valid:
        lines.append("Thanks! I’ve reviewed your claim. Here’s what I found:")
    else:
        lines.append("I noticed some issues with your claim:")
        for e in errors:
            lines.append(f"- {e}")
        lines.append("Still, here’s what I could extract:")

    if fields.get("name"):
        lines.append(f"The claim is under the name {fields['name']}.")
    if fields.get("policy_number"):
        lines[-1] += f" Policy number is {fields['policy_number']}."
    if fields.get("hospital") or fields.get("invoice_date"):
        line = "It was issued"
        if fields.get("hospital"):
            line += f" by {fields['hospital']}"
        if fields.get("invoice_date"):
            line += f" on {fields['invoice_date']}"
        line += "."
        lines.append(line)
    if fields.get("total_claim_amount"):
        lines.append(f"Total amount claimed is ₹{fields['total_claim_amount']}.")

    if fields.get("itemized_list"):
        lines.append("Here’s a breakdown of the charges:")
        for i, item in enumerate(fields["itemized_list"], 1):
            lines.append(f"{i}. {item['name']} — {item['quantity']} at ₹{item['unit_price']} each, total ₹{item['total']}")

    lines.append("Let me know if you'd like to proceed with submission or corrections.")
    return "\n".join(lines)

@app.post("/chat_parse_claim")
async def chat_parse_claim(data: ClaimTextInput):
    fields = gpt_extract_fields_from_text(data.ocr_text)
    is_valid, errors = validate_claim(fields)
    response = generate_chat_response(fields, is_valid, errors)
    return {"response": response}

@app.post("/chat_upload_claim_image")
async def chat_upload_claim_image(file: UploadFile = File(...)):
    image_bytes = await file.read()
    image = vision.Image(content=image_bytes)
    response = vision_client.text_detection(image=image)
    ocr_text = response.text_annotations[0].description if response.text_annotations else ""

    fields = gpt_extract_fields_from_text(ocr_text)
    is_valid, errors = validate_claim(fields)
    response = generate_chat_response(fields, is_valid, errors)
    return {"response": response}
