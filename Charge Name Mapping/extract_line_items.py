#!/usr/bin/env python3
"""
Extract Invoice Line Items from Document AI JSONs

Extracts full invoice context (account, invoice #, line items with amounts) 
for matching against billing_charges to build charge_type_map.csv.

Usage:
    python extract_line_items.py "/path/to/json/folder"
    python extract_line_items.py "/path/to/json/folder" "Lawrence"

Output:
    invoice_extract_detail_YYYY-MM-DD.csv   - Full line item details
    invoice_extract_summary_YYYY-MM-DD.csv  - Aggregated by vendor/description
"""

import os
import sys
import json
import re
import hashlib
from collections import defaultdict
from datetime import datetime
import csv


# Equipment patterns - order matters (more specific first)
EQUIPMENT_PATTERNS = [
    (r'\b(\d+)\s*YA?RD\s*(COMPACTOR|COMP)\b', lambda m: f"{m.group(1)}YD COMPACTOR"),
    (r'\b(\d+)\s*YA?RD\s*(ROLL.?OFF|RO)\b', lambda m: f"{m.group(1)}YD ROLL OFF"),
    (r'\b(\d+)\s*YA?RD\s*(FRONT.?LOAD|FL)\b', lambda m: f"{m.group(1)}YD FRONT LOAD"),
    (r'\b(\d+)\s*YA?RD\s*(REAR.?LOAD|RL)\b', lambda m: f"{m.group(1)}YD REAR LOAD"),
    (r'\b(\d+)\s*YA?RD\b', lambda m: f"{m.group(1)}YD"),
    (r'\bCOMPACTOR\b', lambda m: "COMPACTOR"),
    (r'\bROLL.?OFF\b', lambda m: "ROLL OFF"),
    (r'\bFRONT.?LOAD\b', lambda m: "FRONT LOAD"),
    (r'\bREAR.?LOAD\b', lambda m: "REAR LOAD"),
    (r'\b(\d+)\s*GAL(LON)?\b', lambda m: f"{m.group(1)}GAL"),
    (r'\b(\d+)\s*CU(BIC)?\s*YD\b', lambda m: f"{m.group(1)}YD"),
]

# Material patterns
MATERIAL_PATTERNS = [
    (r'\bCARDBOARD|OCC\b', 'Cardboard'),
    (r'\bPAPER\b', 'Paper'),
    (r'\bPLASTIC|HDPE|PET\b', 'Plastic'),
    (r'\bMETAL|SCRAP\s*METAL|ALUMINUM\b', 'Metal'),
    (r'\bGLASS\b', 'Glass'),
    (r'\bWOOD|PALLETS?\b', 'Wood'),
    (r'\bORGANIC|FOOD\s*WASTE|COMPOST\b', 'Organic'),
    (r'\bE-?WASTE|ELECTRONIC\b', 'E-Waste'),
    (r'\bC&D|CONSTRUCTION|DEMO(LITION)?\b', 'C&D'),
    (r'\bMSW|TRASH|GARBAGE|REFUSE\b', 'MSW'),
    (r'\bRECYCL(E|ING|ABLES?)\b', 'Recycling'),
]


def extract_equipment_from_description(text):
    """Extract equipment type from description text."""
    if not text:
        return None
    text_upper = text.upper()
    for pattern, handler in EQUIPMENT_PATTERNS:
        match = re.search(pattern, text_upper)
        if match:
            return handler(match)
    return None


def extract_material_from_description(text):
    """Extract material type from description text."""
    if not text:
        return None
    text_upper = text.upper()
    for pattern, material in MATERIAL_PATTERNS:
        if re.search(pattern, text_upper):
            return material
    return None


def clean_description(text):
    """Clean up a line item description."""
    if not text:
        return ""
    # Remove date patterns
    text = re.sub(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}', '', text)
    # Remove dollar amounts
    text = re.sub(r'\$?\d+\.\d{2}\b', '', text)
    # Remove standalone numbers
    text = re.sub(r'\b\d+\.\d+\b', '', text)
    text = re.sub(r'\s+\d+\s*$', '', text)
    # Clean whitespace
    text = ' '.join(text.split())
    text = text.strip(' -')
    return text


