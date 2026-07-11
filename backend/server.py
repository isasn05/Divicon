"""
Camera test server — a self-contained harness for testing the scanner
with a live phone/webcam camera.

    python camera_test/server.py

Opens on http://localhost:5000 (camera works on localhost without HTTPS).
To test from your phone, use ngrok:  ngrok http 5000

This is NOT production infrastructure — it's a dev tool. The UI team
will build their own camera flow and call scan_receipt() from their backend.
"""

import base64
import json

import numpy as np
import cv2
from flask import Flask, request, jsonify, send_from_directory

# Import from the parent package — works because we add the project root
# to sys.path below.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from receipt_scanner import scan_receipt

app = Flask(__name__, static_folder=".", static_url_path="")


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/scan", methods=["POST"])
def scan():
    """Accept a base64 data-URL from the camera JS, run the scanner."""
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


if __name__ == "__main__":
    print("\n  Camera test harness running at http://localhost:5000")
    print("  Phone testing: ngrok http 5000\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
