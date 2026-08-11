#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Remove BOM from manifest.json
"""

import os

def remove_bom(filename):
    """Remove BOM from file"""
    print(f"Removing BOM from {filename}...")
    
    # Read file
    with open(filename, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    
    # Write without BOM
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[OK] BOM removed from {filename}")

if __name__ == "__main__":
    print("=" * 60)
    print(" BOM Remover")
    print("=" * 60)
    print("")
    
    remove_bom("widget/manifest.json")
    
    print("")
    print("SUCCESS! Now recreate the archive:")
    print("  python create_widget_archive.py")
    print("")
    input("Press Enter to exit...")
