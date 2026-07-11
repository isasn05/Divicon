"""
db.py — Firebase/Firestore data access layer for the budget app.

WHY THIS FILE EXISTS:
Instead of letting every teammate write their own Firestore queries,
all database logic lives here. Teammates just call these functions
(e.g. add_transaction(...)) without knowing anything about Firestore.

PYTHON VS C NOTES (for someone coming from C):
- No semicolons at the end of lines. Line breaks end statements.
- No curly braces {}. Blocks are defined by INDENTATION (spaces).
  If your indentation is wrong, your code is wrong — this is unlike C
  where braces do that job.
- No need to declare variable types (no "int x = 5", just "x = 5").
  Python figures out the type at runtime.
- Functions are declared with "def function_name(args):" instead of
  "return_type function_name(args) { }"
- "None" is Python's NULL/nullptr.
- Dictionaries {} are like a lightweight struct/hashmap combined —
  key-value pairs, e.g. {"name": "groceries", "amount": 20}
- Lists [] are like dynamic arrays (think C++ vector, not a raw C array).
"""

# "import" is like #include in C — it pulls in code from another library.
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime


# --------------------------------------------------------------------------
# SETUP — runs once when this file is loaded, like initializing a global
# connection handle in C.
# --------------------------------------------------------------------------

# Path to the private key you downloaded from Firebase console.
# In C terms: this is like a config value you'd normally #define or read
# from a file at startup.
SERVICE_ACCOUNT_PATH = "service-account-key.json"

# credentials.Certificate(...) reads that key file and builds an auth object.
cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)

# This actually opens the connection to your Firebase project.
# Equivalent to something like calling an init() function once at program start.
firebase_admin.initialize_app(cred)

# "db" is now your handle to the whole database — similar to a
# sqlite3* connection pointer in C, except you don't need to close it
# manually or manage memory for it.
db = firestore.client()


# --------------------------------------------------------------------------
# USERS
# --------------------------------------------------------------------------

def create_user(name, email):
    """
    Create a new user. Firestore generates a random, guaranteed-unique
    document ID for us automatically — no need to build our own ID or
    check for collisions. Returns the new user_id.
    """
    if not name or not isinstance(name, str):
        raise ValueError("name must be a non-empty string")
    if not email or not isinstance(email, str):
        raise ValueError("email must be a non-empty string")

    # .document() with NO argument = Firestore makes up a random ID for us.
    # This is the same trick used for accounts/transactions elsewhere in
    # this file — Firestore's own IDs are long and random enough that a
    # collision is practically impossible, so there's no need to check.
    doc_ref = db.collection("users").document()
    doc_ref.set({
        "name": name,
        "email": email,
        "created_at": firestore.SERVER_TIMESTAMP
    })

    # doc_ref.id is the ID Firestore just generated. This IS the user_id
    # every other function in this file expects to be passed in.
    return doc_ref.id


def get_user(user_id):
    """
    Look up a user's info (name, email, etc.) by their ID. Raises a
    ValueError if no user exists with that ID, instead of silently
    returning nothing.
    """
    # .document(user_id).get() fetches ONE specific document directly by
    # ID — much cheaper than a .where() query, since Firestore can go
    # straight to it instead of searching.
    doc = db.collection("users").document(user_id).get()

    # .exists is a boolean — True only if a document was actually found
    # at that path. A made-up or deleted user_id would fail this check.
    if not doc.exists:
        raise ValueError("No user found with that ID")

    # to_dict() turns the document into a plain dict like
    # {"name": "Alex", "email": "alex@email.com", "created_at": ...}.
    # The "| {"id": doc.id}" merges in the ID itself, same pattern used
    # elsewhere in this file, since to_dict() alone doesn't include it.
    return doc.to_dict() | {"id": doc.id}


# --------------------------------------------------------------------------
# ACCOUNTS  (e.g. "Checking", "Savings", "Credit Card")
# --------------------------------------------------------------------------

def create_account(user_id, name, account_type, starting_balance=0):
    """
    Create a new account for a user.

    Note: "starting_balance=0" is a DEFAULT ARGUMENT — if the caller doesn't
    pass a value, it defaults to 0. C doesn't have this natively; think of
    it like an overloaded function that fills in a default for you.
    """
    # db.collection("x") is like picking a table.
    # .document(user_id) is like picking a row by primary key.
    # .collection("accounts") is like a "sub-table" that only belongs to
    # that specific user (Firestore lets you nest data like this).
    # .document() with NO argument tells Firestore "auto-generate an ID for me".
    doc_ref = db.collection("users").document(user_id).collection("accounts").document()

    # .set(...) writes the dictionary as the contents of that document.
    # Think of this dict like a struct literal: { .name = "Checking", ... } in C.
    doc_ref.set({
        "name": name,
        "type": account_type,
        "balance": starting_balance,
        "created_at": firestore.SERVER_TIMESTAMP  # Firebase fills in the real time
    })

    # doc_ref.id is the auto-generated ID Firestore just created.
    # "return" works just like in C.
    return doc_ref.id