def extract_entities(data):
    """Extract all entities from Document AI JSON."""
    if isinstance(data, dict):
        if 'entities' in data:
            return data['entities']
        if 'document' in data and 'entities' in data['document']:
            return data['document']['entities']
    return []


def parse_money_value(prop):
    """Extract dollar amount from a property."""
    nv = prop.get('normalizedValue', {})
    if 'moneyValue' in nv:
        mv = nv['moneyValue']
        units = int(mv.get('units', 0) or 0)
        nanos = int(mv.get('nanos', 0) or 0)
        return units + nanos / 1e9
    mention = prop.get('mentionText', '')
    try:
        return float(re.sub(r'[^\d.\-]', '', mention))
    except:
        return None


def extract_invoice_data(json_path):
    """Extract all relevant data from an invoice JSON."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return None, f"JSON parse error: {e}"
    
    entities = extract_entities(data)
    
    invoice = {
        'account_number': None,
        'invoice_number': None,
        'invoice_date': None,
        'vendor_name': None,
        'location_code': None,
        'service_address': None,
        'total_amount': None,
        'line_items': []
    }
    
    # Extract header entities
    for entity in entities:
        entity_type = entity.get('type', '').lower()
        mention = entity.get('mentionText', '').strip()
        
        if 'account' in entity_type and 'number' in entity_type:
            invoice['account_number'] = mention
        elif 'invoice' in entity_type and ('number' in entity_type or 'id' in entity_type):
            invoice['invoice_number'] = mention
        elif 'invoice' in entity_type and 'date' in entity_type:
            invoice['invoice_date'] = mention
        elif 'supplier' in entity_type or 'vendor' in entity_type:
            invoice['vendor_name'] = mention
        elif 'location' in entity_type:
            invoice['location_code'] = mention
        elif 'service' in entity_type and 'address' in entity_type:
            invoice['service_address'] = mention
        elif entity_type in ['total_amount', 'amount_due', 'total_due']:
            invoice['total_amount'] = parse_money_value(entity)
    
    # Extract line items
    for entity in entities:
        if entity.get('type') == 'line_item':
            props = {
                'description': None,
                'amount': None,
                'quantity': None,
                'unit_price': None,
                'service_date': None
            }
            full_text = entity.get('mentionText', '').strip()
            
            for prop in entity.get('properties', []):
                prop_type = prop.get('type', '').lower()
                
                if 'description' in prop_type:
                    props['description'] = prop.get('mentionText', '').strip()
                elif prop_type == 'line_item/amount':
                    props['amount'] = parse_money_value(prop)
                elif 'quantity' in prop_type:
                    nv = prop.get('normalizedValue', {})
                    if 'floatValue' in nv:
                        props['quantity'] = nv['floatValue']
                    else:
                        try:
                            props['quantity'] = float(prop.get('mentionText', '').replace(',', ''))
                        except:
                            pass
                elif 'unit_price' in prop_type:
                    props['unit_price'] = parse_money_value(prop)
                elif 'date' in prop_type:
                    props['service_date'] = prop.get('mentionText', '').strip()
            
            # Use full_text if description wasn't captured
            final_desc = props['description'] or clean_description(full_text)
            
            if final_desc or props['amount']:
                parsed_equipment = extract_equipment_from_description(final_desc) or extract_equipment_from_description(full_text)
                parsed_material = extract_material_from_description(final_desc) or extract_material_from_description(full_text)
                
                invoice['line_items'].append({
                    'description': final_desc.upper() if final_desc else '',
                    'amount': props['amount'],
                    'quantity': props['quantity'],
                    'unit_price': props['unit_price'],
                    'service_date': props['service_date'],
                    'full_text': full_text,
                    'parsed_equipment': parsed_equipment,
                    'parsed_material': parsed_material
                })
    
    return invoice, None


def process_folder(folder_path, vendor_filter=None):
    """Process all JSON files in folder."""
    all_rows = []
    summary = defaultdict(lambda: {'count': 0, 'total_amount': 0})
    errors = []
    
    json_files = []
    for root, dirs, files in os.walk(folder_path):
        for f in files:
            if f.endswith('.json'):
                json_files.append(os.path.join(root, f))
    
    print(f"Found {len(json_files)} JSON files")
    
    for i, json_path in enumerate(json_files):
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(json_files)}...")
        
        invoice, error = extract_invoice_data(json_path)
        
        if error:
            errors.append(f"{json_path}: {error}")
            continue
        
        if not invoice:
            continue
        
        # Apply vendor filter
        if vendor_filter:
            vendor = invoice.get('vendor_name', '') or ''
            if vendor_filter.lower() not in vendor.lower():
                continue
        
        # Get MD5 from filename
        json_md5 = os.path.splitext(os.path.basename(json_path))[0]
        
        # Create row for each line item
        for item in invoice['line_items']:
            row = {
                'json_md5': json_md5,
                'vendor_name': invoice['vendor_name'],
                'account_number': invoice['account_number'],
                'invoice_number': invoice['invoice_number'],
                'invoice_date': invoice['invoice_date'],
                'location_code': invoice['location_code'],
                'service_address': invoice['service_address'],
                'line_description': item['description'],
                'line_amount': item['amount'],
                'line_quantity': item['quantity'],
                'line_unit_price': item['unit_price'],
                'service_date': item['service_date'],
                'parsed_equipment': item['parsed_equipment'],
                'parsed_material': item['parsed_material'],
                'full_text': item['full_text']
            }
            all_rows.append(row)
            
            # Update summary
            key = (invoice['vendor_name'], item['description'])
            summary[key]['count'] += 1
            if item['amount']:
                summary[key]['total_amount'] += item['amount']
    
    return all_rows, summary, errors


def save_results(all_rows, summary, errors, output_prefix):
    """Save results to CSV files."""
    timestamp = datetime.now().strftime('%Y-%m-%d')
    
    # Detail file
    detail_file = f"{output_prefix}_detail_{timestamp}.csv"
    if all_rows:
        with open(detail_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"Wrote {len(all_rows)} rows to {detail_file}")
    
    # Summary file
    summary_file = f"{output_prefix}_summary_{timestamp}.csv"
    summary_rows = [
        {'vendor': k[0], 'description': k[1], 'count': v['count'], 'total_amount': v['total_amount']}
        for k, v in sorted(summary.items(), key=lambda x: -x[1]['count'])
    ]
    if summary_rows:
        with open(summary_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['vendor', 'description', 'count', 'total_amount'])
            writer.writeheader()
            writer.writerows(summary_rows)
        print(f"Wrote {len(summary_rows)} summary rows to {summary_file}")
    
    # Errors file
    if errors:
        error_file = f"{output_prefix}_errors_{timestamp}.txt"
        with open(error_file, 'w', encoding='utf-8') as f:
            for err in errors:
                f.write(err + '\n')
        print(f"Wrote {len(errors)} errors to {error_file}")
    
    return detail_file, summary_file


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_line_items.py /path/to/json/folder [vendor_name]")
        print("\nExamples:")
        print('  python extract_line_items.py ./invoices')
        print('  python extract_line_items.py "./My Folder/invoices"')
        print('  python extract_line_items.py ./invoices "Lawrence Waste"')
        sys.exit(1)
    
    folder_path = sys.argv[1]
    vendor_filter = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.isdir(folder_path):
        print(f"Error: {folder_path} is not a directory")
        print("Hint: If path has spaces, wrap it in quotes")
        sys.exit(1)
    
    print(f"Scanning: {folder_path}")
    if vendor_filter:
        print(f"Filtering for vendor: {vendor_filter}")
    
    all_rows, summary, errors = process_folder(folder_path, vendor_filter)
    
    output_prefix = "invoice_extract"
    if vendor_filter:
        safe_vendor = re.sub(r'[^\w\-]', '_', vendor_filter)[:30]
        output_prefix = f"invoice_{safe_vendor}"
    
    save_results(all_rows, summary, errors, output_prefix)


if __name__ == '__main__':
    main()
