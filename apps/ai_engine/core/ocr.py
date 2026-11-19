"""
Module for scanned/image PDF OCR using Google Gemini Vision API.
This handles SCANNED PDFs by converting pages to images and using Gemini Vision.
"""
import fitz
import os
import google.generativeai as genai
from PIL import Image
import io
from ..config import settings

# Configure Gemini with the API key
genai.configure(api_key=settings.GEMINI_API_KEY)

def ocr_extract(file_path: str) -> dict:
    """
    Converts PDF pages to images, sends each to Gemini Vision with a prompt
    to extract text. Returns the same format as extractor.
    """
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
        
    try:
        doc = fitz.open(file_path)
        pages = []
        full_text = []
        
        # Load the Gemini vision model
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = "Extract all text from this document image. Preserve formatting."
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # increase resolution
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            response = model.generate_content([prompt, img])
            text = response.text if response.text else ""
            
            pages.append(text)
            full_text.append(text)
            
        metadata = doc.metadata
        page_count = len(doc)
        doc.close()
        
        return {
            "pages": pages,
            "full_text": "\n".join(full_text),
            "page_count": page_count,
            "metadata": metadata
        }
    except Exception as e:
        return {"error": str(e)}
