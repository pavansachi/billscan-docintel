import os
import sqlite3
import argparse
from sentence_transformers import SentenceTransformer
import chromadb
from tabulate import tabulate

DB_PATH = "receipts.db"
CHROMA_PATH = "chroma_db"

def list_receipts():
    """Lists all receipts stored in SQLite."""
    if not os.path.exists(DB_PATH):
        print("Database receipts.db does not exist yet. Run 'index_receipts.py' first.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, merchant_name, transaction_date, total, currency 
        FROM receipts 
        ORDER BY transaction_date DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("No receipts found in the database.")
        return
        
    print("\n--- ALL INDEXED RECEIPTS ---")
    headers = ["ID (Short)", "Merchant Name", "Transaction Date", "Total Spent", "Currency"]
    # Truncate ID for readability
    display_rows = [
        (r[0][:8], r[1], r[2], f"{r[3]:.2f}" if r[3] is not None else "N/A", r[4]) 
        for r in rows
    ]
    print(tabulate(display_rows, headers=headers, tablefmt="grid"))

def semantic_search(query: str, n_results: int = 5):
    """Searches for items using semantic text matching in Chroma DB."""
    if not os.path.exists(CHROMA_PATH):
        print("Vector database chroma_db does not exist yet. Run 'index_receipts.py' first.")
        return

    print(f"Loading Hugging Face embedding model (all-MiniLM-L6-v2) for search...")
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    query_vector = embedding_model.encode(query).tolist()
    
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        collection = chroma_client.get_collection(name="receipt_items")
    except Exception:
        print("No indexed receipt items found in Chroma DB. Please run 'index_receipts.py' first.")
        return

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=n_results
    )
    
    if not results or not results['metadatas'] or not results['metadatas'][0]:
        print("No matching items found.")
        return

    print(f"\n--- SEMANTIC SEARCH RESULTS FOR: '{query}' ---")
    display_rows = []
    for idx in range(len(results['metadatas'][0])):
        meta = results['metadatas'][0][idx]
        distance = results['distances'][0][idx]
        # Distance to similarity: 1 - distance (approximate cosine similarity)
        similarity = 1.0 - distance
        
        display_rows.append((
            meta.get("description"),
            meta.get("merchant_name"),
            meta.get("category"),
            meta.get("sub_category"),
            f"{meta.get('price'):.2f} {meta.get('currency')}",
            f"{similarity * 100:.1f}%"
        ))
        
    headers = ["Item Description", "Merchant", "Category", "Sub-Category", "Price", "Match Score"]
    print(tabulate(display_rows, headers=headers, tablefmt="grid"))

def run_report(group_by: str):
    """Runs aggregations on the SQLite database."""
    if not os.path.exists(DB_PATH):
        print("Database receipts.db does not exist yet. Run 'index_receipts.py' first.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if group_by == "category":
        cursor.execute("""
            SELECT category, SUM(price * quantity) as total_spent, currency, COUNT(*) as item_count 
            FROM receipt_items 
            JOIN receipts ON receipt_items.receipt_id = receipts.id
            GROUP BY category, currency
            ORDER BY total_spent DESC
        """)
        rows = cursor.fetchall()
        headers = ["Category", "Total Spent", "Currency", "Item Count"]
        
    elif group_by == "subcategory":
        cursor.execute("""
            SELECT category, sub_category, SUM(price * quantity) as total_spent, currency, COUNT(*) as item_count 
            FROM receipt_items 
            JOIN receipts ON receipt_items.receipt_id = receipts.id
            GROUP BY category, sub_category, currency
            ORDER BY total_spent DESC
        """)
        rows = cursor.fetchall()
        headers = ["Category", "Sub-Category", "Total Spent", "Currency", "Item Count"]
        
    elif group_by == "monthly":
        cursor.execute("""
            SELECT strftime('%Y-%m', transaction_date) as month, SUM(total) as total_spent, currency, COUNT(id) as receipt_count
            FROM receipts
            GROUP BY month, currency
            ORDER BY month ASC
        """)
        rows = cursor.fetchall()
        headers = ["Month", "Total Spent", "Currency", "Receipt Count"]
        
    else:
        print(f"Unknown report type: {group_by}. Choose from 'category', 'subcategory', 'monthly'.")
        conn.close()
        return

    conn.close()

    if not rows:
        print("No data available to run reports.")
        return
        
    print(f"\n--- SPENDING REPORT GROUPED BY: {group_by.upper()} ---")
    
    # Format the REAL numbers in rows for cleaner presentation
    display_rows = []
    for r in rows:
        formatted_row = list(r)
        # Find index of total_spent depending on query
        if group_by == "category":
            formatted_row[1] = f"${r[1]:.2f}"
        elif group_by == "subcategory":
            formatted_row[2] = f"${r[2]:.2f}"
        elif group_by == "monthly":
            formatted_row[1] = f"${r[1]:.2f}"
        display_rows.append(formatted_row)
        
    print(tabulate(display_rows, headers=headers, tablefmt="grid"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query and aggregate receipt scanning databases.")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--list", "-l", 
        action="store_true", 
        help="List all receipts currently indexed."
    )
    group.add_argument(
        "--search", "-s", 
        type=str, 
        help="Perform semantic search on line items."
    )
    group.add_argument(
        "--report", "-r", 
        choices=["category", "subcategory", "monthly"], 
        help="Generate aggregation spending reports."
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_receipts()
    elif args.search:
        semantic_search(args.search)
    elif args.report:
        run_report(args.report)
