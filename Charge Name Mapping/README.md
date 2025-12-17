# Charge Name Mapping

Build the mapping from vendor invoice line item descriptions to Wasteology charge types.

## Overview

Vendors use inconsistent descriptions on invoices ("MONTHLY EQUIPMENT FEE", "CONTAINER SVC", "RENTAL - 30YD"). 
This workflow extracts those descriptions from Document AI JSONs and matches them to how we billed them in `billing_charges`, 
creating a lookup table for the validation pipeline.

## Current State

| Level | Charge Types | Match Rate |
|-------|--------------|------------|
| Service Level | 85 | 90% |
| Invoice Level | 2 | 0% (fuel surcharge needs work) |
| WG Internal | 5 | 85% |

## Workflow

### Step 1: Get invoice MD5s

Run `get_vendor_md5s.sql` in DataGrip → Export to `vendor_md5s.csv`

Gets 150 recent invoices per vendor for top 20 vendors (~3,000 total).

### Step 2: Download JSONs from GCP
```bash
python download_vendor_jsons.py vendor_md5s.csv
```

Creates `json_by_vendor/` with subfolders per vendor.

### Step 3: Extract line items
```bash
python extract_line_items.py json_by_vendor
```

Creates `invoice_extract_detail_YYYY-MM-DD.csv` with all line items.

### Step 4: Pull billing charges

Run the companion query to get billing_charges for the same invoices.
Export to `billing_charges.csv`.

### Step 5: Join and analyze
```bash
python join_invoice_billing.py invoice_extract_detail.csv billing_charges.csv
```

Creates `invoice_billing_joined_YYYY-MM-DD.csv` showing:
- Invoice line description → Billing charge description
- Equipment/material mappings
- Amount matches

### Step 6: Build charge_type_map.csv

From the joined data, create patterns:
```csv
vendor_name,invoice_pattern,charge_type,service_type,priority
*,MONTHLY.*FEE,Monthly Service Commercial,Recurring,1
*,DISPOSAL,Disposal Charge,On Call,1
Lawrence Waste,HAUL,Empty & Return,On Call,2
```

## Files

| File | Purpose |
|------|---------|
| `get_vendor_md5s.sql` | SQL to get invoice MD5s by vendor |
| `download_vendor_jsons.py` | Download JSONs from GCP |
| `extract_line_items.py` | Parse Document AI JSONs |
| `join_invoice_billing.py` | Match invoice→billing |
| `charge_type_map.csv` | Pattern lookup table |

## Prerequisites
```bash
pip install google-cloud-storage pandas
gcloud auth application-default login
gcloud config set project academic-torch-405913
```

## Schema Notes

- `billing_charges` is in `wasteology.new_ct` schema
- `sharepoint_gapi` uses `invoice_md5` field (not `md5`)
- Join billing_charges to sharepoint_gapi on `billing_reference = invoice_number` only (vendor names differ)
