import os
import requests
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, HTMLResponse
from config import BASE_PUBLIC_URL, SHOPIFY_API_KEY, SHOPIFY_API_SECRET, SHOPIFY_API_VERSION
from database import shop_collection
from datetime import datetime

# 🟢 Define the Router
router = APIRouter()

# --- HELPER: Register Webhook ---
def register_webhook(shop, access_token):
    print(f"🔗 Attempting to register webhook for {shop}...")
    
    # 🟢 UPDATED ENDPOINT: Matches the route in general.py
    webhook_endpoint = f"{BASE_PUBLIC_URL}/api/webhooks/product_update"
    
    url = f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}/webhooks.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "webhook": {
            # 🟢 UPDATED TOPIC: 'products/update' gives us the Product ID (Fixed the "None" issue)
            "topic": "products/update", 
            "address": webhook_endpoint,
            "format": "json"
        }
    }
    
    try:
        # First, check if it already exists to avoid errors
        get_resp = requests.get(url, headers=headers)
        existing_webhooks = get_resp.json().get("webhooks", [])
        
        for wh in existing_webhooks:
            if wh["address"] == webhook_endpoint:
                print(f"⚠️ Webhook already exists for {shop}. Skipping registration.")
                return

        # If not, create it
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 201:
            print(f"✅ Webhook (products/update) Registered SUCCESSFULLY for {shop}")
        else:
            print(f"❌ Webhook Registration Failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Webhook Exception: {str(e)}")

# --- ROUTES ---

@router.get("/api/auth")
async def shopify_auth(shop: str = None):
    """
    Step 1: Redirect user to Shopify to approve the app.
    """
    # 1. Handle Shop Name
    target_shop = shop or "uzma-video-ads-store.myshopify.com"
    if not target_shop.endswith(".myshopify.com") and "." not in target_shop:
        target_shop = f"{target_shop}.myshopify.com"

    # 2. Prepare OAuth URL
    scopes = "read_products,write_products,write_script_tags"
    redirect_uri = f"{BASE_PUBLIC_URL}/api/auth/callback"
    
    install_url = (
        f"https://{target_shop}/admin/oauth/authorize?"
        f"client_id={SHOPIFY_API_KEY}&scope={scopes}&redirect_uri={redirect_uri}"
    )
    
    print(f"🚀 Redirecting to Shopify OAuth: {install_url}")
    
    # 3. Escape Iframe (Important for embedded apps)
    return HTMLResponse(f"<script>window.top.location.href='{install_url}'</script>")

@router.get("/api/auth/callback")
async def shopify_callback(shop: str, code: str):
    """
    Step 2: Handle the callback from Shopify, get token, and register webhook.
    """
    url = f"https://{shop}/admin/oauth/access_token"
    payload = {
        "client_id": SHOPIFY_API_KEY, 
        "client_secret": SHOPIFY_API_SECRET, 
        "code": code
    }
    
    try:
        # 1. Exchange Code for Token
        resp = requests.post(url, json=payload)
        data = resp.json()
        
        if "access_token" in data:
            access_token = data["access_token"]
            
            # 2. Save to Database
            await shop_collection.update_one(
                {"shop": shop}, 
                {"$set": {
                    "access_token": access_token, 
                    "updated_at": datetime.utcnow()
                }}, 
                upsert=True
            )
            print(f"💾 Token Saved for {shop}")

            # 3. 🟢 REGISTER WEBHOOK IMMEDIATELY
            register_webhook(shop, access_token)
            
            # 4. Redirect to App Home
            store_name = shop.split('.')[0]
            return RedirectResponse(f"https://admin.shopify.com/store/{store_name}/apps/{SHOPIFY_API_KEY}")
        
        else:
            return {"error": "Failed to get access token", "details": data}
            
    except Exception as e:
        return {"error": str(e)}