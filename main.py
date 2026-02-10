from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
import logging

# --- Import Config and Routes ---
from config import BASE_PUBLIC_URL
# 🟢 CRITICAL: We import both auth and general routes here
# Make sure you have a 'routes' folder with auth.py and general.py
from routes import auth, general   
from database import shop_collection

# --- 🟢 SYSTEM START PRINT ---
print("\n\n🛑 SYSTEM RESTARTING: Loading Routes...\n")

app = FastAPI()

# --- Middleware Setup ---
origins = ["*"]  # Allow all for testing (Frontend se connect karne ke liye zaroori)
app.add_middleware(
    CORSMiddleware, 
    allow_origins=origins, 
    allow_methods=["*"], 
    allow_headers=["*"], 
    allow_credentials=True
)

# Session aur HTTPS Proxy Headers (Render ke liye zaroori)
app.add_middleware(SessionMiddleware, secret_key="SECRET_KEY", https_only=True)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# --- 🟢 REGISTER ROUTERS (Connecting the files) ---
# This is what fixes the 404 Error
app.include_router(auth.router)
app.include_router(general.router)

# --- 🟢 DEBUG: Print Routes on Startup ---
@app.on_event("startup")
async def show_routes():
    print("\n🗺️  AVAILABLE ROUTES (Verify these exist):")
    for route in app.routes:
        if hasattr(route, "path"):
             # Print full URL for easy clicking
            print(f"   👉 {BASE_PUBLIC_URL}{route.path}")
    print("\n✅ System Ready! Waiting for requests...\n")

# --- Root Endpoint ---
@app.get("/")
async def home(request: Request, shop: str = None): 
    """
    Entry point for the Shopify App.
    """
    if shop:
        # Simple confirmation page for embedded app
        return HTMLResponse(f"""
            <html>
                <head><title>Uzma's App</title></head>
                <body style="font-family: sans-serif; padding: 50px; text-align: center;">
                    <h1>✅ App is Running for {shop}</h1>
                    <p>Webhooks are active. You can close this tab.</p>
                </body>
            </html>
        """)
    # If no shop param, redirect to auth to be safe
    return RedirectResponse(url="/api/auth")