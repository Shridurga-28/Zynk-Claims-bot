from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from vertexai import init
from vertexai.preview.generative_models import GenerativeModel
from google.cloud import vision
import os, re
from dotenv import load_dotenv

# === ENV SETUP ===
load_dotenv()
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
REGION = os.getenv("REGION", "us-central1")

# Initialize Vertex AI and Gemini
init(project=PROJECT_ID, location=REGION)
model = GenerativeModel("gemini-2.5-pro")

# Google Cloud Vision client
vision_client = vision.ImageAnnotatorClient()

# FastAPI app
app = FastAPI()

# === SCHEMA ===
class ClaimTextInput(BaseModel):
    ocr_text: str

# === UTILS ===
def gpt_generate_chat_from_text(text: str) -> str:
    """
    Sends OCR text to Gemini and returns a conversational, Markdown-formatted summary.
    """
    prompt = (
        "You are an insurance claims assistant. The following is OCR text from a claim invoice.\n\n"
        "Your task:\n"
        "1. Create a friendly summary in Markdown format.\n"
        "2. Always include these sections, even if the data is missing (write 'Not provided' if missing):\n"
        "   - Claimant Name\n"
        "   - Policy Number\n"
        "   - Hospital/Pharmacy Name\n"
        "   - Invoice Date\n"
        "   - Total Claim Amount\n"
        "3. Provide an itemized breakdown with each item's name, quantity, and unit price if available.\n"
        "4. End with a friendly closing line.\n\n"
        "Example output:\n"
        "Hi there! Here’s a quick summary of your claim:\n\n"
        "**Claim Details:**\n"
        "- Claimant Name: John Doe\n"
        "- Policy Number: Not provided\n"
        "- Pharmacy Name: ABC Pharmacy\n"
        "- Invoice Date: 15-Jan-2025\n"
        "- Total Claim Amount: ₹1,250.00\n\n"
        "**Items Purchased:**\n"
        "1. Paracetamol 500 mg — 10 tablets @ ₹5.00 each\n"
        "2. Cough Syrup (200ml) — 2 bottles @ ₹90.00 each\n\n"
        "Everything looks clear. Let me know if you have any questions!\n\n"
        f"Invoice text:\n{text}"
    )

    response = model.generate_content(prompt)
    print("🔍 RAW GEMINI CHAT OUTPUT:\n", response.text)
    return response.text.strip()

def validate_claim_in_text(chat_response: str) -> str:
    """
    Checks the claim amount in the chat response and appends a warning if above ₹50,000.
    """
    match = re.search(r"₹([\d,]+\.\d{2})", chat_response)
    if match:
        try:
            amount = float(match.group(1).replace(",", ""))
            if amount > 100000:
                chat_response += "\n\n **Note:** This claim amount exceeds the ₹1,00,000 limit."
        except:
            pass
    return chat_response

# === ENDPOINTS ===
@app.post("/chat_parse_claim")
async def chat_parse_claim(data: ClaimTextInput):
    chat_response = gpt_generate_chat_from_text(data.ocr_text)
    chat_response = validate_claim_in_text(chat_response)
    return {"response": chat_response}

@app.post("/chat_upload_claim_image")
async def chat_upload_claim_image(file: UploadFile = File(...)):
    image_bytes = await file.read()
    image = vision.Image(content=image_bytes)
    response = vision_client.text_detection(image=image)
    ocr_text = response.text_annotations[0].description if response.text_annotations else ""

    if not ocr_text.strip():
        return {
            "response": "Hmm... I couldn't read any text from this image. Please upload a clearer image or try again."
        }

    chat_response = gpt_generate_chat_from_text(ocr_text)
    chat_response = validate_claim_in_text(chat_response)
    return {"response": chat_response}

# Root endpoint
@app.get("/")
def root():
    return {"message": "Claims Processing Chat API is live!"}
