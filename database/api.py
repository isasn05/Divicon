"""
api.py — a thin HTTP bridge between db.py (Python/Firebase) and the
frontend (JavaScript/HTML).

WHY THIS FILE EXISTS:
Browsers can't import Python files. The only language-agnostic way for
JavaScript to talk to Python code is over HTTP — the same protocol used
for every website. This file uses Flask (a small Python web framework)
to turn each of your db.py functions into a URL. The frontend hits that
URL with a normal fetch() call, gets JSON back, and never needs to know
Python or Firestore exist.

Think of this as a translator sitting between two people who speak
different languages: JS speaks "HTTP requests", Python speaks "function
calls". This file converts one into the other.

INSTALL:
    pip install flask flask-cors

RUN:
    python api.py
    (starts a local server, by default at http://localhost:5000)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import db  # db.py file import

app = Flask(__name__)

# tells browser program is safe
CORS(app)

# ----------------------- USERS ----------------------------------------------

@app.route("/users", methods=["POST"])
def create_user():
    data = request.json
    try:
        user_id = db.create_user(data["name"], data["email"])
        return jsonify({"id": user_id})
    except ValueError as e:
        # str(e) pulls out the message passed to raise ValueError(...) in db.py
        return jsonify({"error": str(e)}), 400


@app.route("/users/<user_id>", methods=["GET"])
def get_user(user_id):
    try:
        return jsonify(db.get_user(user_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

@app.route("/users/<user_id>", methods=["PATCH"])
def update_user(user_id):
    data = request.json
    try:
        db.update_user(user_id, data)
        return jsonify({"status": "updated"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    

# ----------------------- CATEGORIES ----------------------------------------



# ----------------------- TRANSACTIONS --------------------------------------

@app.route("/transactions/<user_id>", methods=["GET"])
def get_transactions(user_id):
    # Example of an optional query parameter: /transactions/user_123?category=Groceries
    # request.args is where ?key=value pairs in the URL show up.
    category = request.args.get("category")

    if category:
        return jsonify(db.get_transactions_by_category(user_id, category))
    return jsonify(db.get_transactions(user_id))


@app.route("/transactions/<user_id>", methods=["POST"])
def add_transaction(user_id):
    data = request.json
    tx_id = db.add_transaction(
        user_id,
        data["amount"],
        data["category"],
        data.get("description", ""),
        merchant=data.get("merchant"),
        receipt_date=data.get("receipt_date"),
    )
    return jsonify({"id": tx_id})


@app.route("/summary/<user_id>", methods=["GET"])
def summary(user_id):
    return jsonify(db.get_summary(user_id))


@app.route("/transactions/<user_id>/<transaction_id>", methods=["PATCH"])
def update_transaction(user_id, transaction_id):
    # PATCH = "partially update an existing thing" — standard REST convention
    # for updates, as opposed to POST (create) or DELETE (remove).
    updates = request.json
    db.update_transaction(user_id, transaction_id, updates)
    return jsonify({"status": "updated"})


@app.route("/transactions/<user_id>/<transaction_id>", methods=["DELETE"])
def delete_transaction(user_id, transaction_id):
    db.delete_transaction(user_id, transaction_id)
    return jsonify({"status": "deleted"})


# ----------------------- SUMMARY ----------------------------------------
