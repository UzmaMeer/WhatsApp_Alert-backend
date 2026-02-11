import os
from dotenv import load_dotenv

# Load local .env for local testing (Railway uses its own Variables tab)
load_dotenv()

# --- Base Directories ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Public URL Configuration ---
# 🟢 Your permanent Railway address
BASE_PUBLIC_URL = "https://whatsappalert-backend-production.up.railway.app"

# --- Shopify Configuration ---
# API Version used for products and webhooks
SHOPIFY_API_VERSION = "2024-01" 
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")

# --- Database Configuration ---
# MongoDB Cluster0 connection details
MONGO_DETAILS = os.getenv("MONGO_DETAILS")

# --- WhatsApp Configuration ---
# Credentials for Meta Graph API to send alerts
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID") 
WA_ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN")