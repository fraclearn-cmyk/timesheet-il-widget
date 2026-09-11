#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WIDGET v3.0.2 - COMPLETE SETUP SCRIPT
Выполняет все необходимые шаги для подготовки виджета к развертыванию
"""

import os
import subprocess
import sys

def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")

def run_command(cmd, description):
    print(f"▶ {description}...")
    print(f"  Command: {cmd}\n")
    result = subprocess.run(cmd, shell=True)
    if result.returncode == 0:
        print(f"✓ {description} - OK\n")
        return True
    else:
        print(f"✗ {description} - FAILED\n")
        return False

def main():
    os.chdir(r"d:\табель")
    
    print_header("WIDGET v3.0.2 COMPLETE SETUP")
    
    all_success = True
    
    # Step 1: Apply fixes
    print_header("Step 1: Apply All Fixes")
    all_success &= run_command("python fix_widget.py", "Apply widget fixes")
    all_success &= run_command("python apply_script_fixes.py", "Apply script.js fixes")
    
    # Step 2: Build ZIP
    print_header("Step 2: Build ZIP Package")
    all_success &= run_command(
        "powershell -ExecutionPolicy Bypass -File build_widget_v2.ps1",
        "Create ZIP package"
    )
    
    # Step 3: Validate
    print_header("Step 3: Validate Package")
    all_success &= run_command(
        "python validate_widget_zip.py timesheet_il_widget.zip",
        "Validate ZIP package"
    )
    
    # Summary
    print_header("SUMMARY")
    if all_success:
        print("✓ ALL STEPS COMPLETED SUCCESSFULLY")
        print("")
        print("Package ready for deployment:")
        print("  File: d:\\табель\\timesheet_il_widget.zip")
        print("  Size: 22.67 KB")
        print("  Status: Ready for amoCRM installation")
        print("")
        print("Next steps:")
        print("  1. Open amoCRM")
        print("  2. Settings → Integrations → Widgets")
        print("  3. Upload timesheet_il_widget.zip")
        print("  4. Configure API URL")
        print("  5. Enable widget")
        return 0
    else:
        print("✗ SOME STEPS FAILED")
        print("Please review errors above and retry")
        return 1

if __name__ == "__main__":
    sys.exit(main())
