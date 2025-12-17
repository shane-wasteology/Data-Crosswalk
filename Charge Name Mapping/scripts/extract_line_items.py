#!/usr/bin/env python3
"""
Extract Invoice Line Items from Document AI JSONs.

Parses Document AI JSON output and extracts structured line item data
for matching against billing_charges to build charge_type_map.

Usage:
    python extract_line_items.py json_by_vendor
    python extract_line_items.py json_by_vendor --output invoice_extract.csv

Output columns:
    json_md5, vendor_name, account_number, invoice_number, invoice_date,
    location_code, service_address, line_description, parsed_equipment,
    parsed_material, line_amount, line_quantity, line_unit_price,
    service_date, full_text
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime
import csv


# Equipment patterns - order matters (more specific first)
EQUIPMENT_PATTERNS = [
    (r'\b(\d+)\s*YA?RD?\s*(COMPACTOR|COMP)\b', lambda m: f"{m.group(1)} Yard Compactor"),
    (r'\b(\d+)\s*YA?RD?\s*(ROLL.?OFF|RO)\b', lambda m: f"{m.group(1)} Yard Roll Off"),
    (r'\b(\d+)\s*YA?RD?\s*(FRONT.?LOAD|FL)\b', lambda m: f"{m.group(1)} Yard Front Load"),
    (r'\b(\d+)\s*YA?RD?\s*(REAR.?LOAD|RL)\b', lambda m: f"{m.group(1)} Yard Rear Load"),
    (r'\b(\d+)\s*YA?RD?\s*(OPEN.?TOP|OT)\b', lambda m: f"{m.group(1)} Yard Open Top"),
    (r'\b(\d+)\s*CY\b', lambda m: f"{m.group(1)} Yard"),
    (r'\bCOMPACTOR\b', lambda m: "Compactor"),
    (r'\bROLL.?OFF\b', lambda m: "Roll Off"),
    (r'\bFRONT.?LOAD\b', lambda m: "Front Load"),
    (r'\bREAR.?LOAD\b', lambda m: "Rear Load"),
    (r'\bOPEN.?TOP\b', lambda m: "Open Top"),
    (r'\b(\d+)\s*GAL(LON)?\b', lambda m: f"{m.group(1)} Gallon"),
    (r'\bTOTER\b', lambda m: "Toter"),
]

# Material patterns
MATERIAL_PATTERNS = [
    (r'\bCARDBOARD|OCC\b', 'OCC'),
    (r'\bPAPER\b', 'Paper'),
    (r'\bPLASTIC|HDPE|PET\b', 'Plastic'),
    (r'\bMETAL|SCRAP\s*METAL|ALUMINUM\b', 'Metal'),
    (r'\bGLASS\b', 'Glass'),
    (r'\bWOOD|PALLETS?\b', 'Wood'),
    (r'\bORGANIC|FOOD\s*WASTE|COMPOST\b', 'Organic'),
    (r'\bE-?WASTE|ELECTRONIC\b', 'E-Waste'),
    (r'\bC&D|CONSTRUCTION|DEMO(LITION)?\b', 'C&D'),
    (r'\bMSW|TRASH|GARBAGE|REFUSE\b', 'Trash'),
    (r'\bRECYCL(E|ING|ABLES?)?\b', 'Recycling'),
]


def extract_equipment(text):
    """Extract equipment type from description."""
    if not text:
        return ''
    text = str(text).upper()
    for pattern, formatter in EQUIPMENT_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return formatter(match)
    return ''


def extract_material(text):
    """Extract material type from description."""
    if not text:
        return ''
    text = str(text).upper()
    for pattern, material in MATERIAL_PATTERNS:
        if re.search(pattern, text):
            return material
    return ''


def get_entity_value(entities, entity_type):
    """Extract entity value from Document AI entities."""
    for entity in entities:
        if entity.get('type') == entity_type:
            return entity.get('mentionText', '').strip()
    return ''


def parse_amount(text):
    """Parse dollar amount from text."""
    if not text:
        return None
    text = str(text).replace('$', '').replace(',', '').strip()
    try:
        return float(text)
    except:
        return None


def extract_line_items_from_json(json_path):
    """Extract line items from a single Document AI JSON file."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return None, f"JSON parse error: {e}"
    
    # Get MD5 from filename
    json_md5 = os.path.basename(json_path).replace('.json', '')
    
    # Get entities
    entities = data.get('entities', [])
    
    # Extract header info
    vendor_name = get_entity_value(entities, 'supplier_name')
    account_number = get_entity_value(entities, 'account_number') or get_entity_value(entities, 'customer_id')
    invoice_number = get_entity_value(entities, 'invoice_number') or get_entity_value(entities, 'invoice_id')
    invoice_date = get_entity_value(entities, 'invoice_date')
    location_code = get_entity_value(entities, 'site_number') or get_entity_value(entities, 'location_code')
    service_address = get_entity_value(entities, 'service_address') or get_entity_value(entities, 'ship_to_address')
    
    # Extract line items
    line_items = []
    
    for entity in entities:
        if entity.get('type') == 'line_item':
            props = {p.get('type'): p.get('mentionText', '') for p in entity.get('properties', [])}
            
            description = props.get('line_item/description', '') or props.get('line_item/product_code', '')
            amount = parse_amount(props.get('line_item/amount', ''))
            quantity = parse_amount(props.get('line_item/quantity', ''))
            unit_price = parse_amount(props.get('line_item/unit_price', ''))
            service_date = props.get('line_item/service_date', '')
            
            # Build full text from all properties
            full_text = ' '.join([v for v in props.values() if v]).strip()
            
            # Clean description
            description_clean = re.sub(r'\s+', ' ', description).strip().upper()
            
            line_items.append({
                'json_md5': json_md5,
                'vendor_name': vendor_name,
                'account_number': account_number,
                'invoice_number': invoice_number,
                'invoice_date': invoice_date,
                'location_code': location_code,
                'service_address': service_address,
                'line_description': description_clean,
                'parsed_equipment': extract_equipment(description),
                'parsed_material': extract_material(description),
                'line_amount': amount,
                'line_quantity': quantity,
                'line_unit_price': unit_price,
                'service_date': service_date,
                'full_text': full_text,
            })
    
    return line_items, None


