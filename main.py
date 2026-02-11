import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

# Import project configurations, database, and internal routes
from config import BASE_PUBLIC_URL
from routes import auth, general
from database import shop_collection

app = FastAPI(title="WhatsApp Alert Backend Service")

# --- 1. Middleware Configuration ---
# Configures which frontends are allowed to communicate with this backend
app.add_middleware(
    CORSMiddleware, 
    allow_origins=[
        "https://whats-app-alert-frontend.vercel.app",  # Production Vercel Frontend
        "https://shopify-alert.web.app",                # Legacy Firebase Frontend
        "https://admin.shopify.com",                    # Shopify Admin UI
        "http://localhost:3000",                        # Local Development
        "*"                                             # Wildcard allowed for testing
    ], 
    allow_methods=["*"], 
    allow_headers=["*"], 
    allow_credentials=True
)

# Secure session management for the Shopify OAuth flow
app.add_middleware(
    SessionMiddleware, 
    secret_key="UZMA_SECURE_KEY_2026", 
    https_only=True # Ensures cookies are only sent over HTTPS
)

# --- 2. Route Registration ---
app.include_router(auth.router)    # Handles App Install & Shopify OAuth
app.include_router(general.router) # Handles Product fetching & WhatsApp Leads

# --- 3. Health Check Endpoint ---
@app.get("/status")
async def health_check():
    """Simple endpoint to verify if the Railway backend is online."""
    return {
        "status": "ok", 
        "message": "Railway Backend Service is Active",
        "version": "1.0.1"
    }

# --- 4. Main App Entry Point (Shopify Dashboard) ---
@app.get("/")
async def home(request: Request, shop: str = None):
    """
    Entry point when a merchant opens the app in Shopify.
    Redirects to either the App Installation (OAuth) or the Live Dashboard.
    """
    if shop:
        # Check if the shop has already installed the app (exists in DB)
        existing_shop = await shop_collection.find_one({"shop": shop})
        if existing_shop and existing_shop.get("access_token"):
            print(f"✅ Shop {shop} verified. Redirecting to Live Vercel Dashboard.")
            # Redirect to the Vercel-hosted React frontend
            return RedirectResponse(f"https://whats-app-alert-frontend.vercel.app?shop={shop}")

    # If the shop is new or parameters are missing, start the OAuth installation flow
    print(f"🔄 Shop {shop} not found. Starting Shopify OAuth Installation.")
    auth_url = f"/api/auth?shop={shop}" if shop else "/api/auth"
    return RedirectResponse(url=auth_url)

# --- 5. Global Exception Handling ---
@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    """Captures and returns detailed error logs for 500-level failures."""
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": str(exc)},
    )