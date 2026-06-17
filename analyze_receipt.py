import os
import sys
import argparse
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentAnalysisFeature
from azure.core.exceptions import HttpResponseError

# 1. Configuration
ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "YOUR_ENDPOINT_HERE")
KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "YOUR_KEY_HERE")

def analyze_receipt(source_path_or_url: str, query_fields: list = None):
    """
    Analyzes a single receipt document (URL or local file).
    Optional query_fields lists custom fields to extract.
    """
    if "YOUR_ENDPOINT_HERE" in ENDPOINT or "YOUR_KEY_HERE" in KEY:
        print("[Error] Please configure your Azure endpoint and API key in the script or set environment variables:")
        print("  - AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        print("  - AZURE_DOCUMENT_INTELLIGENCE_KEY")
        return

    client = DocumentIntelligenceClient(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(KEY)
    )

    is_url = source_path_or_url.startswith("http://") or source_path_or_url.startswith("https://")
    
    # Configure query fields features if specified
    features = [DocumentAnalysisFeature.QUERY_FIELDS] if query_fields else None

    try:
        if is_url:
            print(f"Analyzing receipt from URL: {source_path_or_url}...")
            poller = client.begin_analyze_document(
                "prebuilt-receipt",
                AnalyzeDocumentRequest(url_source=source_path_or_url),
                features=features,
                query_fields=query_fields
            )
        else:
            if not os.path.exists(source_path_or_url):
                print(f"[Error] Local file not found: {source_path_or_url}")
                return
            
            print(f"Analyzing local receipt file: {source_path_or_url}...")
            with open(source_path_or_url, "rb") as f:
                poller = client.begin_analyze_document(
                    "prebuilt-receipt",
                    body=f,
                    features=features,
                    query_fields=query_fields
                )
        
        result = poller.result()
        print("Analysis completed successfully!\n")
        display_results(result, query_fields)

    except HttpResponseError as e:
        print(f"\n[Error] Azure Service Request Failed for {source_path_or_url}:")
        print(e.message)
    except Exception as e:
        print(f"\n[Error] An unexpected error occurred: {e}")

def process_source(source_path_or_url: str, query_fields: list = None):
    """
    Determines if source is a URL, a single file, or a directory of files,
    and runs analysis accordingly.
    """
    is_url = source_path_or_url.startswith("http://") or source_path_or_url.startswith("https://")
    
    if not is_url and os.path.isdir(source_path_or_url):
        print(f"Source is a directory. Scanning folder '{source_path_or_url}'...")
        supported_exts = ('.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif')
        files = [
            os.path.join(source_path_or_url, f) 
            for f in os.listdir(source_path_or_url) 
            if f.lower().endswith(supported_exts)
        ]
        
        if not files:
            print(f"No supported receipt files found in '{source_path_or_url}'.")
            return
            
        print(f"Found {len(files)} files to analyze.\n")
        for file_path in files:
            print("=" * 60)
            print(f"Processing: {os.path.basename(file_path)}")
            print("=" * 60)
            analyze_receipt(file_path, query_fields)
            print("\n")
    else:
        analyze_receipt(source_path_or_url, query_fields)

def display_results(result, query_fields=None):
    """
    Extracts and displays key fields from the analyzed receipt model.
    """
    if not result.documents:
        print("No structured documents detected in the receipt scan.")
        return

    for idx, document in enumerate(result.documents):
        print(f"================ RECEIPT DETAILS ================")
        fields = document.fields
        if not fields:
            print("No key-value fields extracted.")
            continue

        # Merchant Information
        merchant_name = fields.get("MerchantName")
        if merchant_name:
            print(f"Merchant Name:  {merchant_name.value_string} (Confidence: {merchant_name.confidence:.2f})")
        
        merchant_address = fields.get("MerchantAddress")
        if merchant_address:
            print(f"Address:        {merchant_address.value_string}")
        
        merchant_phone = fields.get("MerchantPhoneNumber")
        if merchant_phone:
            print(f"Phone:          {merchant_phone.value_phone_number}")

        # Transaction Meta
        trans_date = fields.get("TransactionDate")
        if trans_date:
            print(f"Date:           {trans_date.value_date}")
        
        trans_time = fields.get("TransactionTime")
        if trans_time:
            print(f"Time:           {trans_time.value_time}")

        print("-" * 50)
        
        # Line Items
        items = fields.get("Items")
        if items and items.value_array:
            print("LINE ITEMS:")
            print(f"{'Qty':<5} | {'Description':<25} | {'Price':<10}")
            print("-" * 50)
            for item in items.value_array:
                item_fields = item.value_object
                qty = item_fields.get("Quantity")
                qty_val = qty.value_number if qty else 1
                
                desc = item_fields.get("Description")
                desc_val = desc.value_string if desc else "Unknown Item"
                
                total_price = item_fields.get("TotalPrice")
                price_val = f"{total_price.value_currency.amount:.2f}" if total_price and total_price.value_currency else "N/A"
                
                print(f"{qty_val:<5} | {desc_val[:25]:<25} | {price_val:<10}")
            print("-" * 50)

        # Financial Summary
        subtotal = fields.get("Subtotal")
        if subtotal and subtotal.value_currency:
            print(f"Subtotal:       {subtotal.value_currency.amount:.2f} {subtotal.value_currency.currency_code or ''}")
        
        tax = fields.get("TotalTax")
        if tax and tax.value_currency:
            print(f"Tax:            {tax.value_currency.amount:.2f} {tax.value_currency.currency_code or ''}")
        
        tip = fields.get("Tip")
        if tip and tip.value_currency:
            print(f"Tip:            {tip.value_currency.amount:.2f} {tip.value_currency.currency_code or ''}")
        
        total = fields.get("Total")
        if total and total.value_currency:
            print(f"TOTAL:          {total.value_currency.amount:.2f} {total.value_currency.currency_code or ''}")
        
        # Custom Query Fields Display
        if query_fields:
            print("-" * 50)
            print("CUSTOM QUERY FIELDS EXTRACTED:")
            for q_field in query_fields:
                val = fields.get(q_field)
                if val:
                    # Print raw content and confidence score
                    print(f"  {q_field:<15}: {val.content} (Confidence: {val.confidence:.2f})")
                else:
                    print(f"  {q_field:<15}: [Not Found]")

        print("=================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze receipts using Azure AI Document Intelligence.")
    
    # Source path/URL (defaulting to the remote sample)
    default_sample = "https://raw.githubusercontent.com/Azure/azure-sdk-for-python/main/sdk/formrecognizer/azure-ai-formrecognizer/tests/sample_forms/receipt/contoso-receipt.png"
    parser.add_argument(
        "source", 
        nargs="?", 
        default=default_sample,
        help="Path to local file, URL of a receipt, or directory containing multiple receipt files."
    )
    
    # Custom query fields
    parser.add_argument(
        "--query", "-q",
        nargs="+",
        help="List of custom fields to extract using Natural Language queries (e.g. -q ABN PaymentMethod Barcode)"
    )

    args = parser.parse_args()
    
    # Run the processor
    process_source(args.source, args.query)
