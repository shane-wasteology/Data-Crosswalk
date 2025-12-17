#!/usr/bin/env python3
"""
Download Invoice JSONs from GCP organized by vendor.

Usage:
    python download_vendor_jsons.py vendor_md5s.csv
    python download_vendor_jsons.py vendor_md5s.csv --output-dir json_by_vendor

Prerequisites:
    pip install google-cloud-storage pandas
    gcloud auth application-default login
    gcloud config set project academic-torch-405913

Input CSV format (from charge_mapping_queries.sql Query 3):
    vendor_name,billing_reference,invoice_md5,invoice_date
    GFL,12345,abc123def456,2025-10-15
"""

import os
import sys
import re
import argparse
import warnings

# Suppress GCP auth warnings
warnings.filterwarnings("ignore", message="Your application has authenticated using end user credentials")
warnings.filterwarnings("ignore", category=UserWarning, module="google")

import pandas as pd

try:
    from google.cloud import storage
except ImportError:
    print("ERROR: google-cloud-storage not installed")
    print("Run: pip install google-cloud-storage")
    sys.exit(1)

# GCP Configuration
BUCKET_NAME = "invoice_inference_json_output"
PROJECT_ID = "academic-torch-405913"


def sanitize_folder_name(name):
    """Make vendor name safe for folder name."""
    if pd.isna(name):
        return "Unknown"
    name = str(name).strip()
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name[:50]


def download_vendor_jsons(csv_file, output_dir="json_by_vendor"):
    """Download JSONs organized by vendor folder."""
    
    # Load CSV
    print(f"Loading {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Check required columns
    if 'invoice_md5' not in df.columns:
        print("ERROR: CSV must have 'invoice_md5' column")
        sys.exit(1)
    
    if 'vendor_name' not in df.columns:
        print("ERROR: CSV must have 'vendor_name' column")
        sys.exit(1)
    
    # Filter to rows with valid MD5
    df = df[df['invoice_md5'].notna() & (df['invoice_md5'] != '')]
    print(f"  {len(df)} invoices with MD5s")
    print(f"  {df['vendor_name'].nunique()} vendors")
    
    # Initialize GCP client
    print(f"\nConnecting to GCP bucket: {BUCKET_NAME}")
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Download by vendor
    downloaded = 0
    skipped = 0
    not_found = 0
    
    for vendor in df['vendor_name'].unique():
        vendor_folder = sanitize_folder_name(vendor)
        vendor_path = os.path.join(output_dir, vendor_folder)
        os.makedirs(vendor_path, exist_ok=True)
        
        vendor_df = df[df['vendor_name'] == vendor]
        print(f"\n{vendor} ({len(vendor_df)} invoices)")
        
        for _, row in vendor_df.iterrows():
            md5 = row['invoice_md5']
            
            # GCP path (no .json extension)
            blob_path = f"invoice_inference_json_output/{md5}"
            local_path = os.path.join(vendor_path, f"{md5}.json")
            
            # Skip if already exists
            if os.path.exists(local_path):
                skipped += 1
                continue
            
            # Download
            blob = bucket.blob(blob_path)
            try:
                blob.download_to_filename(local_path)
                downloaded += 1
                print(f"  ✓ {md5[:12]}...")
            except Exception as e:
                not_found += 1
                print(f"  ✗ {md5[:12]}... not found")
    
    print(f"\n{'='*50}")
    print(f"SUMMARY")
    print(f"{'='*50}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped (existing): {skipped}")
    print(f"Not found: {not_found}")
    print(f"Output: {output_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description="Download Invoice JSONs from GCP organized by vendor"
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
        print(f"ERROR: File not found: {args.csv_file}")
        sys.exit(1)
    
    download_vendor_jsons(args.csv_file, args.output_dir)


if __name__ == '__main__':
    main()
