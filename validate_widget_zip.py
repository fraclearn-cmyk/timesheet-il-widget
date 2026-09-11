#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validator for amoCRM widget ZIP packages
Performs 8 critical validation checks
"""

import zipfile
import json
import sys
import os
import re
from pathlib import Path

class WidgetValidator:
    def __init__(self, zip_path):
        self.zip_path = zip_path
        self.errors = []
        self.warnings = []
        self.checks_passed = 0
        self.checks_total = 8
        
    def check_1_bom_absence(self):
        """Check 1: No UTF-8 BOM in any text files"""
        print("CHECK 1: UTF-8 BOM absence...", end=" ")
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                text_extensions = ['.json', '.js', '.css', '.html', '.txt']
                bom_found = False
                
                for file_info in zf.filelist:
                    if any(file_info.filename.endswith(ext) for ext in text_extensions):
                        data = zf.read(file_info.filename)
                        if data.startswith(b'\xef\xbb\xbf'):
                            self.errors.append(f"BOM found in {file_info.filename}")
                            bom_found = True
                
                if bom_found:
                    print("❌ FAILED")
                    return False
                else:
                    print("✓ PASSED")
                    self.checks_passed += 1
                    return True
        except Exception as e:
            self.errors.append(f"Check 1 error: {e}")
            print("❌ ERROR")
            return False
    
    def check_2_json_parsing(self):
        """Check 2: All JSON files parse successfully"""
        print("CHECK 2: JSON parsing...", end=" ")
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                json_files = [f for f in zf.namelist() if f.endswith('.json')]
                
                for json_file in json_files:
                    try:
                        content = zf.read(json_file).decode('utf-8-sig')
                        json.loads(content)
                    except json.JSONDecodeError as e:
                        self.errors.append(f"JSON parsing error in {json_file}: {e}")
                        print("❌ FAILED")
                        return False
                
                print("✓ PASSED")
                self.checks_passed += 1
                return True
        except Exception as e:
            self.errors.append(f"Check 2 error: {e}")
            print("❌ ERROR")
            return False
    
    def check_3_locations_field(self):
        """Check 3: Locations field contains valid values"""
        print("CHECK 3: Locations field validation...", end=" ")
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                manifest_data = zf.read('manifest.json').decode('utf-8-sig')
                manifest = json.loads(manifest_data)
                
                if 'locations' not in manifest:
                    self.errors.append("manifest.json missing 'locations' field")
                    print("❌ FAILED")
                    return False
                
                locations = manifest['locations']
                valid_locations = ['advanced_settings', 'settings', 'dashboard']
                
                for loc in locations:
                    if loc not in valid_locations:
                        self.errors.append(f"Invalid location value: {loc}")
                        print("❌ FAILED")
                        return False
                
                # Must have at least one location
                if not locations or len(locations) == 0:
                    self.errors.append("No locations specified in manifest")
                    print("❌ FAILED")
                    return False
                
                print("✓ PASSED")
                self.checks_passed += 1
                return True
        except Exception as e:
            self.errors.append(f"Check 3 error: {e}")
            print("❌ ERROR")
            return False
    
    def check_4_advanced_block(self):
        """Check 4: Advanced settings block present with required structure"""
        print("CHECK 4: Advanced block structure...", end=" ")
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                manifest_data = zf.read('manifest.json').decode('utf-8-sig')
                manifest = json.loads(manifest_data)
                
                if 'advanced' not in manifest:
                    self.errors.append("manifest.json missing 'advanced' block")
                    print("❌ FAILED")
                    return False
                
                advanced = manifest['advanced']
                if not isinstance(advanced, dict):
                    self.errors.append("'advanced' is not a dict/object")
                    print("❌ FAILED")
                    return False
                
                if 'title' not in advanced:
                    self.errors.append("'advanced' block missing 'title' field")
                    print("❌ FAILED")
                    return False
                
                print("✓ PASSED")
                self.checks_passed += 1
                return True
        except Exception as e:
            self.errors.append(f"Check 4 error: {e}")
            print("❌ ERROR")
            return False
    
    def check_5_advanced_callback(self):
        """Check 5: advancedSettings callback exists in script.js"""
        print("CHECK 5: advancedSettings callback...", end=" ")
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                script_data = zf.read('script.js').decode('utf-8-sig')
                
                if 'advancedSettings' not in script_data:
                    self.errors.append("'advancedSettings' callback not found in script.js")
                    print("❌ FAILED")
                    return False
                
                # Check it's a function definition
                if not re.search(r'advancedSettings\s*:\s*function', script_data):
                    self.errors.append("'advancedSettings' is not defined as a function")
                    print("❌ FAILED")
                    return False
                
                print("✓ PASSED")
                self.checks_passed += 1
                return True
        except Exception as e:
            self.errors.append(f"Check 5 error: {e}")
            print("❌ ERROR")
            return False
    
    def check_6_required_images(self):
        """Check 6: Required images present (images/logo.png)"""
        print("CHECK 6: Required images...", end=" ")
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                files = zf.namelist()
                
                required_images = ['images/logo.png']
                
                for img in required_images:
                    if img not in files:
                        self.errors.append(f"Missing required image: {img}")
                        print("❌ FAILED")
                        return False
                
                print("✓ PASSED")
                self.checks_passed += 1
                return True
        except Exception as e:
            self.errors.append(f"Check 6 error: {e}")
            print("❌ ERROR")
            return False
    
    def check_7_unwanted_files(self):
        """Check 7: No unnecessary files in ZIP (reject demo.html, etc)"""
        print("CHECK 7: No unwanted files...", end=" ")
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                files = zf.namelist()
                
                unwanted_files = ['demo.html', 'test.html', '.DS_Store', 'README.md']
                
                for unwanted in unwanted_files:
                    if unwanted in files:
                        self.errors.append(f"Unwanted file found: {unwanted}")
                        print("❌ FAILED")
                        return False
                
                print("✓ PASSED")
                self.checks_passed += 1
                return True
        except Exception as e:
            self.errors.append(f"Check 7 error: {e}")
            print("❌ ERROR")
            return False
    
    def check_8_structure(self):
        """Check 8: manifest.json in ZIP root with proper directory structure"""
        print("CHECK 8: ZIP structure...", end=" ")
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                files = zf.namelist()
                
                # manifest.json must be in root
                if 'manifest.json' not in files:
                    self.errors.append("manifest.json not in ZIP root")
                    print("❌ FAILED")
                    return False
                
                # Required files must exist at root or in proper directories
                required_files = [
                    'manifest.json',
                    'script.js',
                    'styles.css',
                    'i18n/ru.json',
                    'i18n/en.json',
                    'images/logo.png'
                ]
                
                for required in required_files:
                    if required not in files:
                        self.errors.append(f"Missing required file: {required}")
                        print("❌ FAILED")
                        return False
                
                # Check no files in subdirectories like "widget/"
                for file in files:
                    if file.startswith('widget/'):
                        self.errors.append(f"Files should not be in 'widget/' subdirectory: {file}")
                        print("❌ FAILED")
                        return False
                
                print("✓ PASSED")
                self.checks_passed += 1
                return True
        except Exception as e:
            self.errors.append(f"Check 8 error: {e}")
            print("❌ ERROR")
            return False
    
    def validate(self):
        """Run all validation checks"""
        print("=" * 60)
        print("  amoCRM Widget Validator v1.0")
        print("=" * 60)
        print(f"File: {self.zip_path}\n")
        
        # Run all 8 checks
        self.check_1_bom_absence()
        self.check_2_json_parsing()
        self.check_3_locations_field()
        self.check_4_advanced_block()
        self.check_5_advanced_callback()
        self.check_6_required_images()
        self.check_7_unwanted_files()
        self.check_8_structure()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"RESULTS: {self.checks_passed}/{self.checks_total} checks passed")
        print("=" * 60)
        
        if self.errors:
            print("\n❌ ERRORS:")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        if self.checks_passed == self.checks_total:
            print("\n✓ VALIDATION PASSED - Widget is ready for deployment!")
            return True
        else:
            print(f"\n❌ VALIDATION FAILED - {self.checks_total - self.checks_passed} check(s) failed")
            return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_widget_zip.py <path_to_widget.zip>")
        print("\nExample: python validate_widget_zip.py timesheet_il_widget.zip")
        sys.exit(1)
    
    zip_path = sys.argv[1]
    
    if not os.path.exists(zip_path):
        print(f"ERROR: File not found: {zip_path}")
        sys.exit(1)
    
    if not zipfile.is_zipfile(zip_path):
        print(f"ERROR: Not a valid ZIP file: {zip_path}")
        sys.exit(1)
    
    validator = WidgetValidator(zip_path)
    success = validator.validate()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
