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
import io
import json
import logging
import re
import time
from collections import Counter

import requests
from django.conf import settings

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

logger = logging.getLogger(__name__)

_LEGACY_VISION_PROMPT = """You are an expert handwriting transcription assistant. Your ONLY job is to transcribe the handwritten text from this image as accurately as possible.

Instructions:
1. Read every word carefully, including crossed-out text (mark it with ~~strikethrough~~)
2. Preserve the original line breaks and paragraph structure
3. If a word is partially legible, transcribe what you can see and mark uncertain parts with [?]
4. Do NOT interpret, correct spelling, or add punctuation that isn't in the original
5. Do NOT summarize or rephrase — output the exact text as written

Respond ONLY in this exact JSON format, nothing else:
{"text": "<exact transcription>"}
"""

# Keep this replacement deliberately terse: small VLMs tend to invent a
# continuation when a transcription prompt asks them to "read every word".
VISION_PROMPT = """Transcribe ONLY text visibly present in this image.
Never infer, complete, paraphrase, or repeat text. Stop when the visible text ends.
Preserve visible line breaks. Do not add numbering, headings, or punctuation.
Use [illegible] for an unreadable word; if there is no readable handwriting, return an empty text value.
Respond only with JSON in this form: {\"text\": \"<exact transcription>\"}."""


class VisionOCRError(Exception):
    """Raised when the vision OCR model fails to process an image."""
    pass


_MAX_IMAGE_DIMENSION = 1024
_OCR_MAX_RETRIES = 2
_OCR_RETRY_DELAY = 1.0


def _encode_image(image_path: str) -> str:
    """Read and base64-encode an image, resizing it if too large.

    Vision models consume VRAM proportional to image resolution (each pixel
    becomes visual tokens).  Large images (>1024 px on any side) can push a
    small GPU over its VRAM budget, causing the model to crash mid-generation
    (`done: false`) or produce garbage.  We resize before encoding to keep
    VRAM usage predictable while preserving enough detail for handwriting.
    """
    if PILLOW_AVAILABLE:
        try:
            img = Image.open(image_path)
            w, h = img.size
            if max(w, h) > _MAX_IMAGE_DIMENSION:
                ratio = _MAX_IMAGE_DIMENSION / max(w, h)
                new_size = (int(w * ratio), int(h * ratio))
                img = img.resize(new_size, Image.LANCZOS)
                buf = io.BytesIO()
                fmt = "PNG" if image_path.lower().endswith(".png") else "JPEG"
                if fmt == "JPEG" and img.mode == "RGBA":
                    img = img.convert("RGB")
                img.save(buf, format=fmt, quality=90)
                raw = buf.getvalue()
                logger.info("Resized image from %dx%d to %dx%d", w, h, *new_size)
            else:
                with open(image_path, "rb") as f:
                    raw = f.read()
            return base64.b64encode(raw).decode("utf-8")
        except Exception as exc:
            logger.warning("Pillow resize failed, falling back to raw read: %s", exc)

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

    text = text.strip()
    word_count = len(text.split())

    # Reject text that is purely symbols/punctuation (e.g. "@@@@@...", "?????")
    # with no actual alphanumeric content — this is garbage output from the model.
    alpha_word_count = len(re.findall(r"[a-zA-Z0-9]+", text))
    if alpha_word_count == 0:
        return 0.0

    score = 100.0
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


def _repetition_reason(text: str) -> str | None:
    """Identify unmistakable VLM generation loops before they reach grading."""
    normalized_lines = []
    for line in text.splitlines():
        # Compare list entries after removing their generated numbers.
        line = re.sub(r"^\s*(?:\d+|[ivxlcdm]+)[.)]\s*", "", line.lower())
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) >= 8:
            normalized_lines.append(line)

    if normalized_lines and max(Counter(normalized_lines).values()) >= 4:
        return "repeated lines"

    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < 20:
        return None

    phrases = Counter(tuple(words[i:i + 4]) for i in range(len(words) - 3))
    repeated_phrase, occurrences = phrases.most_common(1)[0]
    # Five copies of one phrase covering >=25% of the output is a model loop,
    # not a reasonable handwritten response.
    if occurrences >= 5 and (occurrences * 4) / len(words) >= 0.25:
        return f"repeated phrase: {' '.join(repeated_phrase)!r}"
    return None


def _is_garbage_output(text: str) -> bool:
    """Detect obvious model failures that are not real transcriptions."""
    if not text:
        return True
    # The qwen2.5vl model sometimes crashes and fills output with @@ or ?? repeats.
    stripped = text.strip()
    if len(stripped) < 3:
        return True
    unique_chars = set(stripped)
    if len(unique_chars) <= 3 and all(c in "@#?!=-~" for c in unique_chars):
        return True
    return False


def _call_ollama_vision(image_b64: str) -> dict:
    """Single attempt to call the Ollama vision API. Returns parsed JSON dict."""
    # NOTE: We do NOT send "format": "json" — vision models in Ollama silently
    # fail or return empty responses with that parameter.  We ask for JSON in the
    # prompt text and parse it ourselves.
    response = requests.post(
        f"{settings.OLLAMA_HOST}/api/generate",
        json={
            "model": settings.OLLAMA_VISION_MODEL,
            "prompt": VISION_PROMPT,
            "images": [image_b64],
            "stream": False,
            "keep_alive": "5m",
            "options": {
                "temperature": 0,
                "num_predict": 1024,
                "repeat_penalty": 1.2,
            },
        },
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


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

    raw_response = None
    last_error = None

    for attempt in range(1, _OCR_MAX_RETRIES + 1):
        try:
            ollama_resp = _call_ollama_vision(image_b64)
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

        if ollama_resp.get("status_code") == 404 or ollama_resp.get("error"):
            raise VisionOCRError(
                f"Vision model '{settings.OLLAMA_VISION_MODEL}' not found in Ollama. "
                f"Pull it with: ollama pull {settings.OLLAMA_VISION_MODEL}"
            )

        raw_response = ollama_resp.get("response", "")

        # The Ollama API sets "done": true on a successful completion.
        # done=false usually means the model crashed (e.g. VRAM OOM).
        if not ollama_resp.get("done", True):
            logger.warning(
                "Vision model returned done=false (attempt %d/%d). "
                "Likely VRAM pressure — retrying after %.1fs.",
                attempt, _OCR_MAX_RETRIES, _OCR_RETRY_DELAY,
            )
            last_error = "Model crashed (done=false)"
            time.sleep(_OCR_RETRY_DELAY)
            continue

        if _is_garbage_output(raw_response):
            logger.warning(
                "Vision model returned garbage output (attempt %d/%d): %r",
                attempt, _OCR_MAX_RETRIES, raw_response[:100],
            )
            last_error = "Garbage output"
            time.sleep(_OCR_RETRY_DELAY)
            continue

        # Got a usable response — break out of retry loop
        break
    else:
        # All retries exhausted
        raise VisionOCRError(
            f"Vision model failed after {_OCR_MAX_RETRIES} attempts. "
            f"Last error: {last_error}. Last response: {raw_response[:200] if raw_response else '(none)'}"
        )

    logger.info("Vision OCR raw response (first 500 chars): %s", raw_response[:500])

    try:
        parsed = _extract_json(raw_response)
        text = str(parsed.get("text", "")).strip()
        logger.info("Parsed JSON text field (length %d): %s", len(text), text[:200])
    except Exception as exc:
        logger.warning("Vision OCR response wasn't valid JSON, using raw text: %s", exc)
        text = raw_response.strip()

    repetition_reason = _repetition_reason(text)
    if repetition_reason:
        logger.warning("Rejected hallucinated Vision OCR output: %s", repetition_reason)
        confidence = 0.0
    else:
        confidence = _compute_confidence(text)
    logger.info("Vision OCR confidence: %.1f%%, text length: %d chars, %d words",
                confidence, len(text), len(text.split()))

    return {
        "raw_text": text,
        "confidence": confidence,
        "rejection_reason": repetition_reason,
    }


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
    # Retain raw text for a teacher's audit but never pass a rejected model
    # continuation into retrieval or automatic grading.
    cleaned = "" if result.get("rejection_reason") else clean_text(result["raw_text"])

    below_threshold = result["confidence"] < settings.OCR_CONFIDENCE_THRESHOLD
    if below_threshold:
        logger.warning(
            "OCR confidence %.1f%% is below threshold %s%% for image %s. "
            "Extracted text (first 200 chars): %s. Rejection reason: %s",
            result["confidence"], settings.OCR_CONFIDENCE_THRESHOLD,
            image_path, result["raw_text"][:200], result.get("rejection_reason"),
        )

    return {
        "raw_text": result["raw_text"],
        "cleaned_text": cleaned,
        "confidence": result["confidence"],
        "below_threshold": below_threshold,
    }
