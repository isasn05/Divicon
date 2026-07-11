#run "pip install -r requirements.txt" for dp.py and api.py to work

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

SERVICE_ACCOUNT_PATH = "service-account-key.json"
cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

#ACCOUNTS



#CATEGORIES



#TRANSACTIONS




#SUMMARY