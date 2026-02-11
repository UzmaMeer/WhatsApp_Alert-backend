import os
from dotenv import load_dotenv

# Load local .env for local testing
load_dotenv()

# --- Base Directories ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Note: VIDEO_DIR is no longer needed but kept as a placeholder if you store logs

# --- Public URL Configuration ---
# 🟢 This MUST be your Railway URL so Shopify can send webhooks
BASE_PUBLIC_URL = os.getenv("BASE_PUBLIC_URL", "https://whatsappalert-backend-production.up.railway.app")

# --- Shopify Configuration ---
# Used for authentication and fetching product data
SHOPIFY_API_VERSION = "2024-01" 
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")

# --- Database Configuration ---
# Connection string for your MongoDB Cluster0
MONGO_DETAILS = os.getenv("MONGO_DETAILS")

# --- WhatsApp Configuration ---
# These are required to send the actual restock alerts
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID") 
WA_ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN")