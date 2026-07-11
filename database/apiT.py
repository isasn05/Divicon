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
import dbT  # your existing file — untouched, just imported and reused

app = Flask(__name__)

# CORS = Cross-Origin Resource Sharing. Browsers block JS from calling a
# different "origin" (domain/port) than the page itself, by default, for
# security reasons. Since your frontend (e.g. localhost:3000) and this API
# (localhost:5000) are different origins, CORS(app) tells the browser
# "it's fine, let requests through." Without this line, every fetch() call
# from the frontend would silently fail with a CORS error.
CORS(app)


# ---------------------------------------------------------------------------
# HOW ROUTES WORK
#
# @app.route("/path", methods=["GET"]) is like registering a callback:
# "whenever an HTTP request hits this URL with this method, run this
# function." GET = "give me data" (like a read/SELECT). POST = "here's
# data, create/do something with it" (like a write/INSERT).
#
# Anything in <angle_brackets> in the route is a variable pulled straight
# from the URL — e.g. /accounts/<user_id> lets user_id be whatever the
# caller puts there.
# ---------------------------------------------------------------------------


# ----------------------- ACCOUNTS -----------------------------------------

@app.route("/accounts/<user_id>", methods=["GET"])
def get_accounts(user_id):
    # Just calls your existing db.py function and wraps the result as JSON.
    # jsonify() converts a Python list/dict into a JSON string the
    # frontend can parse — JSON is the common "language" both sides
    # understand, even though Python calls it a dict and JS calls it an object.
    return jsonify(dbT.get_accounts(user_id))


@app.route("/accounts/<user_id>", methods=["POST"])
def create_account(user_id):
    # request.json parses the JSON body the frontend sent in its fetch()
    # call, turning it back into a Python dict.
    data = request.json
    account_id = dbT.create_account(
        user_id,
        data["name"],
        data["account_type"],
        data.get("starting_balance", 0)  # .get() with a default, in case frontend omits it
    )
    return jsonify({"id": account_id})


# ----------------------- CATEGORIES ----------------------------------------

@app.route("/categories/<user_id>", methods=["GET"])
def get_categories(user_id):
    return jsonify(dbT.get_categories(user_id))


@app.route("/categories/<user_id>", methods=["POST"])
def create_category(user_id):
    data = request.json
    category_id = dbT.create_category(
        user_id,
        data["name"],
        data.get("monthly_budget")
    )
    return jsonify({"id": category_id})


# ----------------------- TRANSACTIONS --------------------------------------

@app.route("/transactions/<user_id>", methods=["GET"])
def get_transactions(user_id):
    # Example of an optional query parameter: /transactions/user_123?category=Groceries
    # request.args is where ?key=value pairs in the URL show up.
    category = request.args.get("category")

    if category:
        return jsonify(dbT.get_transactions_by_category(user_id, category))
    return jsonify(dbT.get_transactions(user_id))


@app.route("/transactions/<user_id>", methods=["POST"])
def add_transaction(user_id):
    data = request.json
    tx_id = dbT.add_transaction(
        user_id,
        data["account_id"],
        data["amount"],
        data["category"],
        data.get("description", "")
    )
    return jsonify({"id": tx_id})


@app.route("/transactions/<user_id>/<transaction_id>", methods=["PATCH"])
def update_transaction(user_id, transaction_id):
    # PATCH = "partially update an existing thing" — standard REST convention
    # for updates, as opposed to POST (create) or DELETE (remove).
    updates = request.json
    dbT.update_transaction(user_id, transaction_id, updates)
    return jsonify({"status": "updated"})


@app.route("/transactions/<user_id>/<transaction_id>", methods=["DELETE"])
def delete_transaction(user_id, transaction_id):
    dbT.delete_transaction(user_id, transaction_id)
    return jsonify({"status": "deleted"})


# ----------------------- SUMMARY --------------------------------------------

@app.route("/summary/<user_id>/<int:year>/<int:month>", methods=["GET"])
def get_monthly_summary(user_id, year, month):
    # <int:year> tells Flask to convert that URL segment straight to a
    # Python int, instead of leaving it as a string — a small convenience.
    return jsonify(dbT.get_monthly_summary(user_id, year, month))


# ---------------------------------------------------------------------------
# ENTRY POINT — only runs when you execute "python api.py" directly.
# debug=True auto-restarts the server when you save changes, and shows
# detailed errors in the browser — very handy for a hackathon, but turn
# it off before anything resembling a public deploy.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
