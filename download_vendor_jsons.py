#!/usr/bin/env python3
"""
Download Invoice JSONs from GCP - Organized by Vendor

Downloads invoice JSONs from GCP and organizes them into vendor subfolders.

Location: C:/Users/ShaneStClair/OneDrive - Wasteology Group/Desktop/Deterministic Model

Usage:
    python download_vendor_jsons.py vendor_md5s.csv
    python download_vendor_jsons.py vendor_md5s.csv --output-dir json_by_vendor

Prerequisites:
    pip install google-cloud-storage pandas
    gcloud auth application-default login
    gcloud config set project academic-torch-405913

Input CSV format (from get_vendor_md5s.sql):
    vendor_name,invoice_md5,invoice_date
    Lawrence Waste,abc123,2025-10-15
    Lawrence Waste,def456,2025-10-10
    Boren Brothers,ghi789,2025-10-12
"""

import os
import sys
import re
import argparse
import pandas as pd
from datetime import datetime

try:
    from google.cloud import storage
except ImportError:
    print("❌ google-cloud-storage not installed")
    print("   Run: pip install google-cloud-storage")
    sys.exit(1)

# GCP Configuration
BUCKET_NAME = "invoice_inference_json_output"
PROJECT_ID = "academic-torch-405913"


def sanitize_folder_name(name):
    """Make vendor name safe for folder name."""
    # Remove/replace invalid characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    return name[:50]  # Limit length


def download_vendor_jsons(csv_file, output_dir="json_by_vendor"):
    """Download JSONs organized by vendor folder."""
    
    print("=" * 60)
    print("📥 DOWNLOAD INVOICE JSONs BY VENDOR")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    # Read CSV
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"❌ Error reading {csv_file}: {e}")
        sys.exit(1)
    
    # Check required columns
    required = ['vendor_name', 'invoice_md5']
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"❌ Missing columns: {missing}")
        print(f"   Found columns: {list(df.columns)}")
        sys.exit(1)
    
    # Clean data
    df = df.dropna(subset=['vendor_name', 'invoice_md5'])
    df['invoice_md5'] = df['invoice_md5'].astype(str).str.strip()
    df = df[df['invoice_md5'] != '']
    
    print(f"📝 Loaded {len(df)} invoice records")
    print(f"   Vendors: {df['vendor_name'].nunique()}")
    
    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    print(f"📂 Output directory: {output_dir}")
    
    # Connect to GCP
    print(f"☁️  Connecting to GCS bucket: {BUCKET_NAME}")
    try:
        client = storage.Client(project=PROJECT_ID)
        bucket = client.bucket(BUCKET_NAME)
        print("✅ Connected!")
    except Exception as e:
        print(f"❌ GCP connection error: {e}")
        print("   Try: gcloud auth application-default login")
        sys.exit(1)
    
    # Download by vendor
    stats = {
        'downloaded': 0,
        'not_found': 0,
        'errors': 0,
        'by_vendor': {}
    }
    
    vendors = df['vendor_name'].unique()
    print(f"\n⬇️  Downloading from {len(vendors)} vendors...")
    
    for vendor in vendors:
        vendor_md5s = df[df['vendor_name'] == vendor]['invoice_md5'].tolist()
        vendor_folder = os.path.join(output_dir, sanitize_folder_name(vendor))
        
        if not os.path.exists(vendor_folder):
            os.makedirs(vendor_folder)
        
        vendor_downloaded = 0
        vendor_not_found = 0
        
        print(f"   Processing {vendor}: {len(vendor_md5s)} MD5s...")
        
        for i, md5 in enumerate(vendor_md5s):
            if i < 3:  # Debug first 3
                print(f"      [{i}] MD5: {md5[:16]}... ", end="")
            
            # Try without .json extension first (bucket format)
            blob = bucket.blob(str(md5).strip())
            output_path = os.path.join(vendor_folder, f"{md5}.json")
            
            try:
                exists = blob.exists()
                if i < 3:
                    print(f"exists={exists}")
                
                if exists:
                    blob.download_to_filename(output_path)
                    vendor_downloaded += 1
                    stats['downloaded'] += 1
                else:
                    # Try with .json extension
                    blob_json = bucket.blob(f"{str(md5).strip()}.json")
                    if blob_json.exists():
                        blob_json.download_to_filename(output_path)
                        vendor_downloaded += 1
                        stats['downloaded'] += 1
                    else:
                        vendor_not_found += 1
                        stats['not_found'] += 1
            except Exception as e:
                if i < 3:
                    print(f"ERROR: {e}")
                stats['errors'] += 1
        
        stats['by_vendor'][vendor] = {
            'downloaded': vendor_downloaded,
            'not_found': vendor_not_found,
            'total': len(vendor_md5s)
        }
        
        status = "✅" if vendor_not_found == 0 else "⚠️"
        print(f"   {status} {vendor[:40]}: {vendor_downloaded}/{len(vendor_md5s)}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"✅ Downloaded: {stats['downloaded']}")
    print(f"⚠️  Not found:  {stats['not_found']}")
    print(f"❌ Errors:     {stats['errors']}")
    print(f"\n📁 Files saved to: {os.path.abspath(output_dir)}")
    
    # Show folder structure
    print("\n📂 Folder structure:")
    for vendor in sorted(stats['by_vendor'].keys())[:10]:
        folder = sanitize_folder_name(vendor)
        count = stats['by_vendor'][vendor]['downloaded']
        print(f"   {folder}/ ({count} files)")
    if len(stats['by_vendor']) > 10:
        print(f"   ... and {len(stats['by_vendor']) - 10} more vendors")
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Download invoice JSONs from GCP organized by vendor"
    )
    parser.add_argument(
        "csv_file",
        help="CSV file with vendor_name and invoice_md5 columns"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="json_by_vendor",
        help="Output directory (default: json_by_vendor)"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_file):
        print(f"❌ File not found: {args.csv_file}")
        sys.exit(1)
    
    download_vendor_jsons(args.csv_file, args.output_dir)


if __name__ == '__main__':
    main()
