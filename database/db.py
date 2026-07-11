#run "pip install -r requirements.txt" for dp.py and api.py to work

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

SERVICE_ACCOUNT_PATH = "divicondb-firebase-adminsdk-fbsvc-71fd022ae2.json"
VALID_ACCOUNT_TYPES = ["checking", "savings", "credit"]
ALLOWED_UPDATE_FIELDS = {"amount", "category", "description"}

cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

# --- USERS --- 

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


# --- CATEGORIES --- 



# --- TRANSACTIONS ---

# adds a new transaction
def add_transaction(user_id, amount, category, description=""):
    if not amount or not isinstance(amount, str):
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


#SUMMARY