"""
CLI for testing the scanner without any UI or backend.

    python -m receipt_scanner path/to/photo.jpg
    python -m receipt_scanner photo.jpg --debug   # also saves the processed image

Prints the full JSON result, exactly what the backend team will receive.
"""

import argparse
import json
import sys

from . import scan_receipt


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan a receipt photo.")
    ap.add_argument("image", help="Path to a receipt photo (JPEG/PNG)")
    ap.add_argument("--debug", action="store_true",
                    help="Save the preprocessed image next to the input as *_processed.png")
    args = ap.parse_args()

    if args.debug:
        _save_debug_image(args.image)

    result = scan_receipt(args.image)
    print(json.dumps(result, indent=2, default=float))
    return 0 if result["ok"] else 1


def _save_debug_image(path: str) -> None:
    """Write the binarized image the OCR actually sees — great for tuning."""
    import cv2
    from .preprocess import preprocess_receipt

    img = cv2.imread(path)
    if img is None:
        return
    try:
        processed, _ = preprocess_receipt(img)
        out = path.rsplit(".", 1)[0] + "_processed.png"
        cv2.imwrite(out, processed)
        print(f"[debug] preprocessed image saved to {out}", file=sys.stderr)
    except Exception as exc:
        print(f"[debug] preprocessing failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
