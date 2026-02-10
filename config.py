import os
from dotenv import load_dotenv

load_dotenv()

# --- Base Directories ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = os.path.join(BASE_DIR, "video")
os.makedirs(VIDEO_DIR, exist_ok=True)

# --- Public URL Configuration ---
BASE_PUBLIC_URL = os.getenv("BASE_PUBLIC_URL", "https://snakiest-edward-autochthonously.ngrok-free.dev")

# --- Shopify Configuration ---
SHOPIFY_API_VERSION = "2024-01" 
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")

# --- Meta / Instagram Configuration ---
META_CLIENT_ID = os.getenv("META_CLIENT_ID")
META_CLIENT_SECRET = os.getenv("META_CLIENT_SECRET")
IG_USER_ID = os.getenv("IG_USER_ID")

# --- TikTok Configuration ---
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")

# --- AI Configuration ---
gemini_api_key = os.getenv("GEMINI_API_KEY")

# 🟢 NEW: WhatsApp Configuration (You were missing this!)
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID") 
WA_ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN")