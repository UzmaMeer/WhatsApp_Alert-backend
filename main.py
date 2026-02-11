import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from config import BASE_PUBLIC_URL
from routes import auth, general
from database import shop_collection

app = FastAPI()

# --- Middleware ---
app.add_middleware(
    CORSMiddleware, 
    allow_origins=[
        "https://shopify-alert.web.app", # Your live frontend
        "https://admin.shopify.com"
    ], 
    allow_methods=["*"], 
    allow_headers=["*"], 
    allow_credentials=True
)

app.add_middleware(
    SessionMiddleware, 
    secret_key="UZMA_SECURE_KEY_2026", 
    https_only=True
)

app.include_router(auth.router)
app.include_router(general.router)

@app.get("/")
async def home(request: Request, shop: str = None):
    # Check if shop is already installed in your MongoDB
    if shop:
        existing_shop = await shop_collection.find_one({"shop": shop})
        if existing_shop and existing_shop.get("access_token"):
            # Success: Go to your LIVE frontend deployment
            return RedirectResponse(f"https://shopify-alert.web.app?shop={shop}")

    # Not installed? Go to OAuth installation
    return RedirectResponse(url=f"/api/auth?shop={shop}" if shop else "/api/auth")