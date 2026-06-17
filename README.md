# Azure AI Document Intelligence & Semantic Search Receipt System

This project is a hybrid data extraction, categorization, and semantic search system for receipt scans. It combines **Azure AI Document Intelligence** for document parsing, **SQLite** for structured transactional database reports, and **Chroma DB** with local Hugging Face embeddings for semantic line-item search.

---

## Architecture Overview

```
 ┌────────────────────────┐      ┌─────────────────────────┐
 │ Receipt PDF / Image    ├─────►│ Azure Doc Intel Service │
 └────────────────────────┘      └────────────┬────────────┘
                                              │ (as_dict)
                                              ▼
 ┌────────────────────────┐      ┌─────────────────────────┐
 │ SQLite DB (receipts.db)◄─────┤  index_receipts.py      │
 │ (Reports & Aggregates) │      │  (Item Categorizer)     │
 └────────────────────────┘      └────────────┬────────────┘
                                              │ (all-MiniLM-L6-v2)
                                              ▼
                                 ┌─────────────────────────┐
                                 │  Chroma Vector DB       │
                                 │  (Semantic Search)      │
                                 └─────────────────────────┘
```

1. **Extraction**: `analyze_receipt.py` sends raw images/PDFs of receipts to Azure AI Document Intelligence and saves the response as structured JSON in `.\receipts_json\`.
2. **Database & Categorization**: `index_receipts.py` reads the cached JSON files, automatically classifies each line item into a Category and Sub-category (e.g., `Wacom Tablet` -> `electronics/tablet`), saves structured records to **SQLite**, and generates text embeddings.
3. **Vector Indexing**: The embeddings and item metadata are upserted into a local **Chroma DB** instance.
4. **Retrieval**: `query_receipts.py` performs SQL aggregations for financial reports and vector similarity searches for semantic retrieval.

---

## 1. Prerequisites & Installation

### Option A: Using `uv` (Fastest, Recommended)
If you have `uv` installed, it manages virtual environments and installs dependencies extremely quickly:

```powershell
# Create the virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt
```

### Option B: Standard Python `venv`
```powershell
# Create the virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Install dependencies
.venv\Scripts\pip install -r requirements.txt
```

---

## 2. Configuration

Set your Azure AI Document Intelligence Endpoint and Key as environment variables in your terminal:

```powershell
$env:AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://your-resource-name.cognitiveservices.azure.com/"
$env:AZURE_DOCUMENT_INTELLIGENCE_KEY="your-api-key-here"
```

---

## 3. How to Use

### Step 1: Scan Receipts (`analyze_receipt.py`)
This script uploads local files or URLs to Azure and saves the result as raw JSON files in `.\receipts_json\`.

* **Scan a single local file:**
  ```powershell
  .venv\Scripts\python analyze_receipt.py receipts\your_receipt.pdf
  ```
* **Scan an entire directory of files:**
  ```powershell
  .venv\Scripts\python analyze_receipt.py .\receipts
  ```
* **Scan a receipt with custom query fields (e.g. extracting ABN/PaymentMethod):**
  ```powershell
  .venv\Scripts\python analyze_receipt.py receipts\your_receipt.pdf --query ABN PaymentMethod
  ```

### Step 2: Index and Categorize (`index_receipts.py`)
This processes the cached JSON files, classifies items, and updates SQLite and Chroma DB:

```powershell
.venv\Scripts\python index_receipts.py
```

### Step 3: Query & Generate Reports (`query_receipts.py`)
Once indexed, you can query and search the databases entirely offline.

* **List all receipts in the system:**
  ```powershell
  .venv\Scripts\python query_receipts.py --list
  ```
* **Show spending aggregated by Category:**
  ```powershell
  .venv\Scripts\python query_receipts.py --report category
  ```
* **Show spending aggregated by Sub-category:**
  ```powershell
  .venv\Scripts\python query_receipts.py --report subcategory
  ```
* **Show monthly spending over time:**
  ```powershell
  .venv\Scripts\python query_receipts.py --report monthly
  ```
* **Perform a semantic vector search on line items:**
  ```powershell
  .venv\Scripts\python query_receipts.py --search "something to draw on computer"
  ```
  *(Example: Searching for "drawing device" will find a Wacom Tablet using similarity scores, even if those exact words aren't in the receipt description.)*

---

## Categorization Customization

Line items are categorized automatically by description matching inside `index_receipts.py`. You can expand the keyword mapping dictionary inside `index_receipts.py` to match your specific spending habits:

```python
CATEGORIES = {
    # electronics
    "airpod": ("electronics", "headphone"),
    "wacom": ("electronics", "tablet"),
    
    # eatout
    "mocha": ("eatout", "coffee"),
    "burger": ("eatout", "fastfood"),
    
    # grocery
    "apple": ("grocery", "fruit"),
    "milk": ("grocery", "dairy"),
}
```

---

## Azure Cost Reference (Prebuilt Receipt Model)

| Pricing Tier | Base Analysis Cost | Query Fields Add-on |
| :--- | :--- | :--- |
| **Free (F0)** | Free (up to 500 pages/month) | Free (within 500 pages/month) |
| **Standard (S1)** | $10 per 1,000 pages ($0.01/page) | +$10 per 1,000 pages (+$0.01/page) |

*Note: Once you have run the analysis and saved the JSON files, you can delete the Azure resource or turn off internet access. Indexing, SQL reporting, and semantic searches run completely locally at no cost.*
