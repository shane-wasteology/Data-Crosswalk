#!/usr/bin/env python3
"""
Join Invoice Extracts to Billing Charges

Matches invoice line items from Document AI extraction to billing_charges
records to build the charge_type_map.

Usage:
    python join_invoice_billing.py invoice_extract.csv billing_charges.csv

Output:
    invoice_billing_joined_YYYY-MM-DD.csv
"""

import sys
import pandas as pd
from datetime import datetime


def join_invoice_billing(invoice_file, billing_file, output_file=None):
    """Join invoice extracts to billing charges."""
    
    print("=" * 60)
    print("JOIN INVOICE EXTRACTS TO BILLING CHARGES")
    print("=" * 60)
    
    # Load files
    invoice = pd.read_csv(invoice_file)
    billing = pd.read_csv(billing_file)
    
    print(f"Invoice extract: {len(invoice):,} rows")
    print(f"Billing charges: {len(billing):,} rows")
    
    # Standardize column names
    # Invoice extract uses: json_md5, invoice_number
    # Billing charges uses: invoice_md5, billing_reference or invoice_number
    
    if 'billing_reference' in billing.columns:
        billing = billing.rename(columns={'billing_reference': 'invoice_number'})
    
    # Find common invoice numbers
    invoice_nums = set(invoice['invoice_number'].dropna().astype(str).unique())
    billing_nums = set(billing['invoice_number'].dropna().astype(str).unique())
    common = invoice_nums & billing_nums
    
    print(f"\nInvoice numbers in extract: {len(invoice_nums):,}")
    print(f"Invoice numbers in billing: {len(billing_nums):,}")
    print(f"Common invoice numbers: {len(common):,}")
    
    if not common:
        print("\nNo matching invoice numbers found!")
        print("Check that invoice_number/billing_reference columns match")
        return None
    
    # Filter to common invoices
    invoice_filt = invoice[invoice['invoice_number'].astype(str).isin(common)]
    billing_filt = billing[billing['invoice_number'].astype(str).isin(common)]
    
    print(f"\nFiltered invoice rows: {len(invoice_filt):,}")
    print(f"Filtered billing rows: {len(billing_filt):,}")
    
    # Join on invoice_number with amount matching
    joined_rows = []
    
    invoice_grouped = invoice_filt.groupby('invoice_number')
    billing_grouped = billing_filt.groupby('invoice_number')
    
    for inv_num in common:
        if inv_num not in invoice_grouped.groups or inv_num not in billing_grouped.groups:
            continue
        
        inv_lines = invoice_grouped.get_group(inv_num)
        bill_lines = billing_grouped.get_group(inv_num)
        
        for _, inv_row in inv_lines.iterrows():
            inv_amount = inv_row.get('line_amount')
            
            # Find best matching billing row by amount
            best_match = None
            best_score = 0
            
            for _, bill_row in bill_lines.iterrows():
                bill_amount = bill_row.get('cost') or bill_row.get('price')
                score = 0
                
                # Amount match scoring
                if inv_amount and bill_amount:
                    try:
                        if abs(float(inv_amount) - float(bill_amount)) < 0.02:
                            score = 10
                        elif abs(float(inv_amount) - float(bill_amount)) < 1.00:
                            score = 5
                    except:
                        pass
                
                if score > best_score:
                    best_score = score
                    best_match = bill_row
            
            if best_match is not None and best_score >= 5:
                joined_rows.append({
                    'invoice_number': inv_num,
                    'vendor_name': inv_row.get('vendor_name', ''),
                    'billing_vendor': best_match.get('vendor_name', ''),
                    'invoice_line_description': inv_row.get('line_description', ''),
                    'parsed_equipment': inv_row.get('parsed_equipment', ''),
                    'parsed_material': inv_row.get('parsed_material', ''),
                    'invoice_amount': inv_amount,
                    'billing_charge_description': best_match.get('charge_description', ''),
                    'billing_equipment_type': best_match.get('equipment_type', ''),
                    'billing_material': best_match.get('material', ''),
                    'billing_amount': best_match.get('cost') or best_match.get('price'),
                    'billing_service_id': best_match.get('service_id', ''),
                    'billing_service_type': best_match.get('service_type', ''),
                })
    
    print(f"\nJoined rows: {len(joined_rows):,}")
    
    if not joined_rows:
        print("No rows could be joined!")
        return None
    
    # Create output
    joined_df = pd.DataFrame(joined_rows)
    
    if output_file is None:
        timestamp = datetime.now().strftime('%Y-%m-%d')
        output_file = f"invoice_billing_joined_{timestamp}.csv"
    
    joined_df.to_csv(output_file, index=False)
    print(f"Wrote {len(joined_df):,} rows to {output_file}")
    
    # Summary by charge type
    print("\n" + "=" * 60)
    print("CHARGE TYPE MAPPING SUMMARY")
    print("=" * 60)
    
    mapping = joined_df.groupby(['invoice_line_description', 'billing_charge_description']).size()
    mapping = mapping.sort_values(ascending=False)
    
    print("\nTop 20 invoice → billing mappings:")
    for (inv_desc, bill_desc), count in mapping.head(20).items():
        print(f"  {count:4d} | {inv_desc[:40]:<40} → {bill_desc}")
    
    return joined_df


def main():
    if len(sys.argv) < 3:
        print("Usage: python join_invoice_billing.py invoice_extract.csv billing_charges.csv")
        sys.exit(1)
    
    invoice_file = sys.argv[1]
    billing_file = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else None
    
    join_invoice_billing(invoice_file, billing_file, output_file)


if __name__ == '__main__':
    main()
