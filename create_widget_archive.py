#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create widget archive with correct structure for amoCRM
"""

import os
import zipfile
import sys

def create_widget_archive(source_dir, output_file):
    """Create archive with files in root"""
    print(f"Creating archive from {source_dir}...")
    print("")
    
    files_to_add = []
    
    # Walk through directory
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            full_path = os.path.join(root, file)
            # Get relative path from source_dir
            rel_path = os.path.relpath(full_path, source_dir)
            # Normalize path separators to forward slashes (required by amoCRM!)
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
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print(" Widget Archive Creator for amoCRM")
    print("=" * 50)
    print("")
    
    # Create main widget archive
    if create_widget_archive("widget", "widget.zip"):
        print("")
        print("Upload widget.zip to amoCRM!")
    
    print("")
    input("Press Enter to exit...")
