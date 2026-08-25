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

VISION_PROMPT = """You are an expert handwriting transcription assistant. Your ONLY job is to transcribe the handwritten text from this image as accurately as possible.

Instructions:
1. Read every word carefully, including crossed-out text (mark it with ~~strikethrough~~)
2. Preserve the original line breaks and paragraph structure
3. If a word is partially legible, transcribe what you can see and mark uncertain parts with [?]
4. Do NOT interpret, correct spelling, or add punctuation that isn't in the original
5. Do NOT summarize or rephrase — output the exact text as written

Respond ONLY in this exact JSON format, nothing else:
{"text": "<exact transcription>"}
"""


class VisionOCRError(Exception):
    """Raised when the vision OCR model fails to process an image."""
    pass


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


def check_ollama_status() -> dict:
    """
    Check if Ollama is running and the vision model is available.
    Returns a dict with status info for diagnostic purposes.
    """
    result = {"ollama_running": False, "vision_model_available": False, "error": None}
    try:
        resp = requests.get(f"{settings.OLLAMA_HOST}/api/tags", timeout=5)
        resp.raise_for_status()
        result["ollama_running"] = True
        models = [m.get("name", "") for m in resp.json().get("models", [])]
        vision_model = settings.OLLAMA_VISION_MODEL
        result["vision_model_available"] = any(
            vision_model in m or m.startswith(vision_model.split(":")[0])
            for m in models
        )
        result["available_models"] = models
    except requests.ConnectionError:
        result["error"] = (
            f"Cannot connect to Ollama at {settings.OLLAMA_HOST}. "
            "Make sure Ollama is running (run 'ollama serve' in a terminal)."
        )
    except Exception as exc:
        result["error"] = f"Ollama health check failed: {exc}"
    return result


def _compute_confidence(text: str) -> float:
    """
    Estimate transcription confidence heuristically from the output text.
    Instead of relying on the model's unreliable self-reported confidence,
    we use simple signals: length, uncertainty markers, and character ratios.

    Returns a granular float between 0.0 and 100.0 so the frontend can
    display the exact score rather than a coarse bucket.
    """
    if not text or not text.strip():
        return 0.0

    score = 100.0
    text = text.strip()
    word_count = len(text.split())
    char_count = len(text)

    # Penalize very short output proportionally (not a flat -50)
    # 0 chars → 0, 1 char → ~20, 2-4 chars → 30-40
    if char_count == 0:
        score = 0.0
    elif char_count < 5:
        score = max(0.0, 20.0 + (char_count * 5.0))
    elif char_count < 15:
        # Short but not empty — mild penalty
        score -= 15.0 * (1 - char_count / 15)

    # Penalize uncertainty markers [?] proportionally
    uncertain_count = text.count("[?]")
    if uncertain_count > 0:
        uncertain_ratio = uncertain_count / max(word_count, 1)
        score -= uncertain_ratio * 40  # up to -40 for all uncertain

    # Penalize excessive non-alphanumeric noise (garbled output)
    alpha_chars = sum(c.isalnum() or c.isspace() for c in text)
    total_chars = max(len(text), 1)
    noise_ratio = 1 - (alpha_chars / total_chars)
    if noise_ratio > 0.3:
        # Scale penalty: 0.3→0, 0.6→-15, 1.0→-25
        score -= min(25.0, (noise_ratio - 0.3) * 62.5)

    # Bonus for reasonable length (student answers are usually a few sentences)
    if char_count > 20:
        score = min(100, score + 5)

    return round(max(0.0, min(100.0, score)), 1)


def run_vision_ocr(image_path: str) -> dict:
    """
    Send the raw answer-sheet image to the configured vision model
    (Qwen2.5-VL via Ollama) and get back a transcription.

    Returns: {"raw_text": str, "confidence": float}

    Raises: VisionOCRError if the model cannot process an image.
    """
    import os
    image_size = os.path.getsize(image_path)
    logger.info("Vision OCR request — file: %s, size: %.1f KB", image_path, image_size / 1024)

    image_b64 = _encode_image(image_path)

    try:
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
    except requests.ConnectionError:
        raise VisionOCRError(
            f"Cannot connect to Ollama at {settings.OLLAMA_HOST}. "
            "Make sure Ollama is running (run 'ollama serve' in a terminal). "
            "You also need the vision model: 'ollama pull qwen2.5vl:3b'"
        )
    except requests.Timeout:
        raise VisionOCRError(
            "Ollama request timed out after 180s. "
            "The image may be too large or the model is too slow."
        )
    except requests.RequestException as exc:
        raise VisionOCRError(f"Ollama request failed: {exc}")

    if response.status_code == 404:
        raise VisionOCRError(
            f"Vision model '{settings.OLLAMA_VISION_MODEL}' not found in Ollama. "
            f"Pull it with: ollama pull {settings.OLLAMA_VISION_MODEL}"
        )

    response.raise_for_status()

    try:
        raw_response = response.json()["response"]
    except (KeyError, json.JSONDecodeError) as exc:
        raise VisionOCRError(f"Unexpected Ollama response format: {exc}")

    logger.info("Vision OCR raw response (first 500 chars): %s", raw_response[:500])

    try:
        parsed = _extract_json(raw_response)
        text = str(parsed.get("text", "")).strip()
        logger.info("Parsed JSON text field (length %d): %s", len(text), text[:200])
    except Exception as exc:
        logger.warning("Vision OCR response wasn't valid JSON, using raw text: %s", exc)
        text = raw_response.strip()

    confidence = _compute_confidence(text)
    logger.info("Vision OCR confidence: %.1f%%, text length: %d chars, %d words",
                confidence, len(text), len(text.split()))

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

    below_threshold = result["confidence"] < settings.OCR_CONFIDENCE_THRESHOLD
    if below_threshold:
        logger.warning(
            "OCR confidence %.1f%% is below threshold %s%% for image %s. "
            "Extracted text (first 200 chars): %s",
            result["confidence"], settings.OCR_CONFIDENCE_THRESHOLD,
            image_path, cleaned[:200],
        )

    return {
        "raw_text": result["raw_text"],
        "cleaned_text": cleaned,
        "confidence": result["confidence"],
        "below_threshold": below_threshold,
    }