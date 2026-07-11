"""
Image preprocessing pipeline for receipt photos.

Steps:
  1. Blur detection      (variance of Laplacian — reject shaky photos early)
  2. Edge detection      (Canny on a blurred grayscale copy)
  3. Receipt contour     (largest 4-point contour = the receipt)
  4. Perspective crop    (warp the receipt to a flat, top-down rectangle)
  5. Deskew / rotation   (straighten leftover tilt using minAreaRect)
  6. OCR prep            (adaptive threshold for crisp black-on-white text)
"""

import cv2
import numpy as np

BLUR_THRESHOLD = 60.0  # Laplacian variance below this = too blurry to OCR reliably


class BlurryImageError(Exception):
    pass


class NoReceiptFoundError(Exception):
    pass


def preprocess_receipt(img: np.ndarray) -> tuple[np.ndarray, dict]:
    """Run the full pipeline. Returns (ocr_ready_image, metadata)."""
    meta = {}

    # 1. Blur detection ------------------------------------------------------
    blur_score = measure_blur(img)
    meta["blur_score"] = round(blur_score, 1)
    if blur_score < BLUR_THRESHOLD:
        raise BlurryImageError(
            f"Image is too blurry (sharpness {blur_score:.0f}, need ≥ {BLUR_THRESHOLD:.0f})."
        )

    # 2–4. Edge detection -> contour -> perspective crop ----------------------
    quad = find_receipt_contour(img)
    if quad is not None:
        img = four_point_transform(img, quad)
        meta["receipt_detected"] = True
    else:
        # Fall back to the full frame rather than failing outright — the user
        # may have already cropped tightly.
        meta["receipt_detected"] = False

    # 5. Deskew ---------------------------------------------------------------
    img, angle = deskew(img)
    meta["rotation_applied_deg"] = round(angle, 2)

    # 6. Binarize for OCR ------------------------------------------------------
    ocr_ready = binarize(img)
    return ocr_ready, meta


def measure_blur(img: np.ndarray) -> float:
    """Higher = sharper. Classic variance-of-Laplacian focus measure."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def find_receipt_contour(img: np.ndarray) -> np.ndarray | None:
    """Find the largest 4-corner contour — assumed to be the receipt."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    frame_area = img.shape[0] * img.shape[1]
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        area = cv2.contourArea(c)
        if area < 0.15 * frame_area:  # too small to be the receipt
            break
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            return approx.reshape(4, 2).astype(np.float32)
    return None


def four_point_transform(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Warp the quadrilateral `pts` to a flat top-down rectangle (auto crop)."""
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect

    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))

    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(img, matrix, (width, height))


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order corners: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left has smallest x+y
    rect[2] = pts[np.argmax(s)]   # bottom-right has largest x+y
    rect[1] = pts[np.argmin(d)]   # top-right has smallest y-x
    rect[3] = pts[np.argmax(d)]   # bottom-left has largest y-x
    return rect


def deskew(img: np.ndarray) -> tuple[np.ndarray, float]:
    """Straighten small residual tilt so text lines are horizontal."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 100:
        return img, 0.0

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.3 or abs(angle) > 15:  # ignore noise / wild estimates
        return img, 0.0

    (h, w) = img.shape[:2]
    matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    rotated = cv2.warpAffine(
        img, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated, angle


def binarize(img: np.ndarray) -> np.ndarray:
    """Adaptive threshold: crisp black text on white, robust to uneven light."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)  # denoise, keep edges
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )
