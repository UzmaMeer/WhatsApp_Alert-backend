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
    Sends a WhatsApp message using a pre-defined Meta/Facebook template.
    """
    print(f"📤 [DEBUG] Sending WhatsApp Template '{template_name}' to: {phone_number}...") 
    
    if not WA_PHONE_NUMBER_ID or not WA_ACCESS_TOKEN:
        print("⚠️ [ERROR] WhatsApp Credentials (ID/Token) are missing in config!")
        return False

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
    """Fetches products from the merchant's store."""
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
    """
    Registers a customer for restock alerts. 
    Prevents duplicate subscriptions for the same product.
    """
    print(f"\n📝 [DEBUG] Processing Subscribe Request for: {lead.product_title}") 
    
    # 1. Check if the customer is ALREADY subscribed and waiting for this product
    existing_lead = await leads_collection.find_one({
        "phone_number": lead.phone_number,
        "product_id": lead.product_id,
        "shop": lead.shop,
        "status": "pending"
    })

    if existing_lead:
        print("🔁 [REJECT] Customer is already in the waitlist. Skipping duplicate.")
        return {"status": "success", "message": "You are already on the waitlist for this item!"}

    store = await shop_collection.find_one({"shop": lead.shop})
    if not store: 
        return {"status": "error", "message": "Store not found."}
    
    # 2. Check stock level to ensure it's actually out of stock
    url = f"https://{lead.shop}/admin/api/{SHOPIFY_API_VERSION}/products/{lead.product_id}.json"
    headers = {"X-Shopify-Access-Token": store["access_token"]}
    r = requests.get(url, headers=headers)
    
    inventory = 0
    if r.status_code == 200:
        variants = r.json().get("product", {}).get("variants", [])
        inventory = sum(v.get("inventory_quantity", 0) for v in variants)
    
    if inventory > 0:
        return {"status": "error", "message": "This product is already in stock!"}
    
    # 3. Save new lead to Database
    new_lead = lead.dict()
    new_lead["created_at"] = datetime.utcnow()
    new_lead["status"] = "pending"
    await leads_collection.insert_one(new_lead)
    print("💾 [SAVED] New subscriber added to Database.") 
    
    # TRIGGER 1: Send 'Subscription Confirmation' message
    # Template: subscription_con
    send_whatsapp_message(lead.phone_number, template_name="subscription_con")
    
    return {"status": "success", "message": "You will be notified when it's back!"}

@router.post("/api/webhooks/product_update")
async def product_update_webhook(request: Request):
    """
    Automatically notifies customers when stock is replenished.
    """
    print("\n\n🔔 -------- WEBHOOK RECEIVED --------") 
    try:
        shop_domain = request.headers.get("X-Shopify-Shop-Domain")
        payload = await request.json()
        product_id = payload.get("id")
        
        variants = payload.get("variants", [])
        total_stock = sum(v.get("inventory_quantity", 0) for v in variants)
        
        if total_stock > 0:
            # Find all customers waiting for THIS product in THIS shop
            pending_leads = await leads_collection.find(
                {
                    "product_id": str(product_id), 
                    "status": "pending",
                    "shop": shop_domain
                }
            ).to_list(length=1000)
            
            if len(pending_leads) > 0:
                print(f"🎯 Notifying {len(pending_leads)} customers...")
                for lead in pending_leads:
                    # TRIGGER 2: Send 'Back in Stock' alert
                    # Template: item_back_in_stc
                    success = send_whatsapp_message(lead.get("phone_number"), template_name="item_back_in_stc")
                    
                    if success:
                        # Mark as notified to stop further messages
                        await leads_collection.update_one(
                            {"_id": lead["_id"]}, 
                            {"$set": {"status": "notified", "notified_at": datetime.utcnow()}}
                        )
            else:
                print("😴 No pending customers for this item.")
        
        return {"status": "success"}
    except Exception as e:
        print(f"❌ Webhook Error: {str(e)}") 
        return {"status": "error"}