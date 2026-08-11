#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create final widget v1.0.4 with settings
Remove BOM from all files and create archive
"""

import os
import zipfile

def remove_bom(filename):
    """Remove BOM from file"""
    try:
        with open(filename, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"[OK] Processed: {filename}")
    except Exception as e:
        print(f"[SKIP] {filename}: {e}")

def create_archive(source_dir, output_file):
    """Create archive with correct structure"""
    print(f"\nCreating archive from {source_dir}...")
    print("")
    
    files_to_add = []
    
    # Walk through directory
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, source_dir)
            # Normalize path separators to forward slashes
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
    print("=" * 60)
    print(" Creating Widget v1.0.4 with Settings")
    print("=" * 60)
    print("")
    
    # Remove BOM from all text files
    print("Step 1: Removing BOM from files...")
    print("-" * 60)
    
    text_files = [
        "widget/manifest.json",
        "widget/script.js",
        "widget/styles.css",
        "widget/demo.html",
        "widget/i18n/ru.json",
        "widget/i18n/en.json"
    ]
    
    for file in text_files:
        remove_bom(file)
    
    print("")
    print("Step 2: Creating archive...")
    print("-" * 60)
    
    # Create widget archive
    if create_archive("widget", "widget.zip"):
        print("")
        print("=" * 60)
        print(" SUCCESS! Widget v1.0.4 ready!")
        print("=" * 60)
        print("")
        print("Now:")
        print("  1. Delete old widget from amoCRM")
        print("  2. Upload new widget.zip")
        print("  3. Install with backend_url setting")
        print("  4. Test functionality!")
    else:
        print("")
        print("Failed to create archive!")
    
    print("")
    input("Press Enter to exit...")
