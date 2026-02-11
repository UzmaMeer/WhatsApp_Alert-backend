import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

# Import project configurations and routes
from config import BASE_PUBLIC_URL
from routes import auth, general
from database import shop_collection

app = FastAPI(title="WhatsApp Alert Backend")

# --- 1. Middleware Configuration ---
# We include both Railway and Ngrok in the origins to support the fallback logic
app.add_middleware(
    CORSMiddleware, 
    allow_origins=[
        "https://shopify-alert.web.app",        # Live Firebase Frontend
        "https://admin.shopify.com",             # Shopify Admin Panel
        "http://localhost:3000",                # Local testing
        "https://whatsappalert-backend-production.up.railway.app",
        "https://snakiest-edward-autochthonously.ngrok-free.dev" # Your Ngrok Tunnel
    ], 
    allow_methods=["*"], 
    allow_headers=["*"], 
    allow_credentials=True
)

# Secure session management for Shopify authentication
app.add_middleware(
    SessionMiddleware, 
    secret_key="UZMA_SECURE_KEY_2026", 
    https_only=True
)

# --- 2. Route Registration ---
app.include_router(auth.router)    # Shopify installation & OAuth
app.include_router(general.router) # Product fetching & WhatsApp leads

# --- 3. Health Check Endpoint ---
# Your Frontend (React) will ping this to see if Railway is alive
@app.get("/status")
async def health_check():
    return {
        "status": "ok", 
        "message": "Railway Backend is Active",
        "version": "1.0.0"
    }

# --- 4. Main Entry Point (Shopify Dashboard) ---
@app.get("/")
async def home(request: Request, shop: str = None):
    """
    When a merchant opens the app in Shopify, this route decides 
    if they need to install the app or go straight to the dashboard.
    """
    if shop:
        # Check if we already have an access token for this store
        existing_shop = await shop_collection.find_one({"shop": shop})
        if existing_shop and existing_shop.get("access_token"):
            print(f"✅ Shop {shop} verified. Redirecting to Dashboard.")
            # Redirect to your live Firebase frontend
            return RedirectResponse(f"https://shopify-alert.web.app?shop={shop}")

    # If the shop is not found or no shop param is provided, start installation
    print(f"🔄 Shop {shop} not found or new install. Starting OAuth.")
    return RedirectResponse(url=f"/api/auth?shop={shop}" if shop else "/api/auth")

# --- 5. Exception Handling ---
@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": str(exc)},
    )