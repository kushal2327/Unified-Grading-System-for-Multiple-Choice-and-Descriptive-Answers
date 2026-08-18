"""
apps/descriptive_grading/pipeline/preprocessing.py

Phase 2, Step 1: image preprocessing for a photo of a handwritten
answer sheet, ahead of running Tesseract OCR.

Pipeline: grayscale -> Gaussian blur (light, to preserve handwriting
stroke detail) -> adaptive thresholding (binarization).
"""
import cv2
import numpy as np


def preprocess_image(image_path: str) -> np.ndarray:
    """
    Load an image from disk and run the full preprocessing pipeline.
    Returns a binary (black/white) OpenCV image ready for OCR.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image at {image_path}. "
                          f"Make sure it's a valid image file (jpg/png/etc).")

    return preprocess_array(img)


def preprocess_array(img: np.ndarray) -> np.ndarray:
    """Same preprocessing pipeline, operating on an already-loaded image array."""
    # 1. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Gaussian blur - small 3x3 kernel to remove noise while
    #    preserving handwriting stroke detail (a bigger kernel would
    #    blur thin pen strokes too much, unlike for printed MCQ sheets).
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # 3. Adaptive thresholding - handles uneven lighting/shadows across
    #    a photographed page better than a single global threshold.
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2,
    )

    return binary


def save_debug_image(binary_img: np.ndarray, output_path: str) -> None:
    """Optional helper: save the preprocessed image so a developer can
    visually sanity-check what Tesseract will actually see."""
    cv2.imwrite(output_path, binary_img)
