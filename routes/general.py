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
        print("⚠️ [ERROR] WhatsApp Keys are missing in .env file!")
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
            "language": { "code": "en_US" } 
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
        print("❌ [ERROR] Store not found in database.")
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
    
    # Save to Database (With Shop Name)
    new_lead = lead.dict()
    new_lead["created_at"] = datetime.utcnow()
    new_lead["status"] = "pending"
    await leads_collection.insert_one(new_lead)
    print("💾 [SAVED] Customer saved to database.") 
    
    # Send Welcome Message
    send_whatsapp_message(lead.phone_number, template_name="subscription_confirmed")
    
    return {"status": "success", "message": "You will be notified!"}

# 🟢 FINAL MULTI-STORE WEBHOOK
@router.post("/api/webhooks/product_update")
async def product_update_webhook(request: Request):
    print("\n\n🔔 -------- WEBHOOK RECEIVED (Multi-Store) --------") 
    try:
        # 🟢 1. IDENTIFY THE SHOP (Header se pata lagayenge ke kaunsa store hai)
        shop_domain = request.headers.get("X-Shopify-Shop-Domain")
        if not shop_domain:
            print("⚠️ No Shop Domain in Header. Skipping.")
            return {"status": "error"}

        print(f"🏪 Shop Detected: {shop_domain}")

        # 2. Receive Payload
        payload = await request.json()
        product_id = payload.get("id")
        
        # 3. Check Inventory Level
        variants = payload.get("variants", [])
        total_stock = sum(v.get("inventory_quantity", 0) for v in variants)
        
        print(f"📦 Product ID: {product_id} | New Stock: {total_stock}") 
        
        # 4. If Stock is Back (> 0)
        if total_stock > 0:
            print("🚀 [ACTION] Stock > 0. Searching for waiting customers...") 
            
            # 🟢 5. FIND CUSTOMERS FOR *THIS* SHOP ONLY
            pending_leads = await leads_collection.find(
                {
                    "product_id": str(product_id), 
                    "status": "pending",
                    "shop": shop_domain  # <--- SIRF IS STORE KE LOG
                }
            ).to_list(length=100)
            
            print(f"👥 [DEBUG] Found {len(pending_leads)} customers waiting on {shop_domain}.") 

            if len(pending_leads) > 0:
                for lead in pending_leads:
                    print(f"📲 [SENDING] Alert to: {lead['phone_number']}...")
                    
                    success = send_whatsapp_message(lead.get("phone_number"), template_name="item_back_in_stock")
                    
                    if success:
                        await leads_collection.update_one(
                            {"_id": lead["_id"]}, 
                            {"$set": {"status": "notified", "notified_at": datetime.utcnow()}}
                        )
                        print("✅ [UPDATED] Database updated.")
            else:
                print("😴 [INFO] No one waiting on this store.")

        else:
            print("📉 [INFO] Stock is 0.")
            
        print("🔔 ---------------- END WEBHOOK ----------------\n")
        return {"status": "success"}
        
    except Exception as e:
        print(f"❌ [CRITICAL ERROR] Webhook failed: {str(e)}") 
        return {"status": "error"}