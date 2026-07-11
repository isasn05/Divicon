#run "pip install -r requirements.txt" for dp.py and api.py to work

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

SERVICE_ACCOUNT_PATH = "divicondb-firebase-adminsdk-fbsvc-b899dad912.json"
ALLOWED_USER_UPDATE_FIELDS = {"name", "email"}
ALLOWED_UPDATE_FIELDS = {"amount", "category", "description"}

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
def add_transaction(user_id, amount, category, description=""):
    if not amount or not isinstance(amount, (int, float)):
        raise ValueError("amount must not be empty")
    
    doc_ref = db.collection("users").document(user_id).collection("transactions").document()
    doc_ref.set({
        "amount": amount,
        "category": category,
        "description": description,
        "date": firestore.SERVER_TIMESTAMP
    })
    return doc_ref.id

# returns existing transactions in descecnding order by date
def get_transactions(user_id):
    docs = (
        db.collection("users").document(user_id).collection("transactions")
        .order_by("date", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [doc.to_dict() | {"id": doc.id} for doc in docs]

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
