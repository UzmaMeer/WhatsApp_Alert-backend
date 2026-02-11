import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

# Import project-specific configurations and routes
from config import BASE_PUBLIC_URL
from routes import auth, general
from database import shop_collection

app = FastAPI()

# --- Middleware Configuration ---
# CORS is required so your deployed frontend can communicate with your Ngrok backend
app.add_middleware(
    CORSMiddleware, 
    allow_origins=[
        "http://localhost:3000",
        "https://shopify-alert.web.app",  # Your live frontend URL
        "https://admin.shopify.com"
    ], 
    allow_methods=["*"], 
    allow_headers=["*"], 
    allow_credentials=True
)

# Session management for Shopify authentication flow
app.add_middleware(
    SessionMiddleware, 
    secret_key="UZMA_WHATSAPP_PROJECT_SECURE_999", 
    https_only=True
)

# --- Route Registration ---
# Include authentication logic and general API endpoints
app.include_router(auth.router)
app.include_router(general.router)

# --- Root Endpoint ---
@app.get("/")
async def home(request: Request, shop: str = None):
    """
    Main entry point. It checks if the store is installed.
    If yes, it redirects to the live React interface.
    If no, it starts the Shopify OAuth installation.
    """
    
    # Optional: Use '?force_auth=true' in URL to re-trigger the login process
    force_auth = request.query_params.get("force_auth") == "true"

    if shop and not force_auth:
        # Check if the shop exists in your MongoDB database
        existing_shop = await shop_collection.find_one({"shop": shop})
        
        if existing_shop and existing_shop.get("access_token"):
            # SUCCESS: Redirect directly to your live deployed frontend
            # No need for local 'build' folder copying anymore
            return RedirectResponse(f"https://shopify-alert.web.app?shop={shop}")

    # INSTALLATION: Redirect to the OAuth route if store is not found
    return RedirectResponse(url=f"/api/auth?shop={shop}" if shop else "/api/auth")

# --- Server Status ---
@app.get("/status")
async def status():
    return {"status": "Backend is active and linked to shopify-alert.web.app"}