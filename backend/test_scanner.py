"""Run with: pytest"""
import cv2
import numpy as np

from receipt_scanner import scan_receipt
from receipt_scanner.parser import parse_receipt

SAMPLE_TEXT = """TRADER JOES
07/02/2026
BANANAS 1.99
OAT MILK 3.49
FROZEN PIZZA 5.99
SUBTOTAL 11.47
TAX 0.92
TOTAL 12.39
VISA 12.39
"""

def _fake_receipt_photo():
    """White receipt on dark background, slightly rotated, with printed text."""
    canvas = np.full((900, 700, 3), 40, np.uint8)
    paper = np.full((700, 400, 3), 245, np.uint8)
    for i, t in enumerate(["CORNER CAFE", "07/02/2026", "LATTE 4.50",
                           "BAGEL 3.25", "TOTAL 7.75"]):
        cv2.putText(paper, t, (30, 90 + i * 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (20, 20, 20), 2)
    canvas[100:800, 150:550] = paper
    m = cv2.getRotationMatrix2D((350, 450), 3, 1.0)
    return cv2.warpAffine(canvas, m, (700, 900), borderValue=(40, 40, 40))

def test_parser_fields():
    r = parse_receipt(SAMPLE_TEXT, [])
    assert r["merchant"]["value"] == "Trader Joes"
    assert r["date"]["value"] == "2026-07-02"
    assert r["total"]["value"] == 12.39
    assert len(r["items"]) == 3
    assert r["checksum_ok"] is True

def test_full_pipeline():
    result = scan_receipt(_fake_receipt_photo())
    assert result["ok"] is True
    assert result["preprocessing"]["receipt_detected"] is True
    assert result["receipt"]["total"]["value"] == 7.75

def test_blurry_photo_rejected():
    blurry = cv2.GaussianBlur(_fake_receipt_photo(), (51, 51), 0)
    result = scan_receipt(blurry)
    assert result["ok"] is False
    assert result["error"] == "image_too_blurry"

def test_invalid_input():
    result = scan_receipt(b"this is not an image")
    assert result["ok"] is False
    assert result["error"] == "invalid_image"

def test_missing_file():
    result = scan_receipt("does_not_exist.jpg")
    assert result["ok"] is False
    assert result["error"] == "invalid_image"
