import os
from dotenv import load_dotenv 
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv() 

# 1. Load Config from .env
MONGO_DETAILS = os.getenv("MONGO_DETAILS") 

# 🟢 NEW: Get the DB name from .env (defaults to 'whatsapp_alert_db' if missing)
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "whatsapp_alert_db")

client_db = AsyncIOMotorClient(MONGO_DETAILS)

# 🟢 UPDATED: Use the variable instead of a hardcoded string
database = client_db[MONGO_DB_NAME]

# --- COLLECTIONS ---

# Stores Shopify Tokens
shop_collection = database.get_collection("shopify_stores")

# Stores Customer Subscriptions (Name, Phone, Product ID)
leads_collection = database.get_collection("back_in_stock_leads")

# Stores Social Media Tokens
social_collection = database.get_collection("social_accounts")

# Stores Brand/App Settings
brand_collection = database.get_collection("brand_settings")