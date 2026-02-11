import os
import requests
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse

# Internal imports for database and configuration
from database import shop_collection
from config import SHOPIFY_API_KEY, SHOPIFY_API_SECRET, BASE_PUBLIC_URL, SHOPIFY_API_VERSION

# 🟢 FIXED: Removed the invalid 'register_shopify_webhook' import that was causing the crash.
# Since the function doesn't exist in routes/general, we will handle automation later.

router = APIRouter()

# --- SHOPIFY INSTALLATION FLOW ---

@router.get("/api/auth")
async def shopify_auth(shop: str = None):
    """
    Entry point for handling Shopify app installation.
    Triggered when a merchant clicks 'Install' in the Shopify App Store.
    """
    target_shop = shop
    if not target_shop:
        return "Missing shop parameter."

    # Standardize the shop URL format (ensure it ends with .myshopify.com)
    if not target_shop.endswith(".myshopify.com") and "." not in target_shop:
        target_shop = f"{target_shop}.myshopify.com"

    # Define the permissions (scopes) our app needs
    # 'read_inventory' allows us to track stock levels automatically
    scopes = "read_products,write_products,read_inventory"
    
    redirect_uri = f"{BASE_PUBLIC_URL}/api/auth/callback"
    install_url = (
        f"https://{target_shop}/admin/oauth/authorize?"
        f"client_id={SHOPIFY_API_KEY}&scope={scopes}&redirect_uri={redirect_uri}"
    )
    
    # Escape the Shopify Iframe to ensure the merchant sees the 'Grant Permissions' page correctly
    content = f"""
    <html>
        <head>
            <script type="text/javascript">
                window.top.location.href = "{install_url}";
            </script>
        </head>
        <body>
            <h2 style="text-align:center; padding-top:100px;">Redirecting to Shopify...</h2>
        </body>
    </html>
    """
    return HTMLResponse(content=content)

@router.get("/api/auth/callback")
async def shopify_callback(shop: str, code: str):
    """
    Handles the final step of OAuth: exchanging the temporary code for a 
    permanent access token and saving the store data.
    """
    url = f"https://{shop}/admin/oauth/access_token"
    payload = {
        "client_id": SHOPIFY_API_KEY, 
        "client_secret": SHOPIFY_API_SECRET, 
        "code": code
    }
    
    try:
        # Request the permanent access token from Shopify servers
        resp = requests.post(url, json=payload)
        data = resp.json()
        
        if "access_token" in data:
            access_token = data["access_token"]
            
            # 1. Save or update the shop token in MongoDB for future API calls
            await shop_collection.update_one(
                {"shop": shop}, 
                {"$set": {
                    "access_token": access_token, 
                    "updated_at": datetime.utcnow()
                }}, 
                upsert=True
            )
            print(f"✅ Access Token successfully updated in Database for {shop}")

            # 🛠️ TODO: Implement automatic Webhook registration here in the future
            # For now, we manually register webhooks to ensure stability.
            
        else:
            print(f"❌ Shopify Token Exchange Error: {data}")
            
    except Exception as e: 
        print(f"❌ Shopify Auth Callback Exception: {str(e)}")
    
    # Redirect the merchant back to their Shopify Admin App Dashboard
    store_name = shop.split('.')[0]
    # NOTE: Ensure SHOPIFY_API_KEY matches the Handle/Client ID in your Partner Dashboard
    return RedirectResponse(f"https://admin.shopify.com/store/{store_name}/apps/{SHOPIFY_API_KEY}")