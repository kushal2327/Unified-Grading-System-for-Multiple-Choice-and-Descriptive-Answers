"""
apps/descriptive_grading/pipeline/ocr.py

Phase 2, Step 2: run Tesseract on the preprocessed binary image,
compute an overall confidence score, and clean up the extracted text.
"""
import re
from typing import Tuple

import numpy as np
import pytesseract
from django.conf import settings

# On Windows, Tesseract usually isn't on PATH by default, so let the
# user point pytesseract at the exe explicitly via .env if needed.
if getattr(settings, "TESSERACT_CMD", ""):
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


def run_ocr(binary_image: np.ndarray) -> Tuple[str, float]:
    """
    Run Tesseract on a preprocessed binary image.

    Returns (raw_text, average_confidence) where average_confidence is
    0-100, computed only over words Tesseract actually detected
    (confidence -1 entries, which mean "no text", are excluded).
    """
    data = pytesseract.image_to_data(
        binary_image,
        output_type=pytesseract.Output.DICT,
        config="--psm 6",  # assume a single uniform block of text
    )

    words = []
    confidences = []
    for i, word in enumerate(data["text"]):
        conf = int(data["conf"][i]) if data["conf"][i] not in ("-1", "") else -1
        if word.strip() and conf >= 0:
            words.append(word)
            confidences.append(conf)

    raw_text = " ".join(words)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return raw_text, avg_confidence


# Common Tesseract misreads for handwriting -> intended character.
# Applied conservatively (only in isolated-digit/letter contexts) to
# avoid corrupting otherwise-correct words.
_COMMON_OCR_FIXES = [
    (r"\bl\b", "1"),   # lowercase L standing alone -> likely "1"
    (r"\bO\b", "0"),   # capital O standing alone -> likely "0"
]


def clean_text(raw_text: str) -> str:
    """
    Clean OCR output:
    - collapse whitespace
    - strip stray non-alphanumeric punctuation artifacts
    - fix a small set of common Tesseract misreads (l->1, O->0, etc.)
    """
    text = raw_text.strip()

    # Strip characters Tesseract sometimes hallucinates from paper
    # texture/noise, but keep normal punctuation used in sentences.
    text = re.sub(r"[^\w\s.,;:!?'\"()\-]", "", text)

    # Collapse repeated whitespace
    text = re.sub(r"\s+", " ", text).strip()

    for pattern, replacement in _COMMON_OCR_FIXES:
        text = re.sub(pattern, replacement, text)

    return text


def extract_and_clean(binary_image: np.ndarray) -> dict:
    """
    Full OCR step: run Tesseract, clean the text, and check against the
    configured confidence threshold.

    Returns:
        {
            "raw_text": str,
            "cleaned_text": str,
            "confidence": float,
            "below_threshold": bool,
        }
    """
    raw_text, confidence = run_ocr(binary_image)
    cleaned = clean_text(raw_text)

    return {
        "raw_text": raw_text,
        "cleaned_text": cleaned,
        "confidence": confidence,
        "below_threshold": confidence < settings.OCR_CONFIDENCE_THRESHOLD,
    }
