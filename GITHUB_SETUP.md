# 🐙 ПЕРЕНОС ПРОЕКТА В GITHUB

**Цель:** Загрузить код в GitHub для тестирования в amoCRM перед production

---

## 📋 ЧТО МЫ БУДЕМ ДЕЛАТЬ

1. Создать репозиторий на GitHub
2. Инициализировать Git локально
3. Загрузить код
4. Проверить что секреты не загружены
5. Использовать для тестирования в amoCRM

**Время:** 15-20 минут

---

## ✅ ШАГ 1: СОЗДАНИЕ РЕПОЗИТОРИЯ НА GITHUB

### 1.1. Зарегистрируйтесь на GitHub

Если у вас ещё нет аккаунта:
- Перейдите на https://github.com/
- Нажмите "Sign up"
- Следуйте инструкциям

### 1.2. Создайте новый репозиторий

1. Войдите в GitHub
2. Нажмите **"+"** в правом верхнем углу → **"New repository"**
3. Заполните форму:
   ```
   Repository name: timesheet-il-widget
   Description: amoCRM Timesheet Widget with Activity Tracking
   Visibility: Private (рекомендуется) или Public
   
   НЕ СТАВЬТЕ галочки:
   ❌ Add a README file
   ❌ Add .gitignore
   ❌ Choose a license
   ```
4. Нажмите **"Create repository"**

### 1.3. Скопируйте URL репозитория

После создания скопируйте URL (будет вида):
```
https://github.com/ваш-username/timesheet-il-widget.git
```

---

## ✅ ШАГ 2: ПРОВЕРКА GIT НА ВАШЕМ КОМПЬЮТЕРЕ

### 2.1. Проверьте установку Git

Откройте PowerShell:
```powershell
git --version
```

Должно показать версию. Если нет - установите:
- Скачайте: https://git-scm.com/download/win
- Установите с настройками по умолчанию

### 2.2. Настройте Git (если первый раз)

```powershell
git config --global user.name "Ваше Имя"
git config --global user.email "your@email.com"
```

---

## ✅ ШАГ 3: ИНИЦИАЛИЗАЦИЯ РЕПОЗИТОРИЯ ЛОКАЛЬНО

### 3.1. Перейдите в папку проекта

```powershell
cd d:\табель
```

### 3.2. Инициализируйте Git

```powershell
# Инициализировать репозиторий
git init

# Проверить статус
git status
```

### 3.3. Добавьте все файлы

```powershell
# Добавить все файлы (кроме .gitignore)
git add .

# Проверить что добавлено
git status
```

### 3.4. ВАЖНО: Проверьте что секреты НЕ добавлены

```powershell
# Проверить список файлов
git status

# Убедитесь что НЕТ:
# - .env (должен быть в .gitignore)
# - *.pem, *.key файлов
# - паролей и токенов
```

Если `.env` показывается - удалите его из git:
```powershell
git rm --cached .env
```

---

## ✅ ШАГ 4: СОЗДАНИЕ КОММИТА

```powershell
# Создать первый коммит
git commit -m "Initial commit: Timesheet IL Widget v1.0"

# Переименовать ветку в main (если нужно)
git branch -M main
```

---

## ✅ ШАГ 5: ЗАГРУЗКА НА GITHUB

### 5.1. Подключите удалённый репозиторий

```powershell
# Замените URL на ваш!
git remote add origin https://github.com/ваш-username/timesheet-il-widget.git

# Проверить
git remote -v
```

### 5.2. Загрузите код

```powershell
# Первая загрузка
git push -u origin main
```

**При первой загрузке:**
- Может появиться окно авторизации GitHub
- Войдите в аккаунт
- Разрешите доступ

### 5.3. Проверьте на GitHub

Откройте в браузере:
```
https://github.com/ваш-username/timesheet-il-widget
```

Должны увидеть все файлы!

---

## ✅ ШАГ 6: СОЗДАНИЕ README ДЛЯ GITHUB

Уже есть файл `README.md` в корне проекта. Он будет отображаться на главной странице GitHub.

Проверьте что он содержит нужную информацию.

---

## ✅ ШАГ 7: ИСПОЛЬЗОВАНИЕ ДЛЯ ТЕСТИРОВАНИЯ В amoCRM

### 7.1. Получите raw URL файлов

Для скачивания скриптов прямо на сервер:

