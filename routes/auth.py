import os
import requests
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from database import shop_collection
from config import SHOPIFY_API_KEY, SHOPIFY_API_SECRET, BASE_PUBLIC_URL

router = APIRouter()

# --- SHOPIFY INSTALLATION FLOW ---

@router.get("/api/auth")
async def shopify_auth(shop: str = None):
    """Entry point for handling Shopify app installation."""
    target_shop = shop
    if not target_shop:
        return "Missing shop parameter."

    # Ensure the shop URL is properly formatted
    if not target_shop.endswith(".myshopify.com") and "." not in target_shop:
        target_shop = f"{target_shop}.myshopify.com"

    # Minimal scopes needed for WhatsApp Alerts
    scopes = "read_products,write_products"
    
    redirect_uri = f"{BASE_PUBLIC_URL}/api/auth/callback"
    install_url = (
        f"https://{target_shop}/admin/oauth/authorize?"
        f"client_id={SHOPIFY_API_KEY}&scope={scopes}&redirect_uri={redirect_uri}"
    )
    
    # Escape the Shopify Iframe for the OAuth process
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
    """Exchanges the authorization code for a permanent access token."""
    url = f"https://{shop}/admin/oauth/access_token"
    payload = {
        "client_id": SHOPIFY_API_KEY, 
        "client_secret": SHOPIFY_API_SECRET, 
        "code": code
    }
    
    try:
        resp = requests.post(url, json=payload)
        data = resp.json()
        
        if "access_token" in data:
            await shop_collection.update_one(
                {"shop": shop}, 
                {"$set": {
                    "access_token": data["access_token"], 
                    "updated_at": datetime.utcnow()
                }}, 
                upsert=True
            )
            print(f"✅ Access Token successfully updated for {shop}")
        else:
            print(f"❌ Shopify Token Exchange Error: {data}")
            
    except Exception as e: 
        print(f"❌ Shopify Auth Callback Exception: {e}")
    
    store_name = shop.split('.')[0]
    return RedirectResponse(f"https://admin.shopify.com/store/{store_name}/apps/{SHOPIFY_API_KEY}")