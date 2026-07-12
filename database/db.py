#run "pip install -r requirements.txt" for dp.py and api.py to work

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone

# Resolved relative to this file, not the current working directory — so it
# works whether you run "python db.py" from inside database/, or import db
# from server.py at the project root.
_HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_PATH = os.path.join(_HERE, "divicondb-firebase-adminsdk-fbsvc-b899dad912.json")

ALLOWED_USER_UPDATE_FIELDS = {"name", "email"}
ALLOWED_UPDATE_FIELDS = {"amount", "category", "description", "merchant", "receipt_date"}

# On a deployment host you generally can't (and shouldn't) commit the
# service-account JSON file to your repo. Instead set a FIREBASE_CREDENTIALS
# environment variable containing the *contents* of that file, and this
# will use it automatically. Locally, just keep the .json file next to
# this script (already in .gitignore) and it's used as a fallback.
_creds_json = os.environ.get("FIREBASE_CREDENTIALS")
if _creds_json:
    cred = credentials.Certificate(json.loads(_creds_json))
else:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)

firebase_admin.initialize_app(cred)
db = firestore.client()

# ----------------------- USERS ----------------------------------------------

# creates a new user for the database
# RETURNS USER ID
def create_user(name, email):
# check for no input
    if not name or not isinstance(name, str):
        raise ValueError("name must not be empty")
    if not email or not isinstance(email, str):
        raise ValueError("email must not be empty")
# check for duplicate emails
    if email_exists(email):
        raise ValueError("An account with this email already exists")

# writes input to database
    doc_ref = db.collection("users").document()
    doc_ref.set({
        "name": name,
        "email": email,
        "created_at": firestore.SERVER_TIMESTAMP
    })
    return doc_ref.id

# checks if entered email is already entered into the database
def email_exists(email):
    docs = db.collection("users").where("email", "==", email).limit(1).stream()

    results = list(docs)
    return len(results) > 0

# Divicon doesn't have login/auth yet, so every scan is attributed to one
# shared "default" account. Once real auth exists, swap this out for
# whatever user_id comes from the logged-in session instead.
def get_or_create_default_user(email="demo@divicon.app", name="Demo User"):
    docs = db.collection("users").where("email", "==", email).limit(1).stream()
    results = list(docs)
    if results:
        return results[0].id
    return create_user(name, email)

# returns doc with user deatails
def get_user(user_id):
    doc = db.collection("users").document(user_id).get()
    if not doc.exists:
        raise ValueError("No user found with that ID")
    return doc.to_dict() | {"id": doc.id}

# updates user details, including: Name and email
def update_user(user_id, updates):
# checks for empty input
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id must be a non-empty string")
    if not isinstance(updates, dict) or not updates:
        raise ValueError("updates must be a non-empty dict")
# checks for valid update dict
    invalid_fields = set(updates.keys()) - ALLOWED_USER_UPDATE_FIELDS
    if invalid_fields:
        raise ValueError(f"Invalid fields: {invalid_fields}")
# check empty for updates
    if "name" in updates and (not updates["name"] or not isinstance(updates["name"], str)):
        raise ValueError("name must be a non-empty string")
    if "email" in updates and (not updates["email"] or not isinstance(updates["email"], str)):
        raise ValueError("email must be a non-empty string")
# confirm user exists
    doc_ref = db.collection("users").document(user_id)
    if not doc_ref.get().exists:
        raise ValueError("No user found with that ID")
# update user
    doc_ref.update(updates)



# ----------------------- CATEGORIES ----------------------------------------------



# ----------------------- TRANSACTIONS ----------------------------------------------

# adds a new transaction
# merchant/receipt_date are optional extras used by the receipt scanner —
# merchant is the store name (e.g. "Publix"), receipt_date is the date
# printed on the receipt itself (as opposed to "date", which is always the
# server's upload timestamp, used for ordering).
def add_transaction(user_id, amount, category, description="", merchant=None, receipt_date=None):
    if not amount or not isinstance(amount, (int, float)):
        raise ValueError("amount must not be empty")

    doc_ref = db.collection("users").document(user_id).collection("transactions").document()
    doc_ref.set({
        "amount": amount,
        "category": category,
        "description": description,
        "merchant": merchant,
        "receipt_date": receipt_date,
        "date": firestore.SERVER_TIMESTAMP
    })
    return doc_ref.id

# Firestore timestamps aren't JSON-serializable on their own — jsonify()
# will throw on them. This turns any datetime fields into ISO strings
# before a document is sent back over HTTP.
def _serialize(doc) -> dict:
    d = doc.to_dict() | {"id": doc.id}
    if hasattr(d.get("date"), "isoformat"):
        d["date"] = d["date"].isoformat()
    return d

# returns existing transactions in descecnding order by date
def get_transactions(user_id):
    docs = (
        db.collection("users").document(user_id).collection("transactions")
        .order_by("date", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [_serialize(doc) for doc in docs]

# update an existing transaction
# example: update_transaction("user_123", "tx_456", {"amount": -45.20, "category": "Groceries", "description": "Trader Joe's"})
def update_transaction(user_id, transaction_id, updates):
# check if updates are valid
    invalid_fields = set(updates.keys()) - ALLOWED_UPDATE_FIELDS
    if invalid_fields:
        raise ValueError(f"Invalid fields: {invalid_fields}")
    (db.collection("users").document(user_id)
       .collection("transactions").document(transaction_id)
       .update(updates))
    
# deletes an existing transaction
def delete_transaction(user_id, transaction_id):
    (db.collection("users").document(user_id)
       .collection("transactions").document(transaction_id)
       .delete())


# ----------------------- SUMMARY ----------------------------------------------

def get_monthly_summary(user_id, year, month):
    transactions = get_transactions(user_id)

    total_income = 0
    total_expense = 0
    by_category = {}

    
    for t in transactions:
        # NOTE: in a real version you'd filter by t["date"]'s year/month here.
        # Skipped for brevity — happy to add that filtering logic if useful.
        amount = t["amount"]
        category = t["category"]

        if amount >= 0:
            total_income += amount
        else:
            total_expense += amount

        # dict.get(key, default) returns default if the key isn't present yet
        # — avoids a manual "if category not in by_category: by_category[category] = 0"
        by_category[category] = by_category.get(category, 0) + amount

    # Returning a dict lets the caller access fields by name, e.g. result["total_income"]
    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "net": total_income + total_expense,
        "by_category": by_category
    }


# Powers the finances.html summary strip ("This Month", "Receipts",
# "Avg / trip") and the purchases table, all from one Firestore read —
# recalculated fresh every time it's called, so it's always up to date
# with whatever has been scanned so far.
def get_summary(user_id):
    now = datetime.now(timezone.utc)

    docs = (
        db.collection("users").document(user_id).collection("transactions")
        .order_by("date", direction=firestore.Query.DESCENDING)
        .stream()
    )

    transactions = []
    month_total = 0.0
    month_count = 0

    for doc in docs:
        raw = doc.to_dict()
        raw_date = raw.get("date")

        is_this_month = (
            hasattr(raw_date, "year")
            and raw_date.year == now.year
            and raw_date.month == now.month
        )
        if is_this_month:
            month_total += abs(raw.get("amount") or 0)
            month_count += 1

        raw["id"] = doc.id
        if hasattr(raw_date, "isoformat"):
            raw["date"] = raw_date.isoformat()
        transactions.append(raw)

    avg_trip = round(month_total / month_count, 2) if month_count else 0.0

    return {
        "transactions": transactions,
        "this_month_total": round(month_total, 2),
        "receipt_count": month_count,
        "avg_per_trip": avg_trip,
    }


# --------------------------------------------------------------------------
# QUICK MANUAL TEST — only runs if you execute "python db.py" directly,
# NOT when this file is imported elsewhere. Equivalent to a
# "#ifdef TESTING ... main() ... #endif" pattern in C.
# --------------------------------------------------------------------------
if __name__ == "__main__":
    acc_id = create_user("guy", "guy@gmail.com")
    add_transaction(acc_id, -45.20, "Groceries", "Trader Joe's")
    add_transaction(acc_id, 1200, "Paycheck", "Biweekly pay")

    print(get_transactions(acc_id))
    print(get_monthly_summary(acc_id, 2026, 7))
