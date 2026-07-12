"""
Camera test server - Windows compatible

NEW IN THIS VERSION:
  Saved receipts. When you scan a receipt and press "Save to finances",
  the frontend POSTs the photo + parsed data to /api/receipts. The server
  stores the data in receipts_data/receipts.json and the photo as an image
  file next to it. The finances page reads the list back with GET
  /api/receipts, and the receipt detail page (receipt.html) reads a single
  receipt with GET /api/receipts/<id> and its photo from
  GET /api/receipts/<id>/image.

  This is simple file-based storage for the dev harness — no database
  needed. Delete the receipts_data folder to wipe everything.
"""

import base64
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
from flask import Flask, request, jsonify, send_from_directory

# Add backend folder to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

# Now we can import from backend
from backend import scan_receipt

app = Flask(__name__, static_folder="frontend", static_url_path="")

# Define where frontend files are located
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

# Where saved receipts live (created automatically on first run)
DATA_DIR = Path(__file__).resolve().parent / "receipts_data"
DATA_DIR.mkdir(exist_ok=True)
RECEIPTS_JSON = DATA_DIR / "receipts.json"


# ----------------------- receipt storage helpers ---------------------------

def _load_receipts() -> list:
    """Read the saved receipts list from disk. Returns [] if none yet."""
    if RECEIPTS_JSON.exists():
        try:
            return json.loads(RECEIPTS_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_receipts(receipts: list) -> None:
    RECEIPTS_JSON.write_text(
        json.dumps(receipts, indent=2), encoding="utf-8"
    )


def _field_value(receipt: dict, key: str):
    """Parsed fields look like {"value": ..., "confidence": ...}."""
    field = receipt.get(key) or {}
    return field.get("value") if isinstance(field, dict) else None


# ----------------------- pages ---------------------------------------------

@app.route("/")
def index():
    """Serve the finances page as the homepage"""
    return send_from_directory(str(FRONTEND_DIR), "finances.html")

@app.route("/scanner")
def scanner():
    """Serve the camera scanner page"""
    return send_from_directory(str(FRONTEND_DIR), "index.html")

@app.route("/finances")
def finances():
    """Serve the finances page (redirect or serve directly)"""
    return send_from_directory(str(FRONTEND_DIR), "finances.html")

@app.route("/camera.js")
def camera_js():
    """Serve the camera JavaScript"""
    return send_from_directory(str(FRONTEND_DIR), "camera.js")

@app.route("/Nick.jpg")
def nick_image():
    """Serve the sample image"""
    return send_from_directory(str(Path(__file__).resolve().parent), "Nick.jpg")


# ----------------------- scan ----------------------------------------------

@app.route("/api/scan", methods=["POST"])
def scan():
    """Handle receipt scanning"""
    body = request.get_json(silent=True) or {}
    data_url = body.get("image", "")

    if "," in data_url:
        data_url = data_url.split(",", 1)[1]

    try:
        raw = base64.b64decode(data_url)
    except Exception:
        return jsonify({"ok": False, "error": "invalid_image",
                        "message": "Bad base64", "hint": "Try again."}), 400

    result = scan_receipt(raw)
    return jsonify(result)


# ----------------------- saved receipts ------------------------------------

@app.route("/api/receipts", methods=["GET"])
def list_receipts():
    """All saved receipts, newest first (for the finances page)."""
    receipts = _load_receipts()
    receipts.sort(key=lambda r: r.get("saved_at", ""), reverse=True)
    return jsonify(receipts)


@app.route("/api/receipts", methods=["POST"])
def save_receipt():
    """
    Save a scanned receipt. Expects JSON:
        { "image": <data URL from the camera>,
          "receipt": <the "receipt" object from /api/scan>,
          "ocr_confidence": <number, optional> }
    """
    body = request.get_json(silent=True) or {}
    receipt = body.get("receipt") or {}
    image = body.get("image", "")

    if not receipt:
        return jsonify({"ok": False, "error": "missing_receipt",
                        "message": "No receipt data supplied."}), 400

    rid = uuid.uuid4().hex[:12]

    # ---- save the photo to disk ----
    image_file = None
    if image:
        ext = ".png" if image.startswith("data:image/png") else ".jpg"
        b64 = image.split(",", 1)[1] if "," in image else image
        try:
            (DATA_DIR / f"{rid}{ext}").write_bytes(base64.b64decode(b64))
            image_file = f"{rid}{ext}"
        except Exception:
            image_file = None  # photo failed to save, keep the data anyway

    # ---- save the parsed data ----
    entry = {
        "id": rid,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "image_file": image_file,
        "merchant": _field_value(receipt, "merchant"),
        "date": _field_value(receipt, "date"),          # "YYYY-MM-DD" or None
        "subtotal": _field_value(receipt, "subtotal"),
        "tax": _field_value(receipt, "tax"),
        "total": _field_value(receipt, "total"),
        "items": receipt.get("items", []),
        "items_sum": receipt.get("items_sum"),
        "checksum_ok": receipt.get("checksum_ok"),
        "ocr_confidence": body.get("ocr_confidence"),
    }

    receipts = _load_receipts()
    receipts.append(entry)
    _save_receipts(receipts)

    return jsonify({"ok": True, "id": rid})


@app.route("/api/receipts/<rid>", methods=["GET"])
def get_receipt(rid):
    """One saved receipt (for the receipt detail page)."""
    for r in _load_receipts():
        if r.get("id") == rid:
            return jsonify(r)
    return jsonify({"error": "not_found",
                    "message": "No receipt with that id."}), 404


@app.route("/api/receipts/<rid>/image", methods=["GET"])
def get_receipt_image(rid):
    """The saved photo for one receipt."""
    for r in _load_receipts():
        if r.get("id") == rid and r.get("image_file"):
            path = DATA_DIR / r["image_file"]
            if path.exists():
                return send_from_directory(str(DATA_DIR), r["image_file"])
    return jsonify({"error": "not_found"}), 404


# ----------------------- static fallback -----------------------------------

@app.route("/<path:path>")
def serve_static(path):
    """Serve any other static files from frontend folder"""
    return send_from_directory("frontend", path)

if __name__ == "__main__":
    # print("\nReceipt Scanner running at http://localhost:5000")
    print("Finances page: http://localhost:5000")
    # print("Scanner page: http://localhost:5000/scanner")
    # print("On phone: http://172.20.10.12:5000 (if on same network)\n")
    app.run(debug=True, host="0.0.0.0", port=5000)