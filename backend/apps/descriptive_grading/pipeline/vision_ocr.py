"""
apps/descriptive_grading/pipeline/vision_ocr.py

Replaces Tesseract-based OCR with a vision-language model
(Qwen2.5-VL, served locally through Ollama) for transcribing
handwritten answer sheets. VLMs read messy/cursive handwriting far
better than traditional OCR engines like Tesseract, since they use
contextual/semantic understanding rather than per-character pattern
matching.
"""
import base64
import json
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

VISION_PROMPT = """Transcribe all handwritten text in this image exactly as written, preserving line breaks where natural. Then rate your confidence in the accuracy of this transcription from 0 to 100, based on handwriting legibility, image clarity, and any ambiguous or illegible words.

Respond ONLY in this exact JSON format, with no other text:
{"text": "<the transcribed text>", "confidence": <integer 0-100>}
"""


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _extract_json(raw_response: str) -> dict:
    """
    Parse the model's JSON response, tolerating trailing garbage after
    a valid object (e.g. Qwen2.5-VL sometimes emits a stray extra
    closing brace: {"text": "...", "confidence": 85}} ). raw_decode
    parses just the first complete JSON object starting from the
    first '{' and ignores anything after it, instead of failing on it.
    """
    text = raw_response.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in vision model response")

    decoder = json.JSONDecoder()
    obj, _end_index = decoder.raw_decode(text, start)
    return obj


def run_vision_ocr(image_path: str) -> dict:
    """
    Send the raw answer-sheet image to the configured vision model
    (Qwen2.5-VL via Ollama) and get back a transcription + the
    model's own confidence estimate.

    Returns: {"raw_text": str, "confidence": float}
    """
    image_b64 = _encode_image(image_path)

    response = requests.post(
        f"{settings.OLLAMA_HOST}/api/generate",
        json={
            "model": settings.OLLAMA_VISION_MODEL,
            "prompt": VISION_PROMPT,
            "images": [image_b64],
            "stream": False,
        },
        timeout=180,
    )
    response.raise_for_status()
    raw_response = response.json()["response"]

    try:
        parsed = _extract_json(raw_response)
        text = str(parsed.get("text", "")).strip()
        confidence = float(parsed.get("confidence", 0))
    except Exception as exc:
        logger.warning("Vision OCR response wasn't valid JSON, falling back to raw text: %s", exc)
        text = raw_response.strip()
        confidence = 50.0

    confidence = max(0.0, min(100.0, confidence))
    return {"raw_text": text, "confidence": confidence}


def clean_text(raw_text: str) -> str:
    """Light cleanup only - collapse whitespace. VLM output is
    typically already clean prose, so we skip the Tesseract-era
    character-fix hacks (l->1, O->0), which would be inappropriate
    here and could actively corrupt otherwise-correct text."""
    return re.sub(r"\s+", " ", raw_text.strip())


def extract_and_clean(image_path: str) -> dict:
    """
    Full OCR step using the vision model. Matches the interface the
    grading pipeline previously used from ocr.extract_and_clean(),
    except it takes an image PATH instead of a preprocessed array -
    Qwen2.5-VL works from the raw image directly and does not need
    (or benefit from) OpenCV grayscale/threshold preprocessing.
    """
    result = run_vision_ocr(image_path)
    cleaned = clean_text(result["raw_text"])

    return {
        "raw_text": result["raw_text"],
        "cleaned_text": cleaned,
        "confidence": result["confidence"],
        "below_threshold": result["confidence"] < settings.OCR_CONFIDENCE_THRESHOLD,
    }