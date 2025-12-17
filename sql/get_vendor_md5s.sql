-- Get invoice MD5s for top 20 vendors (150 invoices each = ~3,000 total)
-- Run this in DataGrip, export to vendor_md5s.csv

-- Step 1: Get top 20 vendors by invoice count
WITH top_vendors AS (
    SELECT TOP 20 
        vendor_name,
        COUNT(DISTINCT billing_reference) as inv_count
    FROM wasteology.new_ct.billing_charges
    WHERE invoice_date BETWEEN '2025-01-01' AND '2025-12-31'
    GROUP BY vendor_name
    ORDER BY COUNT(DISTINCT billing_reference) DESC
),

-- Step 2: Get MD5s from sharepoint_gapi joined to billing_charges
-- NOTE: Join only on invoice_number (vendor names differ between tables)
invoice_md5s AS (
    SELECT DISTINCT
        bc.vendor_name,
        sp.invoice_md5,
        bc.invoice_date
    FROM wasteology.new_ct.billing_charges bc
    INNER JOIN wasteology.dbo.sharepoint_gapi sp 
        ON bc.billing_reference = sp.invoice_number
    WHERE sp.invoice_md5 IS NOT NULL
      AND sp.invoice_md5 != ''
),

-- Step 3: Rank and filter to 150 per vendor
ranked AS (
    SELECT 
        im.vendor_name,
        im.invoice_md5,
        im.invoice_date,
        ROW_NUMBER() OVER (PARTITION BY im.vendor_name ORDER BY im.invoice_date DESC) as rn
    FROM invoice_md5s im
    INNER JOIN top_vendors tv ON im.vendor_name = tv.vendor_name
)

SELECT 
    vendor_name,
    invoice_md5,
    invoice_date
FROM ranked
WHERE rn <= 150
ORDER BY vendor_name, invoice_date DESC
