import os
import requests
import time
import uuid

# --- Helper to run GraphQL queries ---
def shopify_graphql(shop, access_token, query, variables=None):
    url = f"https://{shop}/admin/api/2024-01/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers, json={"query": query, "variables": variables})
    try:
        return response.json()
    except:
        return {"errors": [{"message": "Invalid JSON response from Shopify"}]}

# --- Step 0: Delete existing videos to prevent duplicates ---
def delete_existing_video_from_product(shop, access_token, product_id):
    if not str(product_id).startswith("gid://"):
        product_id = f"gid://shopify/Product/{product_id}"

    # 1. Get current media nodes
    query_get_media = """
    query($id: ID!) {
      product(id: $id) {
        media(first: 20) {
          nodes {
            id
            mediaContentType
          }
        }
      }
    }
    """
    res = shopify_graphql(shop, access_token, query_get_media, {"id": product_id})
    media_nodes = res.get('data', {}).get('product', {}).get('media', {}).get('nodes', [])

    # 2. Filter for VIDEO IDs
    video_media_ids = [m['id'] for m in media_nodes if m['mediaContentType'] == 'VIDEO']

    if video_media_ids:
        print(f"🗑️ Deleting {len(video_media_ids)} existing video(s)...")
        query_delete = """
        mutation productDeleteMedia($productId: ID!, $mediaIds: [ID!]!) {
          productDeleteMedia(productId: $productId, mediaIds: $mediaIds) {
            deletedMediaIds
            userErrors { message }
          }
        }
        """
        shopify_graphql(shop, access_token, query_delete, {
            "productId": product_id, 
            "mediaIds": video_media_ids
        })

# --- Step 7: Move video to first position for Catalogue visibility ---
def move_video_to_front(shop, access_token, product_id, media_id):
    print("🔄 Reordering: Moving video to the front of the gallery...")
    query_reorder = """
    mutation productReorderMedia($id: ID!, $moves: [MoveInput!]!) {
      productReorderMedia(id: $id, moves: $moves) {
        userErrors { message }
      }
    }
    """
    vars_reorder = {
        "id": product_id,
        "moves": [{"id": media_id, "newPosition": "0"}]
    }
    return shopify_graphql(shop, access_token, query_reorder, vars_reorder)

# --- Main Upload Function ---
def upload_video_to_shopify_gallery(shop, access_token, product_id, video_path):
    print(f"\n{'='*20} PROCESS START {'='*20}")
    print(f"🚀 Target Product: {product_id}")
    
    if not os.path.exists(video_path):
        print("❌ Error: Local video file not found.")
        return {"error": "Video file not found on server"}

    # 🟢 NEW: Clean up old videos first
    delete_existing_video_from_product(shop, access_token, product_id)

    # 1. Generate Unique Info
    unique_id = str(uuid.uuid4())[:12]
    file_size = os.path.getsize(video_path)
    file_name = f"vid_{unique_id}.mp4" 
    mime_type = "video/mp4" 

    # 2. Staged Upload Create
    query_stage = """
    mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
      stagedUploadsCreate(input: $input) {
        stagedTargets { url resourceUrl parameters { name value } }
        userErrors { message }
      }
    }
    """
    res = shopify_graphql(shop, access_token, query_stage, {"input": [{"resource": "VIDEO", "filename": file_name, "mimeType": mime_type, "fileSize": str(file_size), "httpMethod": "POST"}]})
    
    if not res.get("data") or res["data"]["stagedUploadsCreate"]["userErrors"]:
        return {"error": "Stage Create Failed"}

    target = res['data']['stagedUploadsCreate']['stagedTargets'][0]
    resource_url = target['resourceUrl']

    # 3. Physical Upload
    files_payload = [(p['name'], (None, p['value'])) for p in target['parameters']]
    with open(video_path, 'rb') as f:
        files_payload.append(('file', (file_name, f.read(), mime_type)))
    
    requests.post(target['url'], files=files_payload, timeout=60)

    # 4. Register File
    query_file = """
    mutation fileCreate($files: [FileCreateInput!]!) {
      fileCreate(files: $files) {
        files { id fileStatus }
        userErrors { message }
      }
    }
    """
    res_file = shopify_graphql(shop, access_token, query_file, {"files": [{"originalSource": resource_url, "contentType": "VIDEO"}]})
    media_id = res_file['data']['fileCreate']['files'][0]['id']

    # 5. Poll for READY status
    for i in range(40):
        time.sleep(3)
        query_check = "query($id: ID!) { node(id: $id) { ... on Video { fileStatus } } }"
        status_res = shopify_graphql(shop, access_token, query_check, {"id": media_id})
        status = status_res.get("data", {}).get("node", {}).get("fileStatus")
        print(f"   Status: {status}")
        if status == 'READY': break
    else: 
        return {"error": "Video did not reach READY state in time."}

    # 6. Attach to Product Gallery (Using ID to avoid Duplicate Error)
    if not str(product_id).startswith("gid://"):
        product_id = f"gid://shopify/Product/{product_id}"

    query_attach = """
    mutation productCreateMedia($media: [CreateMediaInput!]!, $productId: ID!) {
      productCreateMedia(media: $media, productId: $productId) {
        media { id status }
        mediaUserErrors { message }
      }
    }
    """
    
    attach_vars = {
        "productId": product_id,
        "media": [{"mediaContentType": "VIDEO", "id": media_id}] # 🟢 Fix: Use media_id
    }

    final_res = shopify_graphql(shop, access_token, query_attach, attach_vars)
    
    if final_res.get("data", {}).get("productCreateMedia", {}).get("mediaUserErrors"):
        return {"status": "failed", "details": final_res['data']['productCreateMedia']['mediaUserErrors']}

    # 7. Move to front for Catalogue
    move_video_to_front(shop, access_token, product_id, media_id)

    print(f"{'='*20} SUCCESS: VIDEO PINNED & REORDERED {'='*20}\n")
    return {"status": "success", "media_id": media_id}