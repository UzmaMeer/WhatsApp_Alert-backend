import os
import requests
import google.generativeai as genai
from pymongo import MongoClient 
from datetime import datetime
from dotenv import load_dotenv
from celery import Celery  

load_dotenv()

# 🟢 CRITICAL IMPORT: Imports the updated video generation logic from utils.py
from utils import generate_video_from_images 

# --- 1. CELERY CONFIGURATION (Windows Compatible) ---
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

celery_app = Celery(
    "video_tasks",
    broker=redis_url,
    backend=redis_url
)

# --- CONFIGURATION ---
MONGO_DETAILS = os.getenv("MONGO_DETAILS")
client = MongoClient(MONGO_DETAILS) 
db = client.video_ai_db
video_jobs_collection = db.get_collection("video_jobs")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
BASE_PUBLIC_URL = os.getenv("BASE_PUBLIC_URL", "")

# --- HELPER FUNCTIONS ---
def generate_viral_caption(title, desc):
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = (f"Write a short, viral Instagram/TikTok caption for '{title}'. Include 3-4 trending hashtags. Under 2 sentences. No quotes.")
        resp = model.generate_content(prompt)
        return resp.text.strip()
    except:
        return f"Check out {title}! #Trending #Fashion"

# --- THE MAIN WORKER FUNCTION ---
@celery_app.task(name="process_video_job_task")
def process_video_job_task(job_id, image_urls, title, desc, logo_url, voice_gender, 
                           duration, script_tone, custom_music_path, video_theme="Modern", 
                           shop_name=None, custom_script=None, user_voice_audio=None):
    
    print(f"🛠️ Worker Starting Job: {job_id}")

    def update_progress_db(percent):
        video_jobs_collection.update_one(
            {"job_id": job_id},
            {"$set": {"progress": percent, "status": "processing", "updated_at": datetime.utcnow()}}
        )

    try:
        update_progress_db(10)

        # 🟢 Pass the overrides into the generator function
        filename, script_used = generate_video_from_images(
            image_urls=image_urls, 
            product_title=title, 
            product_desc=desc, 
            logo_url=logo_url, 
            gender=voice_gender, 
            target_duration=duration, 
            script_tone=script_tone, 
            custom_music_path=custom_music_path, 
            progress_callback=update_progress_db,  
            shop_name=shop_name, 
            video_theme=video_theme,
            custom_script=custom_script,       
            user_voice_audio=user_voice_audio  
        )
        
        if filename:
            update_progress_db(98)
            smart_caption = generate_viral_caption(title, desc)
            video_url = f"{BASE_PUBLIC_URL}/static/{filename}"
            print(f"✅ Worker Finished: {filename}")
            
            video_jobs_collection.update_one(
                {"job_id": job_id},
                {
                    "$set": {
                        "status": "done", 
                        "progress": 100, 
                        "url": video_url, 
                        "filename": filename, 
                        "caption": smart_caption,
                        "completed_at": datetime.utcnow()
                    }
                }
            )
        else:
            print(f"❌ Worker Failed: Utils returned None for {job_id}")
            video_jobs_collection.update_one(
                {"job_id": job_id},
                {"$set": {"status": "failed", "error": "Video generation returned no file."}}
            )

    except Exception as e:
        print(f"❌ Worker CRASH Error: {e}")
        video_jobs_collection.update_one(
            {"job_id": job_id},
            {"$set": {"status": "failed", "error": str(e)}}
        )