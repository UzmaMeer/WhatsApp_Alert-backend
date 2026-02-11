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
    Returns True if successful, False otherwise.
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
    
    # Clean formatting from phone number
    clean_phone = phone_number.replace("+", "").replace(" ", "").strip()

    payload = {
        "messaging_product": "whatsapp",
        "to": clean_phone,
        "type": "template",
        "template": { 
            "name": template_name,
            "language": { "code": "en" } # Ensure your Meta template is approved in English
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
    """
    Fetches the list of products from the merchant's Shopify store.
    """
    if not shop: return {"products": []}
    
    # Retrieve shop access token from database
    store = await shop_collection.find_one({"shop": shop})
    if not store: return {"products": []}
    
    url = f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}/products.json"
    headers = {"X-Shopify-Access-Token": store["access_token"]}
    
    try:
        r = requests.get(url, headers=headers, params={"limit": 50})
        return {"products": r.json().get("products", [])}
    except Exception as e:
        print(f"❌ Error fetching products: {str(e)}")
        return {"products": []}

@router.post("/api/subscribe")
async def subscribe_lead(lead: LeadRequest):
    """
    Registers a customer's request to be notified when a product is back in stock.
    """
    print(f"\n📝 [DEBUG] New Subscribe Request for: {lead.product_title} on {lead.shop}") 
    
    store = await shop_collection.find_one({"shop": lead.shop})
    if not store: 
        print("❌ [ERROR] Store not found in database.")
        return {"status": "error"}
    
    # Verify real-time stock status before allowing subscription
    url = f"https://{lead.shop}/admin/api/{SHOPIFY_API_VERSION}/products/{lead.product_id}.json"
    headers = {"X-Shopify-Access-Token": store["access_token"]}
    r = requests.get(url, headers=headers)
    
    inventory = 0
    if r.status_code == 200:
        variants = r.json().get("product", {}).get("variants", [])
        inventory = sum(v.get("inventory_quantity", 0) for v in variants)
    
    if inventory > 0:
        print("🚫 [REJECT] Product is already in stock. Subscription not allowed.")
        return {"status": "error", "message": "Product is already in stock!"}
    
    # Save lead information to MongoDB
    new_lead = lead.dict()
    new_lead["created_at"] = datetime.utcnow()
    new_lead["status"] = "pending"
    await leads_collection.insert_one(new_lead)
    print("💾 [SAVED] Customer saved to database successfully.") 
    
    # TRIGGER 1: Send immediate 'Subscription Confirmed' WhatsApp message
    send_whatsapp_message(lead.phone_number, template_name="subscription_con")
    
    return {"status": "success", "message": "You will be notified!"}

@router.post("/api/webhooks/product_update")
async def product_update_webhook(request: Request):
    """
    Shopify Webhook listener. Triggered whenever a product's inventory changes.
    If stock becomes > 0, it notifies all pending customers.
    """
    print("\n\n🔔 -------- WEBHOOK RECEIVED FROM SHOPIFY --------") 
    try:
        shop_domain = request.headers.get("X-Shopify-Shop-Domain")
        if not shop_domain:
            return {"status": "error", "message": "Missing shop domain header"}

        payload = await request.json()
        product_id = payload.get("id")
        
        # Calculate total stock across all product variants
        variants = payload.get("variants", [])
        total_stock = sum(v.get("inventory_quantity", 0) for v in variants)
        
        print(f"🏪 Shop: {shop_domain} | 📦 Product ID: {product_id} | 📈 Current Stock: {total_stock}") 
        
        if total_stock > 0:
            # Find all pending leads for this specific product in this shop
            pending_leads = await leads_collection.find(
                {
                    "product_id": str(product_id), 
                    "status": "pending",
                    "shop": shop_domain
                }
            ).to_list(length=500)
            
            if len(pending_leads) > 0:
                print(f"🎯 Found {len(pending_leads)} customers to notify.")
                for lead in pending_leads:
                    # TRIGGER 2: Send 'Item Back in Stock' Alert
                    success = send_whatsapp_message(lead.get("phone_number"), template_name="item_back_in_stc")
                    
                    if success:
                        # Update lead status to 'notified' to avoid duplicate alerts
                        await leads_collection.update_one(
                            {"_id": lead["_id"]}, 
                            {"$set": {"status": "notified", "notified_at": datetime.utcnow()}}
                        )
            else:
                print("😴 No pending subscriptions for this item.")
        else:
            print("📉 Item updated but total stock is still 0.")
            
        print("🔔 -------- WEBHOOK PROCESSED SUCCESSFULLY --------\n")
        return {"status": "success"}
        
    except Exception as e:
        print(f"❌ Webhook Processing Error: {str(e)}") 
        return {"status": "error"}