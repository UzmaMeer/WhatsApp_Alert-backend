from fastapi import APIRouter, HTTPException, Request
import requests
import logging
from datetime import datetime
from database import shop_collection, leads_collection
from models import LeadRequest
from config import SHOPIFY_API_VERSION, WA_PHONE_NUMBER_ID, WA_ACCESS_TOKEN, BASE_PUBLIC_URL

# Basic Logging Configuration
logging.basicConfig(level=logging.INFO)
router = APIRouter()

# --- 🟢 HELPER: Auto-Register Webhook ---
def register_shopify_webhook(shop, access_token):
    """
    Communicates with Shopify to subscribe to 'products/update' events.
    Whenever a product's stock changes, Shopify will ping our Railway server.
    """
    webhook_url = f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}/webhooks.json"
    
    # Our Railway destination URL for the webhook
    target_address = f"{BASE_PUBLIC_URL}/api/webhooks/product_update"
    
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "webhook": {
            "topic": "products/update",
            "address": target_address,
            "format": "json"
        }
    }
    
    try:
        response = requests.post(webhook_url, json=payload, headers=headers)
        if response.status_code == 201:
            print(f"✅ [AUTO-WEBHOOK] Successfully registered for {shop}")
        elif response.status_code == 422:
            print(f"ℹ️ [AUTO-WEBHOOK] Webhook already exists for {shop}")
    except Exception as e:
        print(f"❌ [AUTO-WEBHOOK] Registration Error: {e}")

# --- HELPER: Send WhatsApp Message ---
def send_whatsapp_message(phone_number, template_name):
    """
    Sends a pre-approved Meta WhatsApp template to a customer's phone number.
   
    """
    print(f"📤 [DEBUG] Sending WhatsApp Template '{template_name}' to: {phone_number}...") 
    
    if not WA_PHONE_NUMBER_ID or not WA_ACCESS_TOKEN:
        print("⚠️ [ERROR] WhatsApp Keys are missing from environment!")
        return False

    url = f"https://graph.facebook.com/v18.0/{WA_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Ensure the phone number is in the correct format for Meta
    clean_phone = phone_number.replace("+", "").replace(" ", "").strip()

    payload = {
        "messaging_product": "whatsapp",
        "to": clean_phone,
        "type": "template",
        "template": { 
            "name": template_name,
            # FIXED: Language code 'en' matches your 'Active - English' templates
            "language": { "code": "en" } 
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            print(f"✅ [SUCCESS] WhatsApp sent successfully to {clean_phone}!") 
            return True
        else:
            print(f"❌ [FAILED] WhatsApp API Error: {response.text}") 
            return False
    except Exception as e:
        print(f"❌ [EXCEPTION] WhatsApp Connection Error: {str(e)}")
        return False

# --- ROUTES ---

@router.get("/api/products")
async def get_products(shop: str = None):
    """Fetches store products to display in the App dashboard."""
    if not shop: return {"products": []}
    store = await shop_collection.find_one({"shop": shop})
    if not store: return {"products": []}
    
    url = f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}/products.json"
    headers = {"X-Shopify-Access-Token": store["access_token"]}
    
    try:
        r = requests.get(url, headers=headers, params={"limit": 50})
        return {"products": r.json().get("products", [])}
    except:
        return {"products": []}

@router.post("/api/subscribe")
async def subscribe_lead(lead: LeadRequest):
    """
    ACTION 1: Triggered when a customer enters their phone number on a product page.
    Sends the immediate 'Subscription Confirmation' message.
    """
    print(f"\n📝 [DEBUG] New Subscribe Request for: {lead.product_title} on {lead.shop}") 
    
    store = await shop_collection.find_one({"shop": lead.shop})
    if not store: return {"status": "error"}
    
    # Save the customer phone number and product interest to MongoDB
    new_lead = lead.dict()
    new_lead["created_at"] = datetime.utcnow()
    new_lead["status"] = "pending"
    await leads_collection.insert_one(new_lead)
    
    # 🟢 MSG 1: Immediate confirmation message
    # Template name fixed to match your Meta dashboard
    send_whatsapp_message(lead.phone_number, template_name="subscription_con")
    
    return {"status": "success", "message": "You will be notified!"}

@router.post("/api/webhooks/product_update")
async def product_update_webhook(request: Request):
    """
    ACTION 2: Triggered automatically by Shopify when a product is restocked.
    Sends alerts to all customers who were waiting for this specific item.
    """
    print("\n\n🔔 -------- WEBHOOK RECEIVED (Automation) --------") 
    try:
        shop_domain = request.headers.get("X-Shopify-Shop-Domain")
        if not shop_domain:
            return {"status": "error"}

        payload = await request.json()
        product_id = payload.get("id")
        
        # Calculate new inventory quantity across all product variants
        variants = payload.get("variants", [])
        total_stock = sum(v.get("inventory_quantity", 0) for v in variants)
        
        print(f"🏪 Shop: {shop_domain} | 📦 Product: {product_id} | 📈 Stock: {total_stock}") 
        
        # If stock is now available (> 0), notify customers
        if total_stock > 0:
            pending_leads = await leads_collection.find(
                {
                    "product_id": str(product_id), 
                    "status": "pending",
                    "shop": shop_domain
                }
            ).to_list(length=100)
            
            if len(pending_leads) > 0:
                for lead in pending_leads:
                    # 🟢 MSG 2: Restock Alert Message
                    # Template name fixed to match your Meta dashboard
                    success = send_whatsapp_message(lead.get("phone_number"), template_name="item_back_in_stc")
                    
                    if success:
                        # Update status to 'notified' to prevent duplicate messages
                        await leads_collection.update_one(
                            {"_id": lead["_id"]}, 
                            {"$set": {"status": "notified", "notified_at": datetime.utcnow()}}
                        )
            else:
                print("😴 No pending customers for this item.")
        else:
            print("📉 Inventory update received, but item is still out of stock.")
            
        return {"status": "success"}
    except Exception as e:
        print(f"❌ Webhook Processing Error: {str(e)}") 
        return {"status": "error"}