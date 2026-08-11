#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Widget ZIP Validator - Проверка структуры архива виджета для amoCRM
"""

import zipfile
import os
import sys

def validate_widget_zip(zip_path):
    """Валидация структуры виджета для amoCRM"""
    
    print("=" * 70)
    print(f"📦 ВАЛИДАЦИЯ ВИДЖЕТА: {os.path.basename(zip_path)}")
    print("=" * 70)
    print()
    
    if not os.path.exists(zip_path):
        print(f"❌ ОШИБКА: Файл {zip_path} не найден!")
        return False
    
    # Проверка размера
    size_bytes = os.path.getsize(zip_path)
    size_kb = size_bytes / 1024
    size_mb = size_kb / 1024
    
    print(f"📏 Размер: {size_kb:.2f} KB ({size_mb:.2f} MB)")
    
    if size_mb > 5:
        print("❌ ОШИБКА: Размер превышает 5 MB!")
        return False
    else:
        print("✅ Размер OK (< 5 MB)")
    
    print()
    
    # Открыть архив
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            
            print(f"📁 Файлов в архиве: {len(files)}")
            print()
            
            # Проверка обязательных файлов
            print("🔍 ПРОВЕРКА ОБЯЗАТЕЛЬНЫХ ФАЙЛОВ:")
            print("-" * 70)
            
            required_files = ['manifest.json', 'script.js']
            all_required_exist = True
            
            for req_file in required_files:
                if req_file in files:
                    size = zf.getinfo(req_file).file_size
                    print(f"✅ {req_file:30s} ({size:,} bytes)")
                else:
                    print(f"❌ {req_file:30s} - ОТСУТСТВУЕТ!")
                    all_required_exist = False
            
            print()
            
            # Проверка структуры (не должно быть вложенных папок в корне)
            print("🗂️  ПРОВЕРКА СТРУКТУРЫ:")
            print("-" * 70)
            
            has_nested_folders = False
            root_folders = set()
            
            for file_path in files:
                parts = file_path.split('/')
                
                # Если первая часть - не пустая и есть еще части, это папка
                if len(parts) > 1 and parts[0]:
                    root_folders.add(parts[0])
                    
                    # Проверка на недопустимые папки (tabel, widget и т.д.)
                    if parts[0] in ['tabel', 'widget', 'temp', 'build']:
                        print(f"❌ НЕДОПУСТИМАЯ ПАПКА: {parts[0]}/")
                        has_nested_folders = True
            
            # Допустимые папки
            allowed_folders = {'i18n', 'images'}
            
            for folder in root_folders:
                if folder in allowed_folders:
                    print(f"✅ {folder}/ - OK")
                else:
                    print(f"⚠️  {folder}/ - Неожиданная папка")
            
            if not root_folders:
                print("❌ ОШИБКА: Все файлы в корне без структуры папок!")
                has_nested_folders = True
            
            print()
            
            # Список всех файлов
            print("📄 ПОЛНАЯ СТРУКТУРА АРХИВА:")
            print("-" * 70)
            
            for file_path in sorted(files):
                file_info = zf.getinfo(file_path)
                size = file_info.file_size
                
                # Определение типа
                if file_path.endswith('/'):
                    print(f"📁 {file_path}")
                elif file_path.endswith('.json'):
                    print(f"📋 {file_path:50s} {size:>8,} bytes")
                elif file_path.endswith('.js'):
                    print(f"⚙️  {file_path:50s} {size:>8,} bytes")
                elif file_path.endswith('.css'):
                    print(f"🎨 {file_path:50s} {size:>8,} bytes")
                elif file_path.endswith(('.png', '.jpg', '.jpeg')):
                    print(f"🖼️  {file_path:50s} {size:>8,} bytes")
                else:
                    print(f"📄 {file_path:50s} {size:>8,} bytes")
            
            print()
            print("=" * 70)
            
            # Финальная оценка
            if all_required_exist and not has_nested_folders:
                print("✅ ВАЛИДАЦИЯ ПРОЙДЕНА! Виджет готов к загрузке в amoCRM!")
                return True
            else:
                print("❌ ВАЛИДАЦИЯ НЕ ПРОЙДЕНА!")
                if not all_required_exist:
                    print("   - Отсутствуют обязательные файлы")
                if has_nested_folders:
                    print("   - Неправильная структура папок")
                return False
                
    except zipfile.BadZipFile:
        print("❌ ОШИБКА: Файл не является корректным ZIP архивом!")
        return False
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        return False

if __name__ == "__main__":
    # Проверить timesheet_il_widget.zip
    zip_file = "timesheet_il_widget.zip"
    
    if len(sys.argv) > 1:
        zip_file = sys.argv[1]
    
    success = validate_widget_zip(zip_file)
    
    print()
    sys.exit(0 if success else 1)
