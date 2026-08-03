# ⚡ GITHUB - БЫСТРЫЙ СТАРТ

**За 5 минут загрузите код в GitHub!**

---

## 🚀 КОМАНДЫ ДЛЯ КОПИПАСТА

### 1. Создайте репозиторий на GitHub
- Перейдите: https://github.com/new
- Имя: `timesheet-il-widget`
- Visibility: **Private**
- НЕ добавляйте README, .gitignore, license
- Create repository
- **Скопируйте URL репозитория**

---

### 2. Выполните команды на вашем компьютере

```powershell
# Перейти в папку проекта
cd d:\табель

# Инициализировать Git (если ещё не сделано)
git init

# Добавить все файлы
git add .

# Проверить что .env НЕ добавлен
git status
# Если есть .env - выполните: git rm --cached .env

# Создать первый коммит
git commit -m "Initial commit: Timesheet IL Widget v1.0"

# Переименовать ветку в main
git branch -M main

# Подключить GitHub (ЗАМЕНИТЕ URL НА ВАШ!)
git remote add origin https://github.com/ВАШ-USERNAME/timesheet-il-widget.git

# Загрузить код
git push -u origin main
```

**Готово!** Откройте `https://github.com/ВАШ-USERNAME/timesheet-il-widget`

---

## 📋 ЧАСТЫЕ КОМАНДЫ

### Обновить код на GitHub:
```powershell
git add .
git commit -m "Описание изменений"
git push
```

### Получить изменения с GitHub:
```powershell
git pull
```

### Посмотреть статус:
```powershell
git status
```

### История изменений:
```powershell
git log --oneline
```

---

## 🔒 ПРОВЕРКА БЕЗОПАСНОСТИ

После загрузки проверьте на GitHub:
- ✅ Код загружен
- ✅ .gitignore на месте
- ❌ .env файла НЕТ
- ❌ Паролей и ключей НЕТ

---

## 🌐 ИСПОЛЬЗОВАНИЕ НА СЕРВЕРЕ

### Клонирование:
```bash
git clone https://github.com/ВАШ-USERNAME/timesheet-il-widget.git
cd timesheet-il-widget
```

### Обновление:
```bash
git pull
```

---

## 📚 ПОЛНАЯ ДОКУМЕНТАЦИЯ

Подробности: **GITHUB_SETUP.md**

---

**Время:** 5 минут  
**Результат:** Код в GitHub ✅
