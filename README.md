# Getting Started with Azure AI Document Intelligence for Receipt Scanning

Azure AI Document Intelligence (formerly Form Recognizer) is an AI service that uses machine learning models to extract text, key-value pairs, tables, and structures from documents. It includes a **Prebuilt Receipt Model** designed specifically to extract fields from sales receipts without needing to train custom models.

This guide helps you set up Azure, test receipt extraction without code, and run a Python script to scan receipts programmatically.

---

## 1. Setup Your Azure Resource

To use the service, you need an Azure account and a Document Intelligence resource.

1. **Sign in/Sign up**: Go to the [Azure Portal](https://portal.azure.com/).
2. **Create a Resource**:
   - Search for **Document Intelligence** in the marketplace.
   - Click **Create**.
3. **Configure Resource**:
   - Choose/create a **Resource Group**.
   - Select a region (e.g., `East US` or your local region).
   - Enter a unique **Name** for your resource.
   - For the pricing tier, select **Free (F0)** if available (great for testing) or **Standard (S1)**.
4. **Get Keys and Endpoint**:
   - Once the resource is deployed, navigate to it.
   - On the left sidebar under **Resource Management**, click **Keys and Endpoint**.
   - Copy **KEY 1** (or KEY 2) and the **Endpoint** URL.

---

## 2. No-Code Testing: Azure Document Intelligence Studio

Before writing code, you can test the models visually:

1. Open the [Azure AI Document Intelligence Studio](https://documentintelligence.ai.azure.com/).
2. Scroll to the **Prebuilt models** section and select **Receipts**.
3. Select your Azure subscription, resource, and pricing tier to configure the workspace.
4. Upload an image of a receipt or choose one of the provided samples.
5. Click **Run analysis** (or **Analyze**) to view the extracted fields visually on the right side and inspect the raw JSON output.

---

## 3. Python SDK Quickstart

We have created a script [analyze_receipt.py](file:///c:/Users/Pavan%20Sachi/work/personal/projects/antigravity/bill-scans/analyze_receipt.py) in this workspace. Follow these steps to run it:

### Setup Your Environment

It is recommended to run Python scripts inside a virtual environment to avoid polluting global python packages:

1. Open your terminal in the `bill-scans` folder.
2. Initialize and activate a virtual environment:
   ```powershell
   # Create environment
   python -m venv .venv

   # Activate environment (Windows PowerShell)
   .venv\Scripts\Activate.ps1
   ```
3. Install the required client libraries:
   ```powershell
   .venv\Scripts\pip install azure-ai-documentintelligence azure-core
   ```

### Run the Script

1. Set your Endpoint and Key as environment variables in your terminal:
   ```powershell
   $env:AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT="https://your-resource-name.cognitiveservices.azure.com/"
   $env:AZURE_DOCUMENT_INTELLIGENCE_KEY="your-api-key-here"
   ```
2. Run the script with a sample online receipt:
   ```powershell
   .venv\Scripts\python analyze_receipt.py
   ```
3. Run the script with a local receipt scan:
   ```powershell
   .venv\Scripts\python analyze_receipt.py C:\path\to\your\receipt.jpg
   ```

---

## Extracted Fields Reference

The `prebuilt-receipt` model extracts:
- **Merchant Details**: `MerchantName`, `MerchantAddress`, `MerchantPhoneNumber`
- **Transaction Details**: `TransactionDate`, `TransactionTime`
- **Line Items**: An array of `Items` where each item has `Description`, `Quantity`, `UnitPrice`, and `TotalPrice`.
- **Financial Totals**: `Subtotal`, `TotalTax`, `Tip`, and `Total`.
