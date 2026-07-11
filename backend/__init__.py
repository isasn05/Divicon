"""
receipt_scanner — standalone receipt scanning library.

This is the ONE function your teammates need:

    from receipt_scanner import scan_receipt

    result = scan_receipt("photo.jpg")          # file path
    result = scan_receipt(image_bytes)          # raw bytes from an upload
    result = scan_receipt(numpy_bgr_array)      # already-decoded image

It never raises for bad photos — errors come back inside the dict, so the
backend team just serializes `result` to JSON and the UI team renders it.

Success shape:
    {
      "ok": True,
      "preprocessing": {"blur_score", "receipt_detected", "rotation_applied_deg"},
      "ocr": {"text", "mean_confidence", "words": [...]},
      "receipt": {"merchant", "date", "items", "subtotal", "tax", "total",
                  "items_sum", "checksum_ok"},
    }

Failure shape:
    {
      "ok": False,
      "error": "image_too_blurry" | "no_text_found" | "invalid_image",
      "message": human-readable detail,
      "hint": what the end user should do about it,
    }
"""

from pathlib import Path

import cv2
import numpy as np

from .preprocess import preprocess_receipt, BlurryImageError, NoReceiptFoundError
from .ocr import run_ocr
from .parser import parse_receipt

__version__ = "0.1.0"
__all__ = ["scan_receipt"]


def scan_receipt(image) -> dict:
    """Run the full pipeline on a file path, raw bytes, or BGR numpy array."""
    try:
        img = _to_array(image)
    except ValueError as exc:
        return _fail("invalid_image", str(exc), "Send a valid JPEG or PNG.")

    try:
        processed, pre_meta = preprocess_receipt(img)
    except BlurryImageError as exc:
        return _fail(
            "image_too_blurry", str(exc),
            "Hold the camera steady and make sure the receipt is in focus.",
        )
    except NoReceiptFoundError as exc:
        return _fail(
            "no_receipt_detected", str(exc),
            "Place the receipt on a contrasting background and fill the frame.",
        )

    ocr_result = run_ocr(processed)
    if not ocr_result["text"].strip():
        return _fail(
            "no_text_found", "OCR ran but found no readable text.",
            "Improve lighting, avoid glare, and retake the photo.",
        )

    receipt = parse_receipt(ocr_result["text"], ocr_result["words"])

    return {
        "ok": True,
        "preprocessing": pre_meta,
        "ocr": {
            "text": ocr_result["text"],
            "mean_confidence": ocr_result["mean_confidence"],
            "words": ocr_result["words"],
        },
        "receipt": receipt,
    }


def _to_array(image) -> np.ndarray:
    """Normalize path / bytes / array input to a BGR numpy array."""
    if isinstance(image, np.ndarray):
        if image.ndim == 2:  # grayscale -> BGR
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        return image

    if isinstance(image, (str, Path)):
        path = Path(image)
        if not path.exists():
            raise ValueError(f"File not found: {path}")
        image = path.read_bytes()

    if isinstance(image, (bytes, bytearray)):
        arr = np.frombuffer(bytes(image), dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image data (expected JPEG/PNG).")
        return img

    raise ValueError(f"Unsupported input type: {type(image).__name__}")


def _fail(error: str, message: str, hint: str) -> dict:
    return {"ok": False, "error": error, "message": message, "hint": hint}
