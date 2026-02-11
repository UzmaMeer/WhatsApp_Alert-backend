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
    print(f"📤 [DEBUG] Sending WhatsApp Template '{template_name}' to: {phone_number}...") 
    
    if not WA_PHONE_NUMBER_ID or not WA_ACCESS_TOKEN:
        print("⚠️ [ERROR] WhatsApp Keys are missing!")
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
            "language": { "code": "en" } # DASHBOARD: Status 'Active - English' ka code 'en' hota hai
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
    print(f"\n📝 [DEBUG] New Subscribe Request for: {lead.product_title} on {lead.shop}") 
    
    store = await shop_collection.find_one({"shop": lead.shop})
    if not store: 
        print("❌ [ERROR] Store not found.")
        return {"status": "error"}
    
    # Check Real-time Stock
    url = f"https://{lead.shop}/admin/api/{SHOPIFY_API_VERSION}/products/{lead.product_id}.json"
    headers = {"X-Shopify-Access-Token": store["access_token"]}
    r = requests.get(url, headers=headers)
    
    inventory = 0
    if r.status_code == 200:
        variants = r.json().get("product", {}).get("variants", [])
        inventory = sum(v.get("inventory_quantity", 0) for v in variants)
    
    if inventory > 0:
        print("🚫 [REJECT] Product is already in stock.")
        return {"status": "error", "message": "Product is already in stock!"}
    
    # Save to Database
    new_lead = lead.dict()
    new_lead["created_at"] = datetime.utcnow()
    new_lead["status"] = "pending"
    await leads_collection.insert_one(new_lead)
    print("💾 [SAVED] Customer saved to database.") 
    
    # 🟢 MSG 1: Immediate confirmation after subscription
    # Template name fixed to match your screenshot
    send_whatsapp_message(lead.phone_number, template_name="subscription_con")
    
    return {"status": "success", "message": "You will be notified!"}

# 🟢 MSG 2: Automatic Restock Alert via Webhook
@router.post("/api/webhooks/product_update")
async def product_update_webhook(request: Request):
    print("\n\n🔔 -------- WEBHOOK RECEIVED --------") 
    try:
        shop_domain = request.headers.get("X-Shopify-Shop-Domain")
        if not shop_domain:
            return {"status": "error"}

        payload = await request.json()
        product_id = payload.get("id")
        
        # Calculate new stock level
        variants = payload.get("variants", [])
        total_stock = sum(v.get("inventory_quantity", 0) for v in variants)
        
        print(f"🏪 Shop: {shop_domain} | 📦 Product: {product_id} | 📈 Stock: {total_stock}") 
        
        if total_stock > 0:
            # Find all pending users for this specific product and shop
            pending_leads = await leads_collection.find(
                {
                    "product_id": str(product_id), 
                    "status": "pending",
                    "shop": shop_domain
                }
            ).to_list(length=100)
            
            if len(pending_leads) > 0:
                for lead in pending_leads:
                    # 🟢 Restock Alert Message
                    # Template name fixed to match your screenshot
                    success = send_whatsapp_message(lead.get("phone_number"), template_name="item_back_in_stc")
                    
                    if success:
                        await leads_collection.update_one(
                            {"_id": lead["_id"]}, 
                            {"$set": {"status": "notified", "notified_at": datetime.utcnow()}}
                        )
            else:
                print("😴 No pending subscriptions for this item.")
        else:
            print("📉 Item updated but still out of stock.")
            
        print("🔔 -------- WEBHOOK PROCESSED --------\n")
        return {"status": "success"}
        
    except Exception as e:
        print(f"❌ Webhook Error: {str(e)}") 
        return {"status": "error"}