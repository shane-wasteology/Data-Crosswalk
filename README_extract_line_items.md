# Extract Invoice Line Items from Document AI JSONs

Extracts full invoice context (account, invoice #, line items with amounts) for matching against `billing_charges` to build `charge_type_map.csv`.

## Quick Start

```bash
# Run on a folder of JSONs (all vendors)
python extract_line_items.py "/path/to/json/folder"

# Filter to specific vendor
python extract_line_items.py "/path/to/json/folder" "Lawrence"
```

**⚠️ IMPORTANT: Always wrap paths with spaces in quotes!**

## Arguments

| Position | Required | Description |
|----------|----------|-------------|
| 1 | Yes | Path to folder containing JSON files |
| 2 | No | Vendor name filter (partial match, case-insensitive) |

## Examples

```bash
# Path with spaces - MUST use quotes
python extract_line_items.py "C:\Users\ShaneStClair\OneDrive - Wasteology Group\Flywheel\Crosswalk\Training\json"

# Filter to Lawrence invoices only
python extract_line_items.py "C:\path\to\jsons" "Lawrence"

# Filter to Boren Brothers
python extract_line_items.py ./jsons "Boren"
```

## Output Files

Creates 2-3 files in the **current working directory**:

| File | Contents |
|------|----------|
| `invoice_extract_detail_YYYY-MM-DD.csv` | Full line item details (for matching to billing_charges) |
| `invoice_extract_summary_YYYY-MM-DD.csv` | Aggregated by vendor/description |
| `invoice_extract_errors_YYYY-MM-DD.txt` | Any files that failed to parse |

## Detail File Columns

| Column | Description | Use For |
|--------|-------------|---------|
| json_md5 | Filename (matches invoice_md5 in sharepoint_gapi) | Joining to billing_charges |
| vendor_name | Supplier name from invoice | Filtering |
| account_number | Customer account # | Crosswalk matching |
| invoice_number | Invoice ID | Verification |
| invoice_date | Invoice date (YYYY-MM-DD) | Date filtering |
| location_code | Site/location identifier | Site matching |
| service_address | Service address | Site matching |
| line_description | Cleaned line item text | Building charge_type_map |
| **parsed_equipment** | Extracted equipment type (e.g., "30YD Roll Off", "42YD Compactor") | Multi-equipment matching |
| **parsed_material** | Extracted material/waste stream (e.g., "Scrap Metal", "OCC", "Trash") | Equipment differentiation |
| line_amount | Dollar amount | Rate comparison |
| line_quantity | Quantity (if present) | Unit rate calc |
| line_unit_price | Unit price (if present) | Rate comparison |
| service_date | Service period | Date matching |
| full_text | Raw line item text | Reference |

## Equipment Patterns Recognized

| Pattern | Normalized To |
|---------|---------------|
| 42YD COMPACTOR, 42 YARD COMPACTOR | 42YD Compactor |
| 30YD ROLL OFF, 30 YARD ROLL-OFF | 30YD Roll Off |
| SPLIT BODY, SPLIT BODY 28YD | Split Body Compactor 28YD |
| 4YD FRONT LOAD, 4 CU YD | 4 Yard Front Load |
| 96 GAL TOTER, 96 GALLON CART | 96 Gallon Toter |

## Material Patterns Recognized

| Pattern | Normalized To |
|---------|---------------|
| OCC, CARDBOARD, CORRUGATED | OCC |
| TRASH, MSW, SOLID WASTE | Trash |
| SCRAP METAL | Scrap Metal |
| RECYCLING, RECYCLE | Recycling |
| C&D, CONSTRUCTION, DEMOLITION | C&D |

## Workflow

1. Run script on vendor's JSONs
2. Pull billing_charges for same vendor/date range from database
3. Join on `json_md5 = invoice_md5` (or account + invoice_number)
4. Compare `line_description` → `charge_type` to build mapping
5. Upload both CSVs - Claude builds `charge_type_map.csv`

## Multi-Equipment Matching

When an account has multiple equipment types (e.g., 42YD Compactor + 30YD Compactor), use `parsed_equipment` to match to the correct service_id:

```
Invoice Line Item                          | parsed_equipment  | Matches service_id
-------------------------------------------|-------------------|-------------------
42YD COMPACTOR MONTHLY FEE                 | 42YD Compactor    | 73910
30YD COMPACTOR DISPOSAL - 2.34 TONS        | 30YD Compactor    | 73911
```

For accounts with same equipment but different materials (e.g., 30YD Compactor Trash vs OCC), use `parsed_material`:

```
Invoice Line Item                          | parsed_equipment  | parsed_material | service_id
-------------------------------------------|-------------------|-----------------|------------
30YD COMPACTOR TRASH DISPOSAL              | 30YD Compactor    | Trash           | 73912
30YD COMPACTOR OCC HAUL                    | 30YD Compactor    | OCC             | 73913
```

## Tips

- Script walks subfolders recursively
- Only processes `.json` files
- Vendor filter matches against `supplier_name` entity
- Summary file shows frequency + sample amounts for quick review
