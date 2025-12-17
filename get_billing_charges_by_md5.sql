-- Pull billing_charges for invoices by MD5
-- Use the same vendor_md5s.csv as input - paste MD5s or use a temp table

-- Option 1: If you have the MD5 list in a temp table or want to join to your export
SELECT 
    sp.invoice_md5,
    bc.vendor_name,
    bc.billing_reference as invoice_number,
    bc.invoice_date,
    bc.account_name,
    bc.location_name,
    bc.charge_description,
    bc.equipment_type,
    bc.material,
    bc.service_type,
    bc.price,
    bc.cost,
    bc.weight,
    bc.service_id
FROM wasteology.new_ct.billing_charges bc
INNER JOIN wasteology.dbo.sharepoint_gapi sp 
    ON bc.billing_reference = sp.invoice_number
    -- NOTE: No vendor_name join - names differ between tables
WHERE sp.invoice_md5 IN (
    -- Paste your MD5s here, or use a subquery
    'c6c666dbe16f8a05446a0b7d91846d09',
    '605eed7c0db43e49f3cf8eb7fced96fd'
    -- ... etc
)
ORDER BY sp.invoice_md5, bc.charge_description


-- Option 2: Pull for the same top 20 vendors / 150 invoices each
-- (matches get_vendor_md5s.sql)
;WITH top_vendors AS (
    SELECT TOP 20 
        vendor_name,
        COUNT(DISTINCT billing_reference) as inv_count
    FROM wasteology.new_ct.billing_charges
    WHERE invoice_date BETWEEN '2025-01-01' AND '2025-12-31'
    GROUP BY vendor_name
    ORDER BY COUNT(DISTINCT billing_reference) DESC
),
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
ranked AS (
    SELECT 
        im.vendor_name,
        im.invoice_md5,
        im.invoice_date,
        ROW_NUMBER() OVER (PARTITION BY im.vendor_name ORDER BY im.invoice_date DESC) as rn
    FROM invoice_md5s im
    INNER JOIN top_vendors tv ON im.vendor_name = tv.vendor_name
),
target_md5s AS (
    SELECT invoice_md5
    FROM ranked
    WHERE rn <= 150
)
SELECT 
    sp.invoice_md5,
    bc.vendor_name,
    bc.billing_reference as invoice_number,
    bc.invoice_date,
    bc.account_name,
    bc.location_name,
    bc.charge_description,
    bc.equipment_type,
    bc.material,
    bc.service_type,
    bc.price,
    bc.cost,
    bc.weight,
    bc.service_id
FROM wasteology.new_ct.billing_charges bc
INNER JOIN wasteology.dbo.sharepoint_gapi sp 
    ON bc.billing_reference = sp.invoice_number
INNER JOIN target_md5s t ON sp.invoice_md5 = t.invoice_md5
ORDER BY bc.vendor_name, sp.invoice_md5, bc.charge_description
