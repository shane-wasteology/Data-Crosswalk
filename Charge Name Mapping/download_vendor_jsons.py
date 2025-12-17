#!/usr/bin/env python3
"""
Download Invoice JSONs from GCP organized by vendor

Location: Data-Crosswalk/Charge Name Mapping/

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
    print("google-cloud-storage not installed")
    print("   Run: pip install google-cloud-storage")
    sys.exit(1)

# GCP Configuration
BUCKET_NAME = "invoice_inference_json_output"
PROJECT_ID = "academic-torch-405913"


def sanitize_folder_name(name):
    """Make vendor name safe for folder name."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    return name[:50]


def download_vendor_jsons(csv_file, output_dir="json_by_vendor"):
    """Download JSONs organized by vendor folder."""
    
    print("=" * 60)
    print("DOWNLOAD INVOICE JSONs BY VENDOR")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    # Read CSV
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"Error reading {csv_file}: {e}")
        sys.exit(1)
    
    # Check required columns
    required = ['vendor_name', 'invoice_md5']
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"Missing columns: {missing}")
        print(f"   Found columns: {list(df.columns)}")
        sys.exit(1)
    
    # Clean data
    df = df.dropna(subset=['vendor_name', 'invoice_md5'])
    df['invoice_md5'] = df['invoice_md5'].astype(str).str.strip()
    df = df[df['invoice_md5'] != '']
    
    print(f"Loaded {len(df)} invoice records")
    print(f"   Vendors: {df['vendor_name'].nunique()}")
    
    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    print(f"Output directory: {output_dir}")
    
    # Connect to GCP
    print(f"Connecting to GCS bucket: {BUCKET_NAME}")
    try:
        client = storage.Client(project=PROJECT_ID)
        bucket = client.bucket(BUCKET_NAME)
        print("Connected!")
    except Exception as e:
        print(f"GCP connection failed: {e}")
        print("Try: gcloud auth application-default login")
        sys.exit(1)
    
    # Download by vendor
    stats = {'downloaded': 0, 'not_found': 0, 'errors': 0, 'by_vendor': {}}
    vendors = df.groupby('vendor_name')
    
    print(f"\nDownloading from {len(vendors)} vendors...")
    
    for vendor_name, group in vendors:
        folder_name = sanitize_folder_name(vendor_name)
        vendor_dir = os.path.join(output_dir, folder_name)
        os.makedirs(vendor_dir, exist_ok=True)
        
        vendor_stats = {'downloaded': 0, 'not_found': 0, 'errors': 0}
        
        for _, row in group.iterrows():
            md5 = row['invoice_md5']
            
            # Try with .json extension first, then without
            for blob_name in [f"{md5}.json", md5]:
                blob = bucket.blob(blob_name)
                try:
                    if blob.exists():
                        output_path = os.path.join(vendor_dir, f"{md5}.json")
                        blob.download_to_filename(output_path)
                        vendor_stats['downloaded'] += 1
                        stats['downloaded'] += 1
                        break
                except Exception as e:
                    vendor_stats['errors'] += 1
                    stats['errors'] += 1
                    break
            else:
                vendor_stats['not_found'] += 1
                stats['not_found'] += 1
        
        stats['by_vendor'][vendor_name] = vendor_stats
        print(f"   {folder_name}: {vendor_stats['downloaded']}/{len(group)}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Downloaded: {stats['downloaded']}")
    print(f"Not found:  {stats['not_found']}")
    print(f"Errors:     {stats['errors']}")
    
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
        print(f"File not found: {args.csv_file}")
        sys.exit(1)
    
    download_vendor_jsons(args.csv_file, args.output_dir)


if __name__ == '__main__':
    main()
