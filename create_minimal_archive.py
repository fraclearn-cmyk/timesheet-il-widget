#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create MINIMAL test widget archive for amoCRM
"""

import os
import zipfile

def create_archive(source_dir, output_file):
    """Create archive with correct structure"""
    print(f"Creating archive from {source_dir}...")
    print("")
    
    files_to_add = []
    
    # Walk through directory
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            full_path = os.path.join(root, file)
            # Get relative path from source_dir
            rel_path = os.path.relpath(full_path, source_dir)
            # Normalize path separators
            rel_path = rel_path.replace('\\', '/')
            files_to_add.append((full_path, rel_path))
    
    if not files_to_add:
        print("ERROR: No files found!")
        return False
    
    # Create archive
    try:
        with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for full_path, arc_path in files_to_add:
                print(f"[OK] Adding: {arc_path}")
                zipf.write(full_path, arc_path)
        
        print("")
        print(f"SUCCESS! Created: {output_file}")
        size_kb = os.path.getsize(output_file) / 1024
        print(f"Size: {size_kb:.2f} KB")
        print("")
        print("Files in archive:")
        with zipfile.ZipFile(output_file, 'r') as zipf:
            for name in zipf.namelist():
                print(f"  - {name}")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print(" MINIMAL Test Widget Archive Creator for amoCRM")
    print("=" * 60)
    print("")
    
    # Create minimal widget archive
    if create_archive("widget_minimal", "widget_minimal_test.zip"):
        print("")
        print("Now upload widget_minimal_test.zip to amoCRM!")
        print("If it works - we know the archive structure is correct!")
    else:
        print("")
        print("Failed to create archive!")
    
    print("")
    input("Press Enter to exit...")