**Формат:**
```
https://raw.githubusercontent.com/ваш-username/timesheet-il-widget/main/путь/к/файлу
```

**Примеры:**
```
https://raw.githubusercontent.com/username/timesheet-il-widget/main/deploy/server-setup.sh
https://raw.githubusercontent.com/username/timesheet-il-widget/main/docker-compose.yml
```

### 7.2. Скачивание на сервер

Теперь на сервере можно делать:
```bash
# Скачать отдельный файл
wget https://raw.githubusercontent.com/username/timesheet-il-widget/main/deploy/server-setup.sh

# Или клонировать весь репозиторий
git clone https://github.com/username/timesheet-il-widget.git
cd timesheet-il-widget
```

### 7.3. Клонирование для развёртывания

На сервере:
```bash
# Создать директорию
mkdir -p /opt/timesheet
cd /opt/timesheet

# Клонировать репозиторий
git clone https://github.com/username/timesheet-il-widget.git .

# Создать .env из шаблона
cp deploy/.env.production.template .env
nano .env  # Заполнить параметры

# Запустить
docker-compose up -d
```

---

## 📊 ПРОВЕРКА БЕЗОПАСНОСТИ

### Что ДОЛЖНО быть в репозитории:
✅ Исходный код (backend/, widget/)  
✅ Документация (*.md файлы)  
✅ Конфигурации (docker-compose.yml)  
✅ Шаблоны (.env.example, .env.production.template)  
✅ Скрипты (*.sh, *.ps1)  

### Что НЕ ДОЛЖНО быть в репозитории:
❌ .env файл с реальными паролями  
❌ Файлы баз данных (*.db, *.sql)  
❌ Приватные ключи (*.pem, *.key)  
❌ Логи (*.log)  
❌ Backup файлы  
❌ Собранный виджет (timesheet_il_widget.zip)  

### Проверьте на GitHub:

1. Откройте репозиторий
2. Посмотрите список файлов
3. Убедитесь что `.env` там НЕТ
4. Проверьте что есть `.env.example` или `.env.production.template`

---

## 🔄 ОБНОВЛЕНИЕ КОДА В GITHUB

### Когда вносите изменения:

```powershell
cd d:\табель

# Посмотреть изменения
git status

# Добавить изменённые файлы
git add .

# Создать коммит
git commit -m "Описание изменений"

# Загрузить на GitHub
git push
```

### Пример workflow:

```powershell
# 1. Изменили код виджета
# 2. Добавить в git
git add widget/script.js

# 3. Коммит
git commit -m "Fix: исправлена работа таймера"

# 4. Загрузить
git push
```

---

## 🌿 РАБОТА С ВЕТКАМИ (ОПЦИОНАЛЬНО)

Для безопасного тестирования:

```powershell
# Создать ветку для тестирования
git checkout -b testing

# Внести изменения
# ...

# Коммит
git add .
git commit -m "Test: новая функция"

# Загрузить ветку
git push -u origin testing

# Вернуться на main
git checkout main

# Слить изменения (если тесты прошли)
git merge testing
git push
```

---

## 📋 ПОЛЕЗНЫЕ GIT КОМАНДЫ

### Базовые:
```powershell
# Статус репозитория
git status

# История коммитов
git log --oneline

# Посмотреть изменения
git diff

# Отменить изменения в файле
git checkout -- filename

# Посмотреть удалённые репозитории
git remote -v
```

### Работа с удалённым репозиторием:
```powershell
# Получить изменения с GitHub
git pull

# Загрузить изменения на GitHub
git push

# Клонировать репозиторий
git clone https://github.com/username/repo.git
```

### Работа с файлами:
```powershell
# Удалить файл из git (но оставить локально)
git rm --cached filename

# Переименовать файл
git mv oldname newname

# Добавить конкретный файл
git add path/to/file
```

---

## 🔗 ИСПОЛЬЗОВАНИЕ В PRODUCTION DEPLOYMENT

Теперь в `PRODUCTION_DEPLOYMENT.md` можно использовать:

### Вместо SCP копирования:

**Было:**
```bash
scp timesheet-app.tar.gz root@IP:/opt/timesheet/
```

**Стало:**
```bash
cd /opt/timesheet
git clone https://github.com/username/timesheet-il-widget.git .
```

### Преимущества:
✅ Легче обновлять (`git pull`)  
✅ Видна история изменений  
✅ Можно откатить к предыдущей версии  
✅ Не нужно создавать архивы  

---

## 🎯 WORKFLOW ДЛЯ ТЕСТИРОВАНИЯ В amoCRM

### 1. Локальная разработка и тестирование
```powershell
# На вашем компьютере
cd d:\табель

# Тестируйте локально с ngrok
.\start_local_testing.ps1
```

### 2. Загрузка изменений в GitHub
```powershell
git add .
git commit -m "Update: улучшения виджета"
git push
```

### 3. Развёртывание на тестовом сервере
```bash
# На тестовом сервере
cd /opt/timesheet
git pull  # Получить изменения
docker-compose restart backend  # Перезапустить
```

### 4. Тестирование в amoCRM
- Пересобрать виджет с URL тестового сервера
- Загрузить в amoCRM
- Протестировать

### 5. Если всё ОК → Production
- Создать release на GitHub
- Развернуть на production сервере
- Загрузить финальный виджет в amoCRM

---

## 🏷️ СОЗДАНИЕ RELEASES (ОПЦИОНАЛЬНО)

Для версионирования:

### На GitHub:
1. Перейдите в репозиторий
2. Нажмите **"Releases"** → **"Create a new release"**
3. Заполните:
   ```
   Tag: v1.0.0
   Title: Timesheet IL Widget v1.0.0
   Description: Первый стабильный релиз
   ```
4. Можете приложить файлы (например, собранный виджет)
5. Нажмите **"Publish release"**

### В коде:
```powershell
# Создать тег
git tag -a v1.0.0 -m "Release v1.0.0"

# Загрузить теги
git push --tags
```

---

## 🔒 ПРИВАТНЫЙ vs ПУБЛИЧНЫЙ РЕПОЗИТОРИЙ

### Private (рекомендуется):
✅ Код виден только вам  
✅ Можно пригласить конкретных людей  
✅ Безопасно для коммерческих проектов  
❌ Требует авторизации для клонирования  

### Public:
✅ Бесплатно любые размеры  
✅ Можно показать в портфолио  
✅ Open source сообщество  
❌ Код виден всем  

**Для вашего проекта:** Лучше Private, так как это коммерческий виджет.

---

## 📞 ЧАСТЫЕ ВОПРОСЫ

### Q: Как удалить файл, который случайно загрузил?
```powershell
# Удалить из git
git rm --cached filename

# Добавить в .gitignore
echo "filename" >> .gitignore

# Коммит и пуш
git commit -m "Remove sensitive file"
git push
```

### Q: Как изменить последний коммит?
```powershell
# Изменить сообщение последнего коммита
git commit --amend -m "Новое сообщение"

# Добавить файлы к последнему коммиту
git add forgotten-file
git commit --amend --no-edit
```

### Q: Как откатить изменения?
```powershell
# Отменить все локальные изменения
git reset --hard HEAD

# Откатить к конкретному коммиту
git reset --hard COMMIT_HASH

# Откатить последний коммит (но оставить изменения)
git reset --soft HEAD~1
```

### Q: Как посмотреть, что изменилось?
```powershell
# Посмотреть изменения
git diff

# Посмотреть изменения конкретного файла
git diff filename

# Посмотреть изменения между коммитами
git diff COMMIT1 COMMIT2
```

---

## ✅ ЧЕКЛИСТ ПЕРЕНОСА В GITHUB

- [ ] Создан репозиторий на GitHub
- [ ] Установлен Git на компьютере
- [ ] Настроен user.name и user.email
- [ ] Создан .gitignore файл
- [ ] Инициализирован git в проекте
- [ ] Проверено что .env НЕ добавлен
- [ ] Создан первый коммит
- [ ] Подключен удалённый репозиторий
- [ ] Код загружен на GitHub
- [ ] Проверено на GitHub что всё на месте
- [ ] Проверено что секреты не загружены

---

## 🎉 ГОТОВО!

Теперь ваш код в GitHub и вы можете:
- ✅ Легко клонировать на сервер
- ✅ Делиться кодом с командой
- ✅ Отслеживать изменения
- ✅ Создавать релизы
- ✅ Откатываться к предыдущим версиям

**Следующий шаг:** Используйте GitHub URL в `PRODUCTION_DEPLOYMENT.md` для упрощения развёртывания!

---

**Создано:** 31 июля 2026  
**Версия:** 1.0.0  
**Проект:** Timesheet IL Widget
