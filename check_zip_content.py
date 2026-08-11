#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check and compare ZIP archives
"""

import zipfile
import os

def check_archive(filename):
    """Check archive structure and content"""
    print(f"\n{'='*60}")
    print(f" Checking: {filename}")
    print('='*60)
    
    if not os.path.exists(filename):
        print(f"ERROR: File not found!")
        return
    
    try:
        with zipfile.ZipFile(filename, 'r') as zipf:
            print(f"\nSize: {os.path.getsize(filename) / 1024:.2f} KB")
            print(f"\nFiles ({len(zipf.namelist())}):")
            
            for info in zipf.infolist():
                print(f"  {info.filename:30} {info.file_size:>8} bytes")
            
            # Check manifest.json
            if 'manifest.json' in zipf.namelist():
                print(f"\n{'='*60}")
                print(" manifest.json content:")
                print('='*60)
                manifest_content = zipf.read('manifest.json').decode('utf-8')
                print(manifest_content[:500])  # First 500 chars
                
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    print("ZIP Archive Checker")
    print("")
    
    # Check both archives
    check_archive("widget_minimal_test.zip")
    check_archive("widget.zip")
    
    print(f"\n{'='*60}")
    input("\nPress Enter to exit...")
