import os
import requests
from datetime import datetime
from urllib.parse import urlencode
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from authlib.integrations.starlette_client import OAuth
from database import shop_collection, social_collection
from config import *

router = APIRouter()
oauth = OAuth()

# --- SOCIAL OAUTH REGISTRATION ---
# Registration for Instagram, Facebook, and TikTok remains identical to your existing settings
oauth.register(
    name='instagram', client_id=META_CLIENT_ID, client_secret=META_CLIENT_SECRET,
    access_token_url='https://graph.facebook.com/v21.0/oauth/access_token',
    authorize_url='https://www.facebook.com/v21.0/dialog/oauth',
    api_base_url='https://graph.facebook.com/', 
    client_kwargs={'scope': 'public_profile,pages_show_list,pages_read_engagement,pages_manage_posts,instagram_basic,instagram_content_publish,business_management'},
)
oauth.register(
    name='facebook',
    client_id=META_CLIENT_ID,
    client_secret=META_CLIENT_SECRET,
    access_token_url='https://graph.facebook.com/v21.0/oauth/access_token',
    authorize_url='https://www.facebook.com/v21.0/dialog/oauth',
    api_base_url='https://graph.facebook.com/',
    client_kwargs={'scope': 'public_profile,pages_show_list,pages_read_engagement,pages_manage_posts,business_management'},
)
oauth.register(
    name='tiktok', client_id=TIKTOK_CLIENT_KEY, client_secret=TIKTOK_CLIENT_SECRET,
    access_token_url='https://open.tiktokapis.com/v2/oauth/token/',
    authorize_url='https://www.tiktok.com/v2/auth/authorize/',
    api_base_url='https://open.tiktokapis.com/v2/',
    client_kwargs={'scope': 'user.info.basic,video.upload'}, 
    authorize_params={'client_key': TIKTOK_CLIENT_KEY} 
)

# --- SHOPIFY INSTALLATION FLOW ---

@router.get("/api/auth")
async def shopify_auth(shop: str = None):
    """
    Entry point for the Shopify App. Handles initial installs and re-installs.
    Escapes the Shopify Iframe to prevent 'Refused to Connect' errors.
    """
    # Fallback to your dev store if the shop parameter is missing
    target_shop = shop or "uzma-video-ads-store.myshopify.com" 
    
    # Ensure the shop URL is properly formatted
    if not target_shop.endswith(".myshopify.com") and "." not in target_shop:
        target_shop = f"{target_shop}.myshopify.com"

    # Scopes required for the app's professional features
    scopes = "read_products,write_products,write_script_tags,write_files,write_content"
    
    redirect_uri = f"{BASE_PUBLIC_URL}/api/auth/callback"
    install_url = (
        f"https://{target_shop}/admin/oauth/authorize?"
        f"client_id={SHOPIFY_API_KEY}&scope={scopes}&redirect_uri={redirect_uri}"
    )
    
    print(f"🔗 Escaping Iframe and Redirecting to Shopify OAuth: {install_url}")
    
    # PROFESSIONAL FIX: Escape the iframe using top-level redirection.
    # We include a fallback button in case the browser blocks the script.
    content = f"""
    <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica; text-align: center; padding-top: 100px; color: #202223; }}
                .btn {{ background-color: #008060; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: 600; display: inline-block; margin-top: 20px; }}
                .btn:hover {{ background-color: #006e52; }}
            </style>
            <script type="text/javascript">
                // This line escapes the Shopify Iframe to allow the OAuth page to load
                window.top.location.href = "{install_url}";
            </script>
        </head>
        <body>
            <h2>Authenticating with Shopify</h2>
            <p>If you are not redirected automatically within a few seconds, please click the button below:</p>
            <a href="{install_url}" target="_top" class="btn">Complete Installation</a>
        </body>
    </html>
    """
    return HTMLResponse(content=content)

@router.get("/api/auth/callback")
async def shopify_callback(shop: str, code: str):
    """
    Exchanges the authorization code for a permanent access token.
    Updates the token in the database for re-installations.
    """
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
            # Upsert ensures re-installations overwrite old tokens correctly
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
    
    # Redirect back to the modern Shopify Admin App dashboard
    store_name = shop.split('.')[0]
    return RedirectResponse(f"https://admin.shopify.com/store/{store_name}/apps/{SHOPIFY_API_KEY}")

# --- SOCIAL MEDIA LOGIN ROUTES ---

@router.get("/login/{platform}")
async def social_login(platform: str, request: Request):
    """
    Starts the OAuth flow for social media accounts (Instagram, Facebook, or TikTok).
    """
    redirect_uri = f"{BASE_PUBLIC_URL}/auth/callback/{platform}"
    client = oauth.create_client(platform)
    request.scope["scheme"] = "https" # Ensures compatibility with Ngrok/Proxy
    
    if platform.lower() == "tiktok":
        base_url = "https://www.tiktok.com/v2/auth/authorize/"
        params = {
            "client_key": TIKTOK_CLIENT_KEY, 
            "response_type": "code", 
            "scope": "user.info.basic,video.upload", 
            "redirect_uri": redirect_uri, 
            "state": "somerandomstring"
        }
        return RedirectResponse(f"{base_url}?{urlencode(params)}")
    
    return await client.authorize_redirect(request, redirect_uri)

@router.get("/auth/callback/{platform}")
async def auth_callback(platform: str, request: Request):
    """
    Captures social media tokens and saves them to the database.
    """
    request.scope["scheme"] = "https"
    try:
        client = oauth.create_client(platform)
        token = await client.authorize_access_token(request)
        
        # Determine unique platform user ID for storage
        user_id = "tiktok_user" if platform == "tiktok" else (await client.get('me', token=token)).json().get('id')
        
        # Update social account tokens in MongoDB
        await social_collection.update_one(
            {"platform": platform, "platform_user_id": user_id}, 
            {"$set": {"token_data": token}}, 
            upsert=True
        )
        # Close the popup window automatically after connection
        return HTMLResponse("<script>window.close();</script><h1>Connected Successfully!</h1>")
    except Exception as e: 
        return HTMLResponse(f"<h1>OAuth Callback Error: {str(e)}</h1>")