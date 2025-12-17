# Charge Name Mapping

**Purpose:** Map vendor invoice line descriptions → standardized charge types

## The Problem

Vendors use inconsistent descriptions for the same charges:
- "MONTHLY EQUIPMENT FEE", "CONTAINER RENTAL", "MONTHLY SVC" → all mean Monthly Service
- "FUEL SURCHARGE", "ENERGY FEE", "FSC" → all mean Fuel Surcharge

## The Solution

Pattern-based mapping using historical billing data as training:
1. Extract line items from invoice JSONs (what vendors write)
2. Match to billing_charges (how we categorized them)
3. Build `charge_type_map.csv` with vendor-specific patterns

---

## Folder Structure

```
Charge Name Mapping/
├── README.md                    # This file
├── sql/
│   └── charge_mapping_queries.sql   # All SQL queries
├── scripts/
│   ├── download_vendor_jsons.py     # Download JSONs from GCP
│   └── extract_line_items.py        # Parse JSONs, extract line items
├── config/
│   └── charge_type_map.csv          # The mapping table (output)
└── data/                            # Working data (gitignore)
    ├── vendor_md5s.csv
    ├── billing_charges_stratified.csv
    ├── invoice_extract_detail_*.csv
    └── json_by_vendor/
```

---

## Workflow

### Step 1: Identify Top Vendors

Run **Query 1** in `sql/charge_mapping_queries.sql`:
```sql
SELECT TOP 20 vendor_name, COUNT(DISTINCT billing_reference) as invoice_count...
```

Copy the vendor names for use in subsequent queries.

### Step 2: Check Dimension Spread

Run **Query 2** to see equipment types, service types, materials per vendor.
This tells you if the sample size is adequate.

### Step 3: Export MD5s for JSON Download

Run **Query 3**, export as `data/vendor_md5s.csv`

### Step 4: Download Invoice JSONs

```bash
cd "Charge Name Mapping"
python scripts/download_vendor_jsons.py data/vendor_md5s.csv --output-dir data/json_by_vendor
```

### Step 5: Extract Line Items

```bash
python scripts/extract_line_items.py data/json_by_vendor
```

Output: `invoice_extract_detail_YYYY-MM-DD.csv`

### Step 6: Export Billing Charges

Run **Query 4**, export as `data/billing_charges_stratified.csv`

### Step 7: Build Charge Type Map

Upload both files to Claude:
- `invoice_extract_detail_*.csv`
- `billing_charges_stratified.csv`

Claude joins on `billing_reference` = `invoice_number` and builds `charge_type_map.csv`

---

## Output: charge_type_map.csv

| Column | Description |
|--------|-------------|
| vendor_name | Vendor name (or DEFAULT for fallbacks) |
| invoice_pattern | Pattern to match in invoice line description |
| charge_type | Standardized charge type |
| priority | 1 = vendor-specific, 99 = default fallback |
| sample_count | Number of training examples |

### How Matching Works

```
Invoice: "FUEL SURCHARGE" from GFL
         ↓
Step 1: Check GFL + "FUEL SURCHARGE" → Fuel Surcharge Commercial ✓

Invoice: "MONTHLY SERVICE" from Unknown Vendor
         ↓
Step 2: Check DEFAULT + "MONTHLY" → Monthly Service Commercial ✓
```

Vendor-specific patterns (priority=1) are checked first.
Default patterns (priority=99) are fallbacks.

---

## Prerequisites

### Python packages
```bash
pip install pandas google-cloud-storage
```

### GCP Authentication
```bash
gcloud auth application-default login
gcloud config set project academic-torch-405913
```

---

## Key Schema Notes

- `billing_charges` is in `wasteology.new_ct` schema
- `sharepoint_gapi` is in `wasteology.dbo` schema
- `billing_reference` = vendor's invoice number (on the actual bill)
- `invoice_md5` = hash for GCP JSON lookup
- Join billing_charges to sharepoint on `billing_reference = invoice_number`

---

## Sample Size Guidelines

| Vendor Complexity | Invoices Needed |
|-------------------|-----------------|
| Simple (2-3 equipment types) | 30-50 |
| Medium (4-6 equipment types) | 50-100 |
| Complex (7+ equipment types) | 100-150 |

The stratified sample ensures coverage across equipment types and service types,
not just random invoices.

---

## Maintenance

When adding new vendors:
1. Run Query 1 to identify high-volume vendors not yet mapped
2. Follow the workflow above for those vendors
3. Append new patterns to `charge_type_map.csv`
4. Commit to GitHub

---

## Current State

| Metric | Value |
|--------|-------|
| Vendors mapped | 19 |
| Total patterns | ~1,350 |
| Target | Top 20 vendors at 95%+ match rate |

Last updated: 2025-12-17
