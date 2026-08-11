#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Full Project Code Review Package
Собирает ВСЕ файлы проекта в один файл для DeepSeek
"""

import os
from pathlib import Path

# Базовая директория
BASE_DIR = Path(__file__).parent

# Файлы для включения
FILES_TO_INCLUDE = {
    # Widget
    'widget/manifest.json': 'Widget Config',
    'widget/script.js': 'Widget Main Code (655 lines)',
    'widget/styles.css': 'Widget Styles',
    'widget/i18n/ru.json': 'Widget RU Localization',
    'widget/i18n/en.json': 'Widget EN Localization',
    
    # Backend Core
    'backend/app/main.py': 'FastAPI Main App',
    'backend/app/core/config.py': 'Backend Config',
    'backend/app/core/database.py': 'Database Connection',
    'backend/app/core/rbac.py': 'RBAC System',
    
    # Backend Models
    'backend/app/models/__init__.py': 'Models Init',
    'backend/app/models/user.py': 'User Model',
    'backend/app/models/department.py': 'Department Model',
    'backend/app/models/work_session.py': 'Work Session Model',
    'backend/app/models/work_comment.py': 'Work Comment Model',
    'backend/app/models/rop_permission.py': 'ROP Permission Model',
    'backend/app/models/dashboard_settings.py': 'Dashboard Settings Model',
    
    # Backend API
    'backend/app/api/v1/__init__.py': 'API V1 Init',
    'backend/app/api/v1/sessions.py': 'Sessions API',
    'backend/app/api/v1/team.py': 'Team API',
    'backend/app/api/v1/activity.py': 'Activity API',
    'backend/app/api/v1/categories.py': 'Categories API',
    'backend/app/api/v1/settings.py': 'Settings API',
    'backend/app/api/v1/reports.py': 'Reports API',
    'backend/app/api/v1/endpoints/departments.py': 'Departments Endpoint',
    'backend/app/api/v1/endpoints/excel.py': 'Excel Export Endpoint',
    'backend/app/api/v1/endpoints/kpi.py': 'KPI Endpoint',
    
    # Backend Services
    'backend/app/services/kpi_service.py': 'KPI Service',
    'backend/app/services/excel_service.py': 'Excel Service',
    'backend/app/services/team_service.py': 'Team Service',
    
    # Backend Schemas
    'backend/app/schemas/department.py': 'Department Schema',
    'backend/app/schemas/excel.py': 'Excel Schema',
    'backend/app/schemas/kpi.py': 'KPI Schema',
    'backend/app/schemas/team.py': 'Team Schema',
    
    # Frontend HTML
    'frontend/index.html': 'Login Page',
    'frontend/personal.html': 'Personal Dashboard',
    'frontend/rop.html': 'ROP Dashboard',
    'frontend/admin.html': 'Admin Panel',
    'frontend/reports.html': 'Reports Page',
    
    # Frontend JS
    'frontend/assets/js/api-client.js': 'API Client',
    'frontend/assets/js/personal.js': 'Personal Dashboard JS',
    'frontend/assets/js/rop.js': 'ROP Dashboard JS',
    'frontend/assets/js/admin.js': 'Admin Panel JS',
    'frontend/assets/js/reports.js': 'Reports JS',
    
    # Frontend CSS
    'frontend/assets/css/personal.css': 'Personal CSS',
    'frontend/assets/css/rop.css': 'ROP CSS',
    'frontend/assets/css/admin.css': 'Admin CSS',
    'frontend/assets/css/reports.css': 'Reports CSS',
}

def read_file_safe(filepath):
    """Безопасное чтение файла"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"[ERROR reading file: {e}]"

def get_file_ext(filepath):
    """Получить расширение файла для подсветки"""
    ext = Path(filepath).suffix.lower()
    ext_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.json': 'json',
        '.html': 'html',
        '.css': 'css',
        '.md': 'markdown'
    }
    return ext_map.get(ext, '')

