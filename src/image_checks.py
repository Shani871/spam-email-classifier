"""Local screenshot OCR and QR decoding. Destinations are never fetched."""
import io
import sys
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000


def extract_image_content(data, language="eng"):
    if len(data) > MAX_BYTES:
        raise ValueError("Choose an image smaller than 10 MB.")
    try:
        image = Image.open(io.BytesIO(data))
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("Choose an image with fewer than 20 million pixels.")
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((2400, 2400))
    except (UnidentifiedImageError, Image.DecompressionBombError):
        raise ValueError("This file could not be read as a supported image.")
    warnings, text, codes = [], "", []
    try:
        import pytesseract
        text = pytesseract.image_to_string(image, lang=language, timeout=15).strip()
        if not text:
            warnings.append("No readable text found. Try a clearer image or paste the message.")
    except (ImportError, RuntimeError, OSError, subprocess.SubprocessError):
        if sys.platform == "darwin":
            try:
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                helper = Path(__file__).resolve().with_name("native_ocr.py")
                outcome = subprocess.run([sys.executable, str(helper), language], input=buffer.getvalue(),
                                         capture_output=True, timeout=30, check=True)
                recognized = json.loads(outcome.stdout)
                text, languages = recognized["text"], recognized["languages"]
                if "hin" in language and "hi-IN" not in languages:
                    warnings.append("Hindi OCR is unavailable on this device. Review the extracted text carefully.")
                if not text:
                    warnings.append("No readable text found. Try a clearer image or paste the message.")
            except (ImportError, OSError, RuntimeError, ValueError, subprocess.SubprocessError):
                warnings.append("Screenshot text recognition is unavailable. Install the local image dependencies or paste the message text.")
        else:
            warnings.append("Screenshot text recognition requires the local Tesseract engine. You can paste the text below.")
    try:
        import cv2
        import numpy as np
        matrix = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        detector = cv2.QRCodeDetector()
        found, decoded, _, _ = detector.detectAndDecodeMulti(matrix)
        if found:
            codes = list(dict.fromkeys(value for value in decoded if value))
        if not codes:
            single, _, _ = detector.detectAndDecode(matrix)
            if single:
                codes = [single]
    except (ImportError, RuntimeError):
        warnings.append("QR decoding requires the optional image dependencies.")
    if not codes:
        warnings.append("No readable QR destination found. This does not mean the image is safe.")
    return {"text": text, "qr_destinations": codes, "warnings": warnings}
