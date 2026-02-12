from fastapi import APIRouter, HTTPException, Request
import requests
import logging
from datetime import datetime
from database import shop_collection, leads_collection
from models import LeadRequest
from config import SHOPIFY_API_VERSION, WA_PHONE_NUMBER_ID, WA_ACCESS_TOKEN

# Basic Logging Configuration
logging.basicConfig(level=logging.INFO)
router = APIRouter()

# --- HELPER: Send WhatsApp Message ---
def send_whatsapp_message(phone_number, template_name):
    """
    Sends a WhatsApp message and prints the specific status for each number.
    """
    url = f"https://graph.facebook.com/v18.0/{WA_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    clean_phone = phone_number.replace("+", "").replace(" ", "").strip()

    payload = {
        "messaging_product": "whatsapp",
        "to": clean_phone,
        "type": "template",
        "template": { 
            "name": template_name,
            "language": { "code": "en" } 
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        # 📢 LOG: Shows the exact status for THIS specific phone number
        print(f"📩 [WHATSAPP API] Sent to: {clean_phone} | Status: {response.status_code} | Template: {template_name}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ [WHATSAPP ERROR] Failed for {clean_phone}: {str(e)}")
        return False

# --- ROUTES ---

@router.get("/api/products")
async def get_products(shop: str = None):
    """Fetches store products for the merchant dashboard."""
    if not shop: return {"products": []}
    store = await shop_collection.find_one({"shop": shop})
    if not store: return {"products": []}
    
    url = f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}/products.json"
    headers = {"X-Shopify-Access-Token": store["access_token"]}
    
    try:
        r = requests.get(url, headers=headers, params={"limit": 50})
        return {"products": r.json().get("products", [])}
    except Exception as e:
        return {"products": []}

@router.post("/api/subscribe")
async def subscribe_lead(lead: LeadRequest):
    """Registers new lead and prevents duplicates."""
    p_id = str(lead.product_id)
    
    existing_lead = await leads_collection.find_one({
        "phone_number": lead.phone_number,
        "product_id": p_id,
        "shop": lead.shop,
        "status": "pending"
    })

    if existing_lead:
        # Verified working in logs:
        print(f"🔁 [REJECT] {lead.phone_number} is already on waitlist for {p_id}")
        return {"status": "already_subscribed", "message": "You are already on the waitlist!"}

    store = await shop_collection.find_one({"shop": lead.shop})
    if not store: return {"status": "error", "message": "Store not found."}
    
    new_lead = lead.dict()
    new_lead.update({"product_id": p_id, "status": "pending", "created_at": datetime.utcnow()})
    await leads_collection.insert_one(new_lead)
    
    # Message 1: Confirmation
    send_whatsapp_message(lead.phone_number, template_name="subscription_confirmed")
    
    return {"status": "success", "message": "Subscription successful!"}

@router.post("/api/webhooks/product_update")
async def product_update_webhook(request: Request):
    """
    Notifies all pending customers from the list saved in DB.
    """
    print("\n🔔 -------- WEBHOOK RECEIVED FROM SHOPIFY --------") 
    try:
        shop_domain = request.headers.get("X-Shopify-Shop-Domain")
        payload = await request.json()
        product_id = str(payload.get("id"))
        
        variants = payload.get("variants", [])
        total_stock = sum(v.get("inventory_quantity", 0) for v in variants)
        
        print(f"🏪 Shop: {shop_domain} | 📦 Product ID: {product_id} | 📈 New Stock: {total_stock}")

        if total_stock > 0:
            # 1. Get the list of ALL customers waiting for this product
            pending_leads = await leads_collection.find({
                "product_id": product_id, "status": "pending", "shop": shop_domain
            }).to_list(length=1000)
            
            # 📢 LOG: Shows how many people were found in DB
            print(f"🎯 Found {len(pending_leads)} customers in DB waiting for this product.")

            # 2. Loop through the list and notify each one
            for lead in pending_leads:
                customer_phone = lead.get("phone_number")
                
                # TRIGGER: Restock Alert
                success = send_whatsapp_message(customer_phone, template_name="item_back_in_stock")
                
                if success:
                    # 📢 LOG: Confirming success for this specific number
                    print(f"✅ DB Update: Customer {customer_phone} successfully notified.")
                    await leads_collection.update_one(
                        {"_id": lead["_id"]}, 
                        {"$set": {"status": "notified", "notified_at": datetime.utcnow()}}
                    )
                else:
                    # 📢 LOG: Alerting if Meta API failed for this specific number
                    print(f"⚠️ Meta API Failure: Message could not reach {customer_phone}")
        else:
            print("📉 Stock update received, but total quantity is still 0.")
        
        print("🔔 -------- WEBHOOK PROCESSED SUCCESSFULLY --------\n")
        return {"status": "success"}
    except Exception as e:
        print(f"❌ Webhook Error: {str(e)}") 
        return {"status": "error"}