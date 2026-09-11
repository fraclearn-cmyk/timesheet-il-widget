#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix widget according to specifications:
1. Remove UTF-8 BOM from files
2. Update manifest.json
3. Update i18n files
4. Create logo.png
5. Add advancedSettings callback to script.js
"""

import json
import os
import sys

# Widget path
WIDGET_PATH = r"d:\табель\widget"
IMAGES_PATH = os.path.join(WIDGET_PATH, "images")
I18N_PATH = os.path.join(WIDGET_PATH, "i18n")

def remove_utf8_bom(file_path):
    """Remove UTF-8 BOM from file if present."""
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Check for UTF-8 BOM (EF BB BF)
        if content.startswith(b'\xef\xbb\xbf'):
            print(f"✓ Removing BOM from: {os.path.basename(file_path)}")
            # Remove BOM and rewrite
            with open(file_path, 'wb') as f:
                f.write(content[3:])
            return True
    except Exception as e:
        print(f"✗ Error removing BOM from {file_path}: {e}")
    return False

def read_file_safe(file_path):
    """Read file handling BOM properly."""
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            return f.read()
    except Exception as e:
        print(f"✗ Error reading {file_path}: {e}")
        return None

def write_file_utf8(file_path, content):
    """Write file in UTF-8 without BOM."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"✗ Error writing {file_path}: {e}")
        return False

def main():
    print("=== Starting Widget Fixes ===\n")
    
    # 1. Remove BOM from text files
    print("1. Removing UTF-8 BOM from files...")
    text_files = [
        os.path.join(WIDGET_PATH, "manifest.json"),
        os.path.join(WIDGET_PATH, "script.js"),
        os.path.join(WIDGET_PATH, "styles.css"),
        os.path.join(I18N_PATH, "ru.json"),
        os.path.join(I18N_PATH, "en.json"),
    ]
    
    for file_path in text_files:
        if os.path.exists(file_path):
            remove_utf8_bom(file_path)
    
    # 2. Update manifest.json
    print("\n2. Updating manifest.json...")
    manifest_path = os.path.join(WIDGET_PATH, "manifest.json")
    try:
        manifest_content = read_file_safe(manifest_path)
        manifest = json.loads(manifest_content)
        
        # Fix locations
        manifest["locations"] = ["advanced_settings"]
        
        # Remove scopes
        if "scopes" in manifest:
            del manifest["scopes"]
        
        # Add advanced settings
        manifest["advanced"] = {"title": "advanced.title"}
        
        # Write back
        json_str = json.dumps(manifest, ensure_ascii=False, indent=2)
        if write_file_utf8(manifest_path, json_str):
            print("✓ manifest.json updated")
    except Exception as e:
        print(f"✗ Error updating manifest.json: {e}")
    
    # 3. Update i18n/ru.json
    print("\n3. Updating i18n/ru.json...")
    ru_path = os.path.join(I18N_PATH, "ru.json")
    try:
        ru_content = read_file_safe(ru_path)
        ru = json.loads(ru_content)
        
        if "advanced" not in ru:
            ru["advanced"] = {}
        ru["advanced"]["title"] = "Настройки табеля"
        
        json_str = json.dumps(ru, ensure_ascii=False, indent=2)
        if write_file_utf8(ru_path, json_str):
            print("✓ i18n/ru.json updated")
    except Exception as e:
        print(f"✗ Error updating i18n/ru.json: {e}")
    
    # 4. Update i18n/en.json
    print("\n4. Updating i18n/en.json...")
    en_path = os.path.join(I18N_PATH, "en.json")
    try:
        en_content = read_file_safe(en_path)
        en = json.loads(en_content)
        
        if "advanced" not in en:
            en["advanced"] = {}
        en["advanced"]["title"] = "Timesheet Settings"
        
        json_str = json.dumps(en, ensure_ascii=False, indent=2)
        if write_file_utf8(en_path, json_str):
            print("✓ i18n/en.json updated")
    except Exception as e:
        print(f"✗ Error updating i18n/en.json: {e}")
    
    # 5. Create images directory and logo.png
    print("\n5. Creating images/logo.png...")
    if not os.path.exists(IMAGES_PATH):
        os.makedirs(IMAGES_PATH)
        print("✓ Created images directory")
    
    logo_path = os.path.join(IMAGES_PATH, "logo.png")
    if not os.path.exists(logo_path):
        # Minimal 1x1 transparent PNG
        png_bytes = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
            0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,
            0x54, 0x78, 0x9C, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
            0x00, 0x03, 0x01, 0x01, 0x00, 0x18, 0xDD, 0x8D,
            0xB4, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        with open(logo_path, 'wb') as f:
            f.write(png_bytes)
        print("✓ images/logo.png created (1x1 transparent PNG)")
    else:
        print("✓ images/logo.png already exists")
    
    # 6. Add advancedSettings callback to script.js
    print("\n6. Adding advancedSettings callback to script.js...")
    script_path = os.path.join(WIDGET_PATH, "script.js")
    try:
        script_content = read_file_safe(script_path)
        
        if "advancedSettings" not in script_content:
            # Find settings callback and add advancedSettings after it
            if "settings: function()" in script_content:
                callback = """advancedSettings: function() {
                console.log('Advanced settings opened');
                return true;
            },"""
                # Insert after settings callback
                script_content = script_content.replace(
                    "settings: function() {",
                    f"settings: function() {{"
                )
                # Find the closing of settings callback and insert advancedSettings
                # More careful approach: find and insert after the settings function
                lines = script_content.split('\n')
                new_lines = []
                in_settings = False
                brace_count = 0
                
                for i, line in enumerate(lines):
                    new_lines.append(line)
                    if "settings: function()" in line:
                        in_settings = True
                        brace_count = 0
                    
                    if in_settings:
                        brace_count += line.count('{') - line.count('}')
                        if brace_count == 0 and "settings: function()" in ''.join(lines[max(0, i-5):i+1]):
                            # Add comma and new callback
                            if line.strip().endswith('}'):
                                new_lines[-1] = line.rstrip(',') + ','
                                new_lines.append("            " + callback)
                                in_settings = False
                
                script_content = '\n'.join(new_lines)
                if write_file_utf8(script_path, script_content):
                    print("✓ advancedSettings callback added")
            else:
                print("⚠ settings callback not found in expected format")
        else:
            print("✓ advancedSettings callback already exists")
    except Exception as e:
        print(f"✗ Error updating script.js: {e}")
    
    # 7. Verify changes
    print("\n7. Verifying changes...")
    try:
        manifest_content = read_file_safe(manifest_path)
        manifest = json.loads(manifest_content)
        print(f"  ✓ locations: {manifest.get('locations', [])}")
        print(f"  ✓ advanced.title: {manifest.get('advanced', {}).get('title', '')}")
        print(f"  ✓ scopes removed: {'scopes' not in manifest}")
        print(f"  ✓ logo.png exists: {os.path.exists(logo_path)}")
    except Exception as e:
        print(f"  ✗ Error verifying: {e}")
    
    print("\n=== Widget Fixes Complete ===")

if __name__ == "__main__":
    main()
