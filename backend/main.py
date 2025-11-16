from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from bson import ObjectId
from database import db, create_document, get_documents
import os

# -----------------------------
# Utilities
# -----------------------------
class ObjectIdStr(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        try:
            ObjectId(str(v))
            return str(v)
        except Exception:
            raise ValueError("Invalid ObjectId")


def serialize_doc(doc: dict):
    if not doc:
        return doc
    doc["id"] = str(doc.pop("_id")) if doc.get("_id") else None
    return doc


# -----------------------------
# Pydantic Models
# -----------------------------
class ProductIn(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
    images: List[str] = []
    model_url: Optional[str] = None
    featured: bool = False
    rating: float = 4.6
    specs: Optional[dict] = None


class ProductOut(ProductIn):
    id: ObjectIdStr


# -----------------------------
# App Init
# -----------------------------
app = FastAPI(title="FlamesBlue Electronics API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Seed Data
# -----------------------------
SAMPLE_PRODUCTS = [
    {
        "title": "FlamesBlue Nova X Pro",
        "description": "Flagship 6.7\" OLED, triple camera, 5G.",
        "price": 1099.0,
        "category": "Phones",
        "in_stock": True,
        "images": [
            "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=1200&q=80&auto=format&fit=crop",
        ],
        "model_url": None,
        "featured": True,
        "rating": 4.8,
        "specs": {"display": "6.7\" OLED", "chip": "FBX-2", "ram": "12GB", "storage": "256GB"},
    },
    {
        "title": "FlamesBlue AirLite Case",
        "description": "Featherweight, shock-absorbent case for Nova series.",
        "price": 39.0,
        "category": "Phone Cases",
        "in_stock": True,
        "images": [
            "https://images.unsplash.com/photo-1585386959984-a4155223168f?w=1200&q=80&auto=format&fit=crop",
        ],
        "model_url": None,
        "featured": True,
        "rating": 4.5,
        "specs": {"material": "TPU", "weight": "18g"},
    },
    {
        "title": "FlamesBlue Atlas 15",
        "description": "Ultrabook 15\" with RTX graphics for creators.",
        "price": 1799.0,
        "category": "Laptops",
        "in_stock": True,
        "images": [
            "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=1200&q=80&auto=format&fit=crop",
        ],
        "model_url": None,
        "featured": True,
        "rating": 4.7,
        "specs": {"cpu": "12-core", "gpu": "RTX 4060", "ram": "32GB", "storage": "1TB"},
    },
    {
        "title": "FlamesBlue Arc Buds",
        "description": "ANC wireless earbuds with spatial audio.",
        "price": 149.0,
        "category": "Accessories",
        "in_stock": True,
        "images": [
            "https://images.unsplash.com/photo-1518445696298-1f784b22145a?w=1200&q=80&auto=format&fit=crop",
        ],
        "model_url": None,
        "featured": False,
        "rating": 4.4,
        "specs": {"battery": "36h", "waterproof": "IPX5"},
    },
]


@app.on_event("startup")
def seed_database_if_empty():
    if db is None:
        return
    try:
        count = db["product"].count_documents({})
        if count == 0:
            for p in SAMPLE_PRODUCTS:
                create_document("product", p)
    except Exception:
        pass


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def root():
    return {"message": "FlamesBlue Electronics API is live"}


@app.get("/test")
def test_database():
    database_url = os.getenv("DATABASE_URL", "<not-set>")
    database_name = os.getenv("DATABASE_NAME", "<not-set>")
    status = {
        "backend": "ok",
        "database": "connected" if db is not None else "unavailable",
        "database_url": database_url[:20] + "..." if database_url and database_url != "<not-set>" else "<not-set>",
        "database_name": database_name,
        "connection_status": "OK" if db is not None else "NOT CONNECTED",
        "collections": []
    }
    try:
        if db is not None:
            status["collections"] = db.list_collection_names()
    except Exception:
        status["database"] = "error"
        status["connection_status"] = "ERROR"
    return status


@app.get("/api/categories", response_model=List[str])
def get_categories():
    if db is None:
        return ["Phones", "Laptops", "Phone Cases", "Accessories"]
    return sorted(db["product"].distinct("category"))


@app.get("/api/products", response_model=List[ProductOut])
def list_products(category: Optional[str] = None, limit: int = Query(20, ge=1, le=100)):
    filter_dict = {}
    if category:
        filter_dict["category"] = category
    docs = get_documents("product", filter_dict, limit)
    return [ProductOut(**serialize_doc(d)) for d in docs]


@app.get("/api/products/featured", response_model=List[ProductOut])
def featured_products(limit: int = Query(10, ge=1, le=50)):
    docs = get_documents("product", {"featured": True}, limit)
    return [ProductOut(**serialize_doc(d)) for d in docs]


@app.get("/api/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        doc = db["product"].find_one({"_id": ObjectId(product_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut(**serialize_doc(doc))


@app.get("/api/search", response_model=List[ProductOut])
def search_products(q: str, limit: int = Query(20, ge=1, le=100)):
    if not q:
        return []
    filt = {"title": {"$regex": q, "$options": "i"}}
    docs = get_documents("product", filt, limit)
    return [ProductOut(**serialize_doc(d)) for d in docs]


@app.get("/api/recommendations/{product_id}", response_model=List[ProductOut])
def recommendations(product_id: str, limit: int = Query(4, ge=1, le=12)):
    if db is None:
        return []
    try:
        doc = db["product"].find_one({"_id": ObjectId(product_id)})
    except Exception:
        return []
    if not doc:
        return []
    category = doc.get("category")
    docs = db["product"].find({"category": category, "_id": {"$ne": doc["_id"]}}).limit(limit)
    return [ProductOut(**serialize_doc(d)) for d in docs]
