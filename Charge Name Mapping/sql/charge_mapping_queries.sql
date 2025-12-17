-- ============================================================================
-- CHARGE NAME MAPPING - DATA PULL QUERIES
-- ============================================================================
-- Purpose: Pull stratified sample of invoices for charge type mapping training
-- 
-- Workflow:
--   1. Run Query 1 (top vendors) - get your top 20 vendors by volume
--   2. Run Query 2 (diagnostic) - see dimension spread per vendor
--   3. Run Query 3 (MD5s) - export as vendor_md5s.csv for JSON download
--   4. Run Query 4 (billing charges) - export as billing_charges_stratified.csv
--   5. Download JSONs: python download_vendor_jsons.py vendor_md5s.csv
--   6. Extract line items: python extract_line_items.py json_by_vendor
--   7. Join and build map (Claude or join script)
--
-- Schema notes:
--   - billing_charges is in wasteology.new_ct schema
--   - sharepoint_gapi is in wasteology.dbo schema  
--   - billing_reference = vendor's invoice number (what's on the bill)
--   - invoice_md5 = hash for GCP JSON lookup
--
-- Last updated: 2025-12-17
-- ============================================================================


-- ============================================================================
-- QUERY 1: TOP 20 VENDORS BY INVOICE VOLUME
-- ============================================================================
-- Run this first to identify your top vendors.
-- Copy the vendor names for use in subsequent queries.

SELECT TOP 20 
    vendor_name, 
    COUNT(DISTINCT billing_reference) as invoice_count,
    COUNT(*) as line_count
FROM wasteology.new_ct.billing_charges
WHERE invoice_date >= '2025-01-01'
GROUP BY vendor_name
ORDER BY invoice_count DESC;


-- ============================================================================
-- QUERY 2: DIAGNOSTIC - Dimension spread per vendor
-- ============================================================================
-- Shows equipment types, service types, materials, and charge patterns per vendor.
-- Use this to understand complexity and verify sample size is adequate.
--
-- INSTRUCTIONS: Paste your top 20 vendor names into the IN clause below.

SELECT 
    vendor_name,
    COUNT(DISTINCT billing_reference) as total_invoices,
    COUNT(DISTINCT equipment_type) as equipment_types,
    COUNT(DISTINCT service_type) as service_types,
    COUNT(DISTINCT material) as materials,
    COUNT(DISTINCT charge_description) as unique_charges
FROM wasteology.new_ct.billing_charges
WHERE invoice_date >= '2025-01-01'
  AND vendor_name IN (
      -- PASTE YOUR TOP 20 VENDORS HERE
      'Vendor1',
      'Vendor2'
  )
GROUP BY vendor_name
ORDER BY total_invoices DESC;


-- ============================================================================
-- QUERY 3: GET MD5s FOR JSON DOWNLOAD
-- ============================================================================
-- Export as: vendor_md5s.csv
-- Then run: python download_vendor_jsons.py vendor_md5s.csv
--
-- Stratified sample: up to 10 invoices per vendor/equipment/service_type combo
-- This ensures coverage across all billing patterns.
--
-- INSTRUCTIONS: Paste your top 20 vendor names into the IN clause below.

WITH vendor_invoices AS (
    SELECT 
        bc.vendor_name,
        bc.billing_reference,
        bc.equipment_type,
        bc.service_type,
        bc.invoice_date,
        ROW_NUMBER() OVER (
            PARTITION BY bc.vendor_name, bc.equipment_type, bc.service_type 
            ORDER BY bc.invoice_date DESC
        ) as rn
    FROM wasteology.new_ct.billing_charges bc
    WHERE bc.invoice_date >= '2025-01-01'
      AND bc.billing_reference IS NOT NULL
      AND bc.billing_reference != ''
      AND bc.vendor_name IN (
          -- PASTE YOUR TOP 20 VENDORS HERE
          'Wasteology',
          'ANYTIME WASTE SYSTEMS',
          'Waste Management - National',
          'Rumpke',
          'GFL Environmental',
          'Republic Services',
          'UNIVERSAL WASTE SYSTEMS',
          'SmartTrash',
          'Robinson Waste Services-Utah',
          'GFL',
          'STANDARD WASTE SERVICES',
          'MERIDIAN WASTE',
          'Hamilton Alliance, Inc',
          'Waste Vision, LLC',
          'Boren Brothers LLC',
          'CASELLA WASTE SYSTEMS',
          'Flood Brothers',
          'Fusion Waste',
          'Priority Waste IN'
      )
),
stratified AS (
    SELECT DISTINCT vendor_name, billing_reference
    FROM vendor_invoices
    WHERE rn <= 10
)
SELECT DISTINCT
    s.vendor_name,
    s.billing_reference,
    sp.invoice_md5,
    sp.invoice_date
FROM stratified s
INNER JOIN wasteology.dbo.sharepoint_gapi sp 
    ON s.billing_reference = sp.invoice_number
WHERE sp.invoice_md5 IS NOT NULL
  AND sp.invoice_md5 != ''
ORDER BY s.vendor_name, sp.invoice_date DESC;


-- ============================================================================
-- QUERY 4: BILLING CHARGES FOR TRAINING (ANSWER KEY)
-- ============================================================================
-- Export as: billing_charges_stratified.csv
-- This is the "answer key" - how each charge was categorized.
-- Join to extracted invoice lines on billing_reference to build charge_type_map.
--
-- INSTRUCTIONS: Paste your top 20 vendor names into the IN clause below.

WITH vendor_invoices AS (
    SELECT 
        bc.vendor_name,
        bc.billing_reference,
        bc.equipment_type,
        bc.service_type,
        bc.invoice_date,
        ROW_NUMBER() OVER (
            PARTITION BY bc.vendor_name, bc.equipment_type, bc.service_type 
            ORDER BY bc.invoice_date DESC
        ) as rn
    FROM wasteology.new_ct.billing_charges bc
    WHERE bc.invoice_date >= '2025-01-01'
      AND bc.billing_reference IS NOT NULL
      AND bc.billing_reference != ''
      AND bc.vendor_name IN (
          -- PASTE YOUR TOP 20 VENDORS HERE
          'Wasteology',
          'ANYTIME WASTE SYSTEMS',
          'Waste Management - National',
          'Rumpke',
          'GFL Environmental',
          'Republic Services',
          'UNIVERSAL WASTE SYSTEMS',
          'SmartTrash',
          'Robinson Waste Services-Utah',
          'GFL',
          'STANDARD WASTE SERVICES',
          'MERIDIAN WASTE',
          'Hamilton Alliance, Inc',
          'Waste Vision, LLC',
          'Boren Brothers LLC',
          'CASELLA WASTE SYSTEMS',
          'Flood Brothers',
          'Fusion Waste',
          'Priority Waste IN'
      )
),
stratified_refs AS (
    SELECT DISTINCT vendor_name, billing_reference
    FROM vendor_invoices
    WHERE rn <= 10
)
SELECT 
    sp.invoice_md5,
    bc.vendor_name,
    bc.billing_reference,
    bc.invoice_date,
    bc.charge_description,
    bc.equipment_type,
    bc.service_type,
    bc.material,
    bc.service_id,
    bc.charge,
    bc.cost,
    bc.weight,
    bc.account_name,
    bc.location_name
FROM wasteology.new_ct.billing_charges bc
INNER JOIN stratified_refs sr 
    ON bc.billing_reference = sr.billing_reference
    AND bc.vendor_name = sr.vendor_name
LEFT JOIN wasteology.dbo.sharepoint_gapi sp
    ON bc.billing_reference = sp.invoice_number
ORDER BY bc.vendor_name, bc.billing_reference, bc.charge_description;


-- ============================================================================
-- QUERY 5: SAMPLE COUNT CHECK
-- ============================================================================
-- Run this to verify sample sizes and MD5 coverage before downloading JSONs.
--
-- INSTRUCTIONS: Paste your top 20 vendor names into the IN clause below.

WITH vendor_invoices AS (
    SELECT 
        bc.vendor_name,
        bc.billing_reference,
        bc.equipment_type,
        bc.service_type,
        bc.invoice_date,
        ROW_NUMBER() OVER (
            PARTITION BY bc.vendor_name, bc.equipment_type, bc.service_type 
            ORDER BY bc.invoice_date DESC
        ) as rn
    FROM wasteology.new_ct.billing_charges bc
    WHERE bc.invoice_date >= '2025-01-01'
      AND bc.billing_reference IS NOT NULL
      AND bc.billing_reference != ''
      AND bc.vendor_name IN (
          -- PASTE YOUR TOP 20 VENDORS HERE
          'Wasteology',
          'ANYTIME WASTE SYSTEMS',
          'Waste Management - National',
          'Rumpke',
          'GFL Environmental',
          'Republic Services',
          'UNIVERSAL WASTE SYSTEMS',
          'SmartTrash',
          'Robinson Waste Services-Utah',
          'GFL',
          'STANDARD WASTE SERVICES',
          'MERIDIAN WASTE',
          'Hamilton Alliance, Inc',
          'Waste Vision, LLC',
          'Boren Brothers LLC',
          'CASELLA WASTE SYSTEMS',
          'Flood Brothers',
          'Fusion Waste',
          'Priority Waste IN'
      )
),
stratified AS (
    SELECT DISTINCT vendor_name, billing_reference
    FROM vendor_invoices
    WHERE rn <= 10
)
SELECT 
    s.vendor_name,
    COUNT(DISTINCT s.billing_reference) as stratified_invoices,
    COUNT(DISTINCT sp.invoice_md5) as have_md5
FROM stratified s
LEFT JOIN wasteology.dbo.sharepoint_gapi sp 
    ON s.billing_reference = sp.invoice_number
GROUP BY s.vendor_name
ORDER BY stratified_invoices DESC;


-- ============================================================================
-- NOTES ON SAMPLE SIZE
-- ============================================================================
-- The stratified sample pulls up to 10 invoices per vendor/equipment/service_type.
-- 
-- To adjust sample size, change "rn <= 10" to:
--   rn <= 5   -> ~50 invoices per vendor (minimum)
--   rn <= 10  -> ~100 invoices per vendor (recommended)
--   rn <= 15  -> ~150 invoices per vendor (thorough)
--   rn <= 20  -> ~200 invoices per vendor (comprehensive)
--
-- Vendors with fewer equipment/service combinations will have fewer total invoices.
-- ============================================================================