def process_folder(folder_path, output_file=None):
    """Process all JSONs in folder (recursively)."""
    
    if output_file is None:
        output_file = f"invoice_extract_detail_{datetime.now().strftime('%Y-%m-%d')}.csv"
    
    all_line_items = []
    errors = []
    processed = 0
    
    # Walk through all JSON files
    for root, dirs, files in os.walk(folder_path):
        json_files = [f for f in files if f.endswith('.json')]
        
        if json_files:
            folder_name = os.path.basename(root)
            print(f"\n{folder_name}: {len(json_files)} files")
        
        for filename in json_files:
            json_path = os.path.join(root, filename)
            
            line_items, error = extract_line_items_from_json(json_path)
            
            if error:
                errors.append((json_path, error))
            elif line_items:
                all_line_items.extend(line_items)
                processed += 1
    
    # Write output
    if all_line_items:
        fieldnames = [
            'json_md5', 'vendor_name', 'account_number', 'invoice_number',
            'invoice_date', 'location_code', 'service_address', 'line_description',
            'parsed_equipment', 'parsed_material', 'line_amount', 'line_quantity',
            'line_unit_price', 'service_date', 'full_text'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_line_items)
        
        print(f"\n{'='*50}")
        print(f"SUMMARY")
        print(f"{'='*50}")
        print(f"Files processed: {processed}")
        print(f"Line items extracted: {len(all_line_items)}")
        print(f"Errors: {len(errors)}")
        print(f"Output: {output_file}")
    else:
        print("No line items extracted!")
    
    # Write errors if any
    if errors:
        error_file = output_file.replace('.csv', '_errors.txt')
        with open(error_file, 'w') as f:
            for path, error in errors:
                f.write(f"{path}: {error}\n")
        print(f"Errors logged: {error_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract line items from Document AI JSONs"
    )
    parser.add_argument(
        "folder",
        help="Folder containing JSON files (searched recursively)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output CSV file (default: invoice_extract_detail_YYYY-MM-DD.csv)"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.folder):
        print(f"ERROR: Folder not found: {args.folder}")
        sys.exit(1)
    
    process_folder(args.folder, args.output)


if __name__ == '__main__':
    main()
