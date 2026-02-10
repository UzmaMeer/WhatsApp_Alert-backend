import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the MongoDB connection string from .env
# If not found, it defaults to a local connection for safety
MONGO_DETAILS = os.getenv("MONGO_DETAILS", "mongodb://localhost:27017")

# Create the async database client
client = AsyncIOMotorClient(MONGO_DETAILS)

# 🟢 UPDATE: Database name changed to 'whatsapp_alert'
database = client.whatsapp_alert

# --- Collections Definitions ---
video_jobs_collection = database.get_collection("video_jobs")
social_collection = database.get_collection("social_accounts")
shop_collection = database.get_collection("shopify_stores")
brand_collection = database.get_collection("brand_settings")
publish_collection = database.get_collection("publish_jobs")
review_collection = database.get_collection("user_reviews")

# Collection for WhatsApp leads
leads_collection = database.get_collection("leads")

# --- Helper Functions ---

async def check_db_connection():
    """
    Checks if the database connection is active.
    Returns True if connected, False otherwise.
    """
    try:
        # The 'ping' command is lightweight and confirms the server is reachable
        await client.admin.command('ping')
        print(f"✅ Successfully connected to MongoDB at: {MONGO_DETAILS}")
        return True
    except Exception as e:
        print(f"❌ Could not connect to MongoDB: {e}")
        return False