from pydantic import BaseModel
from typing import List, Optional

class ReviewRequest(BaseModel):
    name: str
    rating: int
    comment: str
    designation: str

class BrandSettingsRequest(BaseModel):
    shop: str
    primary_color: str
    cta_text: str
    logo_url: Optional[str] = None

class PublishRequest(BaseModel):
    render_job_id: Optional[str] = None
    video_filename: Optional[str] = None
    accounts: List[str]
    caption_override: Optional[str] = None
    product_id: Optional[str] = None

# 🟢 NEW: Model for WhatsApp Subscribers
class LeadRequest(BaseModel):
    shop: str
    product_id: str
    product_title: str
    customer_name: str
    phone_number: str