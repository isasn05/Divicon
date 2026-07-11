#run "pip install -r requirements.txt" for dp.py and api.py to work

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

SERVICE_ACCOUNT_PATH = "divicondb-firebase-adminsdk-fbsvc-71fd022ae2.json"
cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

#USERS

# creates a new user for the database
# RETURNS USER ID
def create_user(name, email):
# check for no input
    if not name or not isinstance(name, str):
        raise ValueError("name must be a non-empty string")
    if not email or not isinstance(email, str):
        raise ValueError("email must be a non-empty string")
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
    """Check if any user document already has this email."""
    docs = db.collection("users").where("email", "==", email).limit(1).stream()

    results = list(docs)
    return len(results) > 0



#ACCOUNTS
#functions for adding different accounts like checking, credit, savings, etc.

def create_account(user_id, name, account_type, starting_balance=0):
    doc_ref = db.collection("users").document(user_id).collection("accounts").document()

    doc_ref.set({
        "name": name,
        "type": account_type,
        "balance": starting_balance,              # Default is zero
        "created_at": firestore.SERVER_TIMESTAMP  # Firebase fills in the real time
    })

    # doc_ref.id is the auto-generated ID Firestore just created.
    return doc_ref.id



#CATEGORIES



#TRANSACTIONS




#SUMMARY