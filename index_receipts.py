import os
import json
import sqlite3
import hashlib
from sentence_transformers import SentenceTransformer
import chromadb

# Constants
DB_PATH = "receipts.db"
CHROMA_PATH = "chroma_db"
JSON_DIR = "receipts_json"

# Rule-based Categorization Dictionary
CATEGORIES = {
    # electronics
    "airpod": ("electronics", "headphone"),
    "headphone": ("electronics", "headphone"),
    "earbud": ("electronics", "headphone"),
    "phone": ("electronics", "mobile"),
    "charger": ("electronics", "accessory"),
    "cable": ("electronics", "accessory"),
    "tv": ("electronics", "display"),
    "laptop": ("electronics", "computer"),
    "ipad": ("electronics", "tablet"),
    "wacom": ("electronics", "tablet"),
    "applecare": ("electronics", "service"),
    "extracover": ("electronics", "warranty"),
    
    # eatout
    "frappe": ("eatout", "coffee"),
    "mocha": ("eatout", "coffee"),
    "coffee": ("eatout", "coffee"),
    "latte": ("eatout", "coffee"),
    "cappuccino": ("eatout", "coffee"),
    "espresso": ("eatout", "coffee"),
    "burger": ("eatout", "fastfood"),
    "pizza": ("eatout", "fastfood"),
    "fries": ("eatout", "fastfood"),
    "drink": ("eatout", "beverage"),
    "soda": ("eatout", "beverage"),
    "coke": ("eatout", "beverage"),
    "water": ("eatout", "beverage"),
    
    # grocery
    "apple": ("grocery", "fruit"),
    "banana": ("grocery", "fruit"),
    "orange": ("grocery", "fruit"),
    "berry": ("grocery", "fruit"),
    "grape": ("grocery", "fruit"),
    "tomato": ("grocery", "vegetable"),
    "potato": ("grocery", "vegetable"),
    "onion": ("grocery", "vegetable"),
    "lettuce": ("grocery", "vegetable"),
    "milk": ("grocery", "dairy"),
    "cheese": ("grocery", "dairy"),
    "butter": ("grocery", "dairy"),
    "bread": ("grocery", "bakery"),
    "egg": ("grocery", "poultry"),
    "chicken": ("grocery", "meat"),
    "beef": ("grocery", "meat"),
    "pork": ("grocery", "meat"),
    
    # clothing
    "shirt": ("clothing", "apparel"),
    "pants": ("clothing", "apparel"),
    "jeans": ("clothing", "apparel"),
    "jacket": ("clothing", "apparel"),
    "shoes": ("clothing", "footwear"),
    "socks": ("clothing", "footwear"),
}

def categorize_item(description: str) -> tuple:
    """
    Categorizes a line item based on its description text using rule-based keywords.
    Returns (category, sub_category).
    """
    desc_lower = description.lower()
    for keyword, cat_sub in CATEGORIES.items():
        if keyword in desc_lower:
            return cat_sub
    return ("other", "general")

def init_sqlite():
    """Initializes SQLite tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS receipts (
        id TEXT PRIMARY KEY,
        merchant_name TEXT,
        transaction_date TEXT,
        total REAL,
        tax REAL,
        currency TEXT,
        file_path TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS receipt_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_id TEXT,
        description TEXT,
        quantity REAL,
        price REAL,
        category TEXT,
        sub_category TEXT,
        FOREIGN KEY (receipt_id) REFERENCES receipts(id)
    )
    """)
    
    conn.commit()
    return conn

def get_val(field_dict, val_key, default=None):
    if not field_dict:
        return default
    return field_dict.get(val_key, default)

def index_all_json():
    # 1. Initialize DBs
    conn = init_sqlite()
    cursor = conn.cursor()
    
    print("Connecting to Chroma Vector DB...")
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_or_create_collection(name="receipt_items")
    
    print("Loading Hugging Face embedding model (all-MiniLM-L6-v2)...")
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    
    if not os.path.exists(JSON_DIR):
        print(f"No JSON directory found at '{JSON_DIR}'. Please analyze receipts first.")
        return

    json_files = [f for f in os.listdir(JSON_DIR) if f.lower().endswith(".json")]
    if not json_files:
        print(f"No JSON files found in '{JSON_DIR}'.")
        return

    print(f"Found {len(json_files)} JSON files to index.\n")
    
    for filename in json_files:
        json_path = os.path.join(JSON_DIR, filename)
        receipt_id = hashlib.md5(filename.encode()).hexdigest()
        
        print(f"Indexing {filename} (ID: {receipt_id})...")
        
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Parse documents list from Azure output
        documents = data.get("documents", [])
        if not documents:
            print(f"  No structured documents in {filename}. Skipping.")
            continue
            
        # Clear existing data for this receipt to avoid duplicates
        cursor.execute("DELETE FROM receipt_items WHERE receipt_id = ?", (receipt_id,))
        cursor.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
        
        try:
            # We can use metadata filtering in Chroma to delete matching records
            collection.delete(where={"receipt_id": receipt_id})
        except Exception:
            # Collection might be empty
            pass
            
        for doc in documents:
            fields = doc.get("fields", {})
            if not fields:
                continue
                
            # Extract receipt metadata
            merchant_name = get_val(fields.get("MerchantName"), "valueString", "Unknown")
            trans_date = get_val(fields.get("TransactionDate"), "valueDate", None)
            
            total_dict = get_val(fields.get("Total"), "valueCurrency")
            total = total_dict.get("amount") if total_dict else None
            currency = total_dict.get("currencyCode", "AUD") if total_dict else "AUD"
            
            tax_dict = get_val(fields.get("TotalTax"), "valueCurrency")
            tax = tax_dict.get("amount") if tax_dict else None
            
            # Save receipt
            cursor.execute("""
            INSERT INTO receipts (id, merchant_name, transaction_date, total, tax, currency, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (receipt_id, merchant_name, trans_date, total, tax, currency, json_path))
            
            # Process and index line items
            items_field = fields.get("Items", {})
            items_list = items_field.get("valueArray", [])
            
            for item in items_list:
                item_obj = item.get("valueObject", {})
                
                qty = get_val(item_obj.get("Quantity"), "valueNumber", 1.0)
                desc = get_val(item_obj.get("Description"), "valueString", "Unknown Item")
                
                price_dict = get_val(item_obj.get("TotalPrice"), "valueCurrency")
                price = price_dict.get("amount") if price_dict else None
                
                # Categorize item
                category, sub_category = categorize_item(desc)
                
                # Save item to SQLite
                cursor.execute("""
                INSERT INTO receipt_items (receipt_id, description, quantity, price, category, sub_category)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (receipt_id, desc, qty, price, category, sub_category))
                
                item_sqlite_id = cursor.lastrowid
                
                # Create text description for vector search
                price_str = f"{price:.2f} {currency}" if price is not None else "N/A"
                text_to_embed = (
                    f"Item: {desc}. Category: {category} ({sub_category}). "
                    f"Merchant: {merchant_name}. Date: {trans_date}. Price: {price_str}."
                )
                
                # Embed text using local model
                embedding = embedding_model.encode(text_to_embed).tolist()
                
                # Add to Chroma Vector DB
                metadata = {
                    "item_id": int(item_sqlite_id),
                    "receipt_id": receipt_id,
                    "description": desc,
                    "category": category,
                    "sub_category": sub_category,
                    "merchant_name": merchant_name,
                    "price": float(price) if price is not None else 0.0,
                    "currency": currency
                }
                
                collection.add(
                    embeddings=[embedding],
                    documents=[text_to_embed],
                    metadatas=[metadata],
                    ids=[str(item_sqlite_id)]
                )
                
        print(f"  Successfully indexed fields and items into SQLite & Chroma DB.\n")
        
    conn.commit()
    conn.close()
    print("Database indexing completed successfully!")

if __name__ == "__main__":
    index_all_json()
