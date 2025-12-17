#!/usr/bin/env python3
"""
Join Extracted Invoice Line Items with Billing Charges

Joins the output from extract_line_items.py with billing_charges export
to create training data for charge_type_map.

Usage:
    python join_invoice_billing.py invoice_extract_detail.csv billing_charges.csv

Output:
    invoice_billing_joined_YYYY-MM-DD.csv - Matched records showing invoice text vs billed charge_type
    invoice_billing_unmatched_YYYY-MM-DD.csv - Invoice lines that didn't match billing_charges

This helps you see:
    - "MONTHLY EQUIPMENT FEE" on invoice → "Monthly Service Commercial" in billing
    - $811.00 on invoice → $811.00 in billing (rate match)
"""

import os
import sys
import pandas as pd
from datetime import datetime
import re


def clean_for_matching(text):
    """Normalize text for fuzzy matching."""
    if pd.isna(text):
        return ""
    text = str(text).upper().strip()
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text


def extract_amount(value):
    """Extract numeric amount from various formats."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    # Try to extract number from string
    match = re.search(r'[\d,]+\.?\d*', str(value).replace(',', ''))
    if match:
        try:
            return float(match.group())
        except:
            return None
    return None


def join_invoice_billing(invoice_file, billing_file, output_prefix="invoice_billing"):
    """
    Join extracted invoice line items with billing_charges.
    
    Join keys:
        - invoice_md5 (primary)
        - Fallback: vendor_name + invoice_number + approximate amount matching
    """
    
    print("=" * 60)
    print("JOIN INVOICE EXTRACTS WITH BILLING CHARGES")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    # Load files
    print(f"\nLoading {invoice_file}...")
    inv_df = pd.read_csv(invoice_file)
    print(f"  {len(inv_df)} invoice line items")
    
    print(f"Loading {billing_file}...")
    bill_df = pd.read_csv(billing_file)
    print(f"  {len(bill_df)} billing charge records")
    
    # Standardize column names (handle variations)
    inv_df.columns = [c.lower().strip() for c in inv_df.columns]
    bill_df.columns = [c.lower().strip() for c in bill_df.columns]
    
    # Ensure we have the join key
    if 'json_md5' in inv_df.columns:
        inv_df['invoice_md5'] = inv_df['json_md5']
    if 'invoice_md5' not in inv_df.columns:
        print("ERROR: invoice file missing json_md5 or invoice_md5 column")
        return
    if 'invoice_md5' not in bill_df.columns:
        print("ERROR: billing file missing invoice_md5 column")
        print("  Make sure you ran get_billing_charges_by_md5.sql")
        return
    
    # Clean MD5s
    inv_df['invoice_md5'] = inv_df['invoice_md5'].astype(str).str.strip().str.lower()
    bill_df['invoice_md5'] = bill_df['invoice_md5'].astype(str).str.strip().str.lower()
    
    # Extract amounts for matching
    if 'line_amount' in inv_df.columns:
        inv_df['inv_amount'] = inv_df['line_amount'].apply(extract_amount)
    elif 'amount' in inv_df.columns:
        inv_df['inv_amount'] = inv_df['amount'].apply(extract_amount)
    else:
        inv_df['inv_amount'] = None
    
    if 'cost' in bill_df.columns:
        bill_df['bill_amount'] = bill_df['cost'].apply(extract_amount)
    elif 'price' in bill_df.columns:
        bill_df['bill_amount'] = bill_df['price'].apply(extract_amount)
    else:
        bill_df['bill_amount'] = None
    
    # Normalize descriptions
    if 'line_description' in inv_df.columns:
        inv_df['inv_desc_clean'] = inv_df['line_description'].apply(clean_for_matching)
    elif 'description' in inv_df.columns:
        inv_df['inv_desc_clean'] = inv_df['description'].apply(clean_for_matching)
    
    if 'charge_description' in bill_df.columns:
        bill_df['bill_desc_clean'] = bill_df['charge_description'].apply(clean_for_matching)
    
    print(f"\nInvoice MD5s: {inv_df['invoice_md5'].nunique()}")
    print(f"Billing MD5s: {bill_df['invoice_md5'].nunique()}")
    
    # Find common MD5s
    common_md5s = set(inv_df['invoice_md5']) & set(bill_df['invoice_md5'])
    print(f"Common MD5s: {len(common_md5s)}")
    
    if len(common_md5s) == 0:
        print("\nWARNING: No matching MD5s found!")
        print("Check that both files are for the same invoices.")
        print(f"\nSample invoice MD5s: {inv_df['invoice_md5'].head(3).tolist()}")
        print(f"Sample billing MD5s: {bill_df['invoice_md5'].head(3).tolist()}")
        return
    
    # Join on MD5
    # For each invoice line item, find billing charges with same MD5
    joined_rows = []
    unmatched_rows = []
    
    for md5 in common_md5s:
        inv_lines = inv_df[inv_df['invoice_md5'] == md5]
        bill_lines = bill_df[bill_df['invoice_md5'] == md5]
        
        for _, inv_row in inv_lines.iterrows():
            inv_amount = inv_row.get('inv_amount')
            inv_desc = inv_row.get('inv_desc_clean', '')
            
            # Try to find matching billing line
            # Strategy: match by amount (within tolerance) or description similarity
            best_match = None
            best_score = 0
            
            for _, bill_row in bill_lines.iterrows():
                bill_amount = bill_row.get('bill_amount')
                bill_desc = bill_row.get('bill_desc_clean', '')
                
                score = 0
                
                # Amount match (within $0.02)
                if inv_amount and bill_amount:
                    if abs(inv_amount - bill_amount) < 0.02:
                        score += 10
                    elif abs(inv_amount - bill_amount) < 1.00:
                        score += 5
                
                # Description word overlap
                if inv_desc and bill_desc:
                    inv_words = set(inv_desc.split())
                    bill_words = set(bill_desc.split())
                    overlap = len(inv_words & bill_words)
                    score += overlap
                
                if score > best_score:
                    best_score = score
                    best_match = bill_row
            
            # Build output row
            row = {
                'invoice_md5': md5,
                'vendor_name': inv_row.get('vendor_name', ''),
                'account_number': inv_row.get('account_number', ''),
                'invoice_date': inv_row.get('invoice_date', ''),
                'invoice_line_description': inv_row.get('line_description', inv_row.get('description', '')),
                'parsed_equipment': inv_row.get('parsed_equipment', ''),
                'parsed_material': inv_row.get('parsed_material', ''),
                'invoice_amount': inv_amount,
            }
            
            if best_match is not None and best_score >= 5:
                row['billing_charge_description'] = best_match.get('charge_description', '')
                row['billing_equipment_type'] = best_match.get('equipment_type', '')
                row['billing_material'] = best_match.get('material', '')
                row['billing_service_type'] = best_match.get('service_type', '')
                row['billing_amount'] = best_match.get('bill_amount')
                row['billing_service_id'] = best_match.get('service_id', '')
                row['match_score'] = best_score
                row['amount_variance'] = (inv_amount - best_match.get('bill_amount', 0)) if inv_amount else None
                joined_rows.append(row)
            else:
                row['match_score'] = best_score
                row['note'] = 'No confident match found'
                unmatched_rows.append(row)
    
    # Also add invoice lines for MD5s not in billing
    missing_md5s = set(inv_df['invoice_md5']) - common_md5s
    for md5 in missing_md5s:
        inv_lines = inv_df[inv_df['invoice_md5'] == md5]
        for _, inv_row in inv_lines.iterrows():
            row = {
                'invoice_md5': md5,
                'vendor_name': inv_row.get('vendor_name', ''),
                'account_number': inv_row.get('account_number', ''),
                'invoice_date': inv_row.get('invoice_date', ''),
                'invoice_line_description': inv_row.get('line_description', inv_row.get('description', '')),
                'parsed_equipment': inv_row.get('parsed_equipment', ''),
                'parsed_material': inv_row.get('parsed_material', ''),
                'invoice_amount': inv_row.get('inv_amount'),
                'match_score': 0,
                'note': 'MD5 not found in billing_charges'
            }
            unmatched_rows.append(row)
    
    # Save results
    timestamp = datetime.now().strftime('%Y-%m-%d')
    
    if joined_rows:
        joined_df = pd.DataFrame(joined_rows)
        joined_file = f"{output_prefix}_joined_{timestamp}.csv"
        joined_df.to_csv(joined_file, index=False)
        print(f"\n✅ Wrote {len(joined_df)} matched rows to {joined_file}")
        
        # Summary stats
        print(f"\nMatched summary:")
        print(f"  Unique vendors: {joined_df['vendor_name'].nunique()}")
        print(f"  Unique MD5s: {joined_df['invoice_md5'].nunique()}")
        if 'amount_variance' in joined_df.columns:
            exact_match = (joined_df['amount_variance'].abs() < 0.02).sum()
            print(f"  Exact amount matches: {exact_match}/{len(joined_df)}")
    
    if unmatched_rows:
        unmatched_df = pd.DataFrame(unmatched_rows)
        unmatched_file = f"{output_prefix}_unmatched_{timestamp}.csv"
        unmatched_df.to_csv(unmatched_file, index=False)
        print(f"⚠️  Wrote {len(unmatched_df)} unmatched rows to {unmatched_file}")
    
    # Show sample of charge type mappings
    if joined_rows:
        print("\n" + "=" * 60)
        print("SAMPLE CHARGE TYPE MAPPINGS (for charge_type_map)")
        print("=" * 60)
        joined_df = pd.DataFrame(joined_rows)
        
        # Group by invoice description → billing description
        mapping = joined_df.groupby(['invoice_line_description', 'billing_charge_description']).size().reset_index(name='count')
        mapping = mapping.sort_values('count', ascending=False).head(20)
        
        print(f"\n{'Invoice Description':<45} → {'Billing Charge Type':<35} Count")
        print("-" * 90)
        for _, row in mapping.iterrows():
            inv = row['invoice_line_description'][:44]
            bill = row['billing_charge_description'][:34]
            print(f"{inv:<45} → {bill:<35} {row['count']}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python join_invoice_billing.py <invoice_extract.csv> <billing_charges.csv>")
        print("\nExample:")
        print("  python join_invoice_billing.py invoice_extract_detail_2025-12-16.csv billing_charges.csv")
        print("\nFiles needed:")
        print("  1. invoice_extract_detail_*.csv - Output from extract_line_items.py")
        print("  2. billing_charges.csv - Export from get_billing_charges_by_md5.sql")
        sys.exit(1)
    
    invoice_file = sys.argv[1]
    billing_file = sys.argv[2]
    
    if not os.path.exists(invoice_file):
        print(f"ERROR: Invoice file not found: {invoice_file}")
        sys.exit(1)
    if not os.path.exists(billing_file):
        print(f"ERROR: Billing file not found: {billing_file}")
        sys.exit(1)
    
    join_invoice_billing(invoice_file, billing_file)


if __name__ == '__main__':
    main()
