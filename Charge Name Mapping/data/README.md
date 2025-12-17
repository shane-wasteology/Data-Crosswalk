# Data Folder

This folder contains working data files generated during the charge mapping workflow.
These files are gitignored (too large / regenerated locally).

## Expected Files

| File | Source | Purpose |
|------|--------|---------|
| `vendor_md5s.csv` | Query 3 export | Input for JSON download |
| `billing_charges_stratified.csv` | Query 4 export | Training data (answer key) |
| `invoice_extract_detail_*.csv` | extract_line_items.py | Extracted invoice lines |
| `json_by_vendor/` | download_vendor_jsons.py | Downloaded JSON files |

## Workflow

1. Run SQL queries, export CSVs here
2. Run download script: `python scripts/download_vendor_jsons.py data/vendor_md5s.csv --output-dir data/json_by_vendor`
3. Run extract script: `python scripts/extract_line_items.py data/json_by_vendor`
4. Upload extract + billing_charges to Claude for joining
