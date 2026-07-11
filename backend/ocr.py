"""
OCR integration using Tesseract (via pytesseract).

Returns raw text plus per-word confidence scores, so the parser and the UI
can flag low-confidence extractions instead of silently trusting them.

Requires the Tesseract binary:
  Ubuntu/Debian: sudo apt install tesseract-ocr
  macOS:         brew install tesseract
  Windows:       https://github.com/UB-Mannheim/tesseract/wiki
"""

import numpy as np
import pytesseract
from pytesseract import Output

# PSM 6 = "assume a single uniform block of text" — a good fit for receipts.
TESSERACT_CONFIG = "--oem 3 --psm 6"


def run_ocr(img: np.ndarray) -> dict:
    """
    OCR a preprocessed (binarized) image.

    Returns:
        {
          "text": full extracted text,
          "words": [{"text", "confidence", "line"}...],
          "mean_confidence": average confidence 0–100 across real words,
        }
    """
    data = pytesseract.image_to_data(
        img, config=TESSERACT_CONFIG, output_type=Output.DICT
    )

    words = []
    lines: dict[tuple, list[str]] = {}

    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = float(data["conf"][i])
        if not text or conf < 0:  # conf == -1 means "not a word"
            continue

        line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(line_key, []).append(text)
        words.append({
            "text": text,
            "confidence": round(conf, 1),
            "line": len(lines) - 1,
        })

    full_text = "\n".join(" ".join(tokens) for tokens in lines.values())
    confs = [w["confidence"] for w in words]

    return {
        "text": full_text,
        "words": words,
        "mean_confidence": round(sum(confs) / len(confs), 1) if confs else 0.0,
    }