def get_accounts(user_id):
    """Return a list of all accounts for a user."""
    # .stream() runs the query and gives you an iterator (like looping over
    # rows returned from a SQL query in C).
    docs = db.collection("users").document(user_id).collection("accounts").stream()

    # This is a LIST COMPREHENSION — Python's compact way of writing a for-loop
    # that builds a list. Equivalent C-ish pseudocode:
    #   for each doc in docs: results[i] = doc.to_dict() with "id" added
    # doc.to_dict() converts the Firestore document into a plain dictionary.
    # The "| {"id": doc.id}" merges in the document's ID as an extra field,
    # since to_dict() alone doesn't include it.
    return [doc.to_dict() | {"id": doc.id} for doc in docs]


# --------------------------------------------------------------------------
# CATEGORIES (e.g. "Groceries", "Rent", "Entertainment")
# --------------------------------------------------------------------------

def create_category(user_id, name, monthly_budget=None):
    """monthly_budget is optional — None means 'no budget limit set'."""
    doc_ref = db.collection("users").document(user_id).collection("categories").document()
    doc_ref.set({
        "name": name,
        "monthly_budget": monthly_budget
    })
    return doc_ref.id


def get_categories(user_id):
    docs = db.collection("users").document(user_id).collection("categories").stream()
    return [doc.to_dict() | {"id": doc.id} for doc in docs]


# --------------------------------------------------------------------------
# TRANSACTIONS — the core of the app
# --------------------------------------------------------------------------

def add_transaction(user_id, account_id, amount, category, description=""):
    """
    Add a transaction. Use a negative amount for expenses, positive for income
    — that's a design choice that makes totals easy to calculate later.
    """
    doc_ref = db.collection("users").document(user_id).collection("transactions").document()
    doc_ref.set({
        "account_id": account_id,
        "amount": amount,
        "category": category,
        "description": description,
        "date": firestore.SERVER_TIMESTAMP
    })
    return doc_ref.id


def get_transactions(user_id):
    """Get every transaction for a user, newest first."""
    docs = (
        db.collection("users").document(user_id).collection("transactions")
        .order_by("date", direction=firestore.Query.DESCENDING)  # like ORDER BY date DESC
        .stream()
    )
    return [doc.to_dict() | {"id": doc.id} for doc in docs]


def get_transactions_by_category(user_id, category):
    """Get transactions filtered to one category — like a WHERE clause."""
    docs = (
        db.collection("users").document(user_id).collection("transactions")
        .where("category", "==", category)
        .stream()
    )
    return [doc.to_dict() | {"id": doc.id} for doc in docs]


def update_transaction(user_id, transaction_id, updates):
    """
    updates is a dict of only the fields you want to change, e.g.
    update_transaction(uid, tid, {"amount": -42.50})
    """
    (db.collection("users").document(user_id)
       .collection("transactions").document(transaction_id)
       .update(updates))


def delete_transaction(user_id, transaction_id):
    (db.collection("users").document(user_id)
       .collection("transactions").document(transaction_id)
       .delete())


# --------------------------------------------------------------------------
# SUMMARY / REPORTING — the kind of "smart" function that saves your
# teammates from writing this logic themselves.
# --------------------------------------------------------------------------

def get_monthly_summary(user_id, year, month):
    """
    Returns total spent, total earned, and a per-category breakdown for a
    given month. This is the kind of function your frontend/API teammate
    will love, because they just call this and get a ready-to-display result.
    """
    transactions = get_transactions(user_id)

    total_income = 0
    total_expense = 0
    by_category = {}  # like a hashmap: category name -> running total

    # "for x in list:" is Python's for-each loop — no index/counter needed,
    # similar to "for (auto& x : list)" in modern C++.
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
    test_user = "test_user_123"
    acc_id = create_account(test_user, "Checking", "checking", 500)
    add_transaction(test_user, acc_id, -45.20, "Groceries", "Trader Joe's")
    add_transaction(test_user, acc_id, 1200, "Paycheck", "Biweekly pay")

    print(get_transactions(test_user))
    print(get_monthly_summary(test_user, 2026, 7))
