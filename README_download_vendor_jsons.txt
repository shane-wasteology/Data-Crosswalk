# Download Invoice JSONs by Vendor

Pull ~150 JSONs from your top 20 vendors for building the charge_type_map.

## Quick Start

```bash
# Step 1: Run SQL in DataGrip, export to vendor_md5s.csv
# Step 2: Download JSONs
python download_vendor_jsons.py vendor_md5s.csv
```

## Full Workflow

### Step 1: Get invoice MD5s by vendor

Run `get_vendor_md5s.sql` in DataGrip:

```sql
-- Gets 150 recent invoices per vendor for top 20 vendors (~3,000 total)
```

Export results to: `vendor_md5s.csv`

Format:
```
vendor_name,invoice_md5,invoice_date
Lawrence Waste Services,abc123def456,2025-10-15
Lawrence Waste Services,789ghi012jkl,2025-10-10
Boren Brothers LLC,mno345pqr678,2025-10-12
```

### Step 2: Download JSONs from GCP

```bash
cd "C:\Users\ShaneStClair\OneDrive - Wasteology Group\Desktop\Deterministic Model"
python download_vendor_jsons.py vendor_md5s.csv
```

Output structure:
```
json_by_vendor/
├── Lawrence_Waste_Services/
│   ├── abc123def456.json
│   ├── 789ghi012jkl.json
│   └── ...
├── Boren_Brothers_LLC/
│   ├── mno345pqr678.json
│   └── ...
└── ...
```

### Step 3: Extract line items

```bash
# All vendors at once
python extract_line_items.py json_by_vendor

# Or one vendor at a time
python extract_line_items.py json_by_vendor "Lawrence"
```

## Prerequisites

### Python packages
```bash
pip install google-cloud-storage pandas
```

### GCP authentication (one-time)
```bash
gcloud auth login
gcloud config set project academic-torch-405913
gcloud auth application-default login
```

## Files

| File | Purpose |
|------|---------|
| `get_vendor_md5s.sql` | SQL query to get invoice MD5s by vendor |
| `download_vendor_jsons.py` | Downloads JSONs organized by vendor folder |
| `extract_line_items.py` | Extracts line items from JSONs |
| `vendor_md5s.csv` | Your export from DataGrip |

## Adjusting the sample size

Edit `get_vendor_md5s.sql`:

```sql
LIMIT 20       -- Number of vendors (line 9)
WHERE rn <= 150 -- Invoices per vendor (line 22)
```

| Vendors | Per Vendor | Total JSONs |
|---------|------------|-------------|
| 20 | 150 | 3,000 |
| 10 | 150 | 1,500 |
| 20 | 75 | 1,500 |

## Troubleshooting

| Error | Solution |
|-------|----------|
| `credentials were not found` | Run `gcloud auth application-default login` |
| `Not found` for all files | Check bucket name, run `gcloud config set project academic-torch-405913` |
| `Permission denied` | Re-run `gcloud auth login` |
| Path with spaces error | Wrap path in quotes |