def generate_review_package():
    """Генерация полного review package"""
    
    output = []
    
    # Header
    output.append("# 🎯 ПОЛНЫЙ CODE REVIEW: Timesheet IL - ALL FILES\n")
    output.append("**Дата:** 11.08.2026\n")
    output.append("**Проект:** Full Stack система учёта рабочего времени для amoCRM\n")
    output.append("**Цель:** Comprehensive code review ВСЕГО проекта\n")
    output.append("\n---\n\n")
    
    # CRAFT Prompt
    output.append("## 📋 CRAFT ПРОМПТ ДЛЯ DEEPSEEK\n\n")
    output.append("```\n")
    output.append("Ты - Senior Full Stack разработчик + эксперт по amoCRM.\n\n")
    output.append("ЗАДАЧА: Полный code review проекта Timesheet IL.\n\n")
    output.append("Ниже предоставлен ВЕСЬ код проекта:\n")
    output.append("- Widget для amoCRM (manifest.json + script.js + styles.css + i18n)\n")
    output.append("- Backend FastAPI (models, API, services, schemas)\n")
    output.append("- Frontend (5 HTML страниц + JS + CSS)\n\n")
    output.append("ФОКУС АНАЛИЗА:\n")
    output.append("1. ✅ Совместимость с amoCRM API\n")
    output.append("2. ✅ Безопасность (XSS, CSRF, SQL injection)\n")
    output.append("3. ✅ Performance & Memory leaks\n")
    output.append("4. ✅ Best practices Python/JavaScript\n")
    output.append("5. ✅ Production readiness\n")
    output.append("6. ✅ Конфликты с amoCRM UI\n\n")
    output.append("ФОРМАТ ОТВЕТА:\n")
    output.append("Для КАЖДОГО файла с проблемами дай:\n\n")
    output.append("```\n")
    output.append("FILE: путь/к/файлу.ext\n")
    output.append("ISSUES:\n")
    output.append("🔴 КРИТИЧНО: Описание проблемы\n")
    output.append("🟠 ВАЖНО: Описание проблемы\n")
    output.append("🟡 ЖЕЛАТЕЛЬНО: Рекомендация\n\n")
    output.append("FIX:\n")
    output.append("[ПОЛНЫЙ ИСПРАВЛЕННЫЙ КОД ФАЙЛА]\n")
    output.append("```\n\n")
    output.append("ВАЖНО: Предоставь ГОТОВЫЙ код для копирования в VS Code!\n")
    output.append("```\n\n")
    output.append("---\n\n")
    
    # Statistics
    output.append("## 📊 СТАТИСТИКА ПРОЕКТА\n\n")
    output.append(f"**Файлов для review:** {len(FILES_TO_INCLUDE)}\n\n")
    output.append("**Структура:**\n")
    output.append("- Widget: 5 файлов (manifest, script, styles, i18n)\n")
    output.append("- Backend: 25 файлов (models, API, services, schemas)\n")
    output.append("- Frontend: 14 файлов (HTML, JS, CSS)\n")
    output.append("- **ИТОГО:** ~6,000 строк кода\n\n")
    output.append("---\n\n")
    
    # Files Content
    output.append("## 📄 ВЕСЬ КОД ПРОЕКТА\n\n")
    
    total_lines = 0
    files_read = 0
    
    for filepath, description in FILES_TO_INCLUDE.items():
        full_path = BASE_DIR / filepath
        
        if not full_path.exists():
            output.append(f"### ⚠️ {description}\n\n")
            output.append(f"**File:** `{filepath}`\n\n")
            output.append("```\n")
            output.append("[FILE NOT FOUND]\n")
            output.append("```\n\n")
            continue
        
        content = read_file_safe(full_path)
        lines = content.count('\n')
        total_lines += lines
        files_read += 1
        
        file_ext = get_file_ext(filepath)
        
        output.append(f"### {description}\n\n")
        output.append(f"**File:** `{filepath}` ({lines} lines)\n\n")
        output.append(f"```{file_ext}\n")
        output.append(content)
        output.append("\n```\n\n")
        output.append("---\n\n")
    
    # Footer
    output.append("## ✅ ИТОГО\n\n")
    output.append(f"**Файлов прочитано:** {files_read}/{len(FILES_TO_INCLUDE)}\n")
    output.append(f"**Строк кода:** {total_lines:,}\n\n")
    output.append("---\n\n")
    output.append("## 🚀 НАЧИНАЙ CODE REVIEW!\n\n")
    output.append("Жду детальный анализ с готовыми исправлениями для каждого файла! 🎉\n")
    
    return ''.join(output)

def main():
    """Main function"""
    print("=" * 70)
    print("  Generating Full Project Code Review Package")
    print("=" * 70)
    print()
    
    print("📁 Сканирование файлов...")
    print(f"   Файлов для включения: {len(FILES_TO_INCLUDE)}")
    print()
    
    print("📝 Генерация review package...")
    content = generate_review_package()
    
    output_file = BASE_DIR / 'COMPLETE_PROJECT_REVIEW.md'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    size_kb = len(content) / 1024
    lines = content.count('\n')
    
    print()
    print("=" * 70)
    print("  ✅ ГОТОВО!")
    print("=" * 70)
    print()
    print(f"📄 Файл: {output_file.name}")
    print(f"📏 Размер: {size_kb:.1f} KB")
    print(f"📊 Строк: {lines:,}")
    print()
    print("🚀 СЛЕДУЮЩИЕ ШАГИ:")
    print("   1. Откройте: code COMPLETE_PROJECT_REVIEW.md")
    print("   2. Скопируйте ВСЁ (Ctrl+A, Ctrl+C)")
    print("   3. Вставьте в DeepSeek: https://chat.deepseek.com")
    print("   4. Получите code review с готовыми исправлениями!")
    print()
    print("=" * 70)

if __name__ == "__main__":
    main()
