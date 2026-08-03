# 🚀 РАЗВЁРТЫВАНИЕ НА PRODUCTION СЕРВЕРЕ

**Дата:** 31 июля 2026  
**Цель:** Перенести виджет на постоянный сервер для работы в production

---

## 📋 СОДЕРЖАНИЕ

1. [Выбор и подготовка сервера](#1-выбор-и-подготовка-сервера)
2. [Покупка и настройка домена](#2-покупка-и-настройка-домена)
3. [Установка необходимого ПО](#3-установка-необходимого-по)
4. [Копирование кода на сервер](#4-копирование-кода-на-сервер)
5. [Настройка окружения](#5-настройка-окружения)
6. [Настройка HTTPS (SSL)](#6-настройка-https-ssl)
7. [Запуск приложения](#7-запуск-приложения)
8. [Пересборка и загрузка виджета](#8-пересборка-и-загрузка-виджета)
9. [Настройка мониторинга](#9-настройка-мониторинга)
10. [Резервное копирование](#10-резервное-копирование)

---

## ОБЩИЙ ПЛАН

**Время на развёртывание:** 2-4 часа  
**Требуемые навыки:** Базовые знания Linux, SSH  
**Стоимость:** ~$12-15/месяц (облачный сервер)

---

## 1. ВЫБОР И ПОДГОТОВКА СЕРВЕРА

### 1.1. Рекомендуемые хостинг-провайдеры

#### Вариант А: DigitalOcean (рекомендуется)
- **Сайт:** https://www.digitalocean.com/
- **Стоимость:** $12/месяц (2GB RAM)
- **Плюсы:** Простота, надёжность, хорошая документация
- **Минусы:** Нужна банковская карта

#### Вариант Б: Yandex Cloud
- **Сайт:** https://cloud.yandex.ru/
- **Стоимость:** ~₽800/месяц
- **Плюсы:** Российский провайдер, оплата в рублях
- **Минусы:** Более сложный интерфейс

#### Вариант В: Timeweb
- **Сайт:** https://timeweb.com/
- **Стоимость:** ~₽500/месяц
- **Плюсы:** Дешёво, русский интерфейс
- **Минусы:** Меньшая надёжность

### 1.2. Минимальные требования к серверу

```
ОС: Ubuntu 22.04 LTS (рекомендуется)
CPU: 2 ядра
RAM: 2 GB минимум (4 GB рекомендуется)
Диск: 20 GB SSD
IP: Статический (выдаётся автоматически)
```

### 1.3. Создание сервера (DigitalOcean)

**Шаг 1:** Зарегистрируйтесь на https://www.digitalocean.com/

**Шаг 2:** Создайте Droplet
- Нажмите "Create" → "Droplets"
- Выберите регион: **Frankfurt** или **Amsterdam** (ближе к России)
- Выберите образ: **Ubuntu 22.04 LTS**
- Выберите план: **Basic** → **$12/mo** (2GB RAM)
- Выберите метод аутентификации: **SSH keys** (рекомендуется) или **Password**

**Шаг 3:** Создайте SSH ключ (если выбрали SSH keys)

На вашем компьютере (Windows PowerShell):
```powershell
# Создать SSH ключ
ssh-keygen -t rsa -b 4096 -C "your@email.com"

# Путь по умолчанию: C:\Users\User\.ssh\id_rsa
# Нажмите Enter для значений по умолчанию

# Посмотреть публичный ключ
cat C:\Users\User\.ssh\id_rsa.pub
```

Скопируйте содержимое и добавьте в DigitalOcean.

**Шаг 4:** Создайте Droplet
- Нажмите "Create Droplet"
- Дождитесь создания (~1 минута)
- Скопируйте IP адрес сервера

### 1.4. Первое подключение к серверу

```powershell
# Подключитесь по SSH
ssh root@ВАШ_IP_АДРЕС

# Например:
ssh root@159.89.123.45

# При первом подключении появится вопрос о fingerprint - напишите 'yes'
```

Вы подключены к серверу! Теперь все команды выполняются на удалённом сервере.

---

## 2. ПОКУПКА И НАСТРОЙКА ДОМЕНА

### 2.1. Покупка домена

**Где купить:**
- **REG.RU** - https://www.reg.ru/ (~₽200/год для .ru)
- **Namecheap** - https://www.namecheap.com/ (~$10/год для .com)
- **Cloudflare** - https://www.cloudflare.com/ (~$10/год + бесплатный SSL)

**Рекомендация:** `api.ваша-компания.ru` или `timesheet.ваша-компания.ru`

### 2.2. Настройка DNS записей

После покупки домена, настройте DNS:

```
Тип    Имя              Значение               TTL
----------------------------------------------------
A      api              ВАШ_IP_СЕРВЕРА        3600
A      @                ВАШ_IP_СЕРВЕРА        3600
```

**Пример:**
```
A      api.example.com  159.89.123.45         3600
```

**Проверка (через 5-30 минут после настройки):**
```bash
# На вашем компьютере
ping api.ваш-домен.ru
```

Должен показать IP вашего сервера.

---

## 3. УСТАНОВКА НЕОБХОДИМОГО ПО

Выполните на сервере (после подключения по SSH).

### 3.1. Обновление системы

```bash
# Обновить список пакетов
apt update

# Обновить систему
apt upgrade -y

# Установить базовые утилиты
apt install -y curl wget git nano htop
```

### 3.2. Установка Docker

```bash
# Установить Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Проверить установку
docker --version

# Должно показать: Docker version 24.x.x
```

### 3.3. Установка Docker Compose

```bash
# Установить Docker Compose
apt install -y docker-compose

# ИЛИ более новая версия:
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Проверить установку
docker-compose --version
```

### 3.4. Установка Nginx (для SSL и прокси)

```bash
# Установить Nginx
apt install -y nginx

# Запустить Nginx
systemctl start nginx
systemctl enable nginx

# Проверить статус
systemctl status nginx
```

### 3.5. Установка Certbot (для SSL)

```bash
# Установить Certbot
apt install -y certbot python3-certbot-nginx

# Проверить установку
certbot --version
```

---

## 4. КОПИРОВАНИЕ КОДА НА СЕРВЕР

### 4.1. Создание структуры каталогов

На сервере:
```bash
# Создать директорию для проекта
mkdir -p /opt/timesheet
cd /opt/timesheet
```

### 4.2. Вариант А: Копирование через Git (рекомендуется)

Если у вас есть Git репозиторий:

```bash
# На сервере
cd /opt/timesheet
git clone https://ваш-репозиторий.git .

# Если нужна авторизация, используйте токен
```

### 4.3. Вариант Б: Копирование через SCP

На вашем компьютере (PowerShell):

```powershell
# Создать архив проекта (без node_modules, .git и т.д.)
# На вашем компьютере в папке проекта:

# Создать список файлов для копирования
$files = @(
    "backend/*",
    "widget/*",
    "docker-compose.yml",
    ".env.example"
)

# Создать временный архив
tar -czf timesheet-app.tar.gz backend/ widget/ docker-compose.yml .env.example

# Скопировать на сервер
scp timesheet-app.tar.gz root@ВАШ_IP:/opt/timesheet/

# Удалить временный архив
rm timesheet-app.tar.gz
```

На сервере:
```bash
# Распаковать архив
cd /opt/timesheet
tar -xzf timesheet-app.tar.gz
rm timesheet-app.tar.gz

# Проверить структуру
ls -la
```

### 4.4. Проверка структуры

Должно быть:
```
/opt/timesheet/
├── backend/
│   ├── app/
│   ├── migrations/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── alembic.ini
├── widget/
│   ├── script.js
│   ├── styles.css
│   ├── manifest.json
│   └── i18n/
├── docker-compose.yml
└── .env.example
```

---

## 5. НАСТРОЙКА ОКРУЖЕНИЯ

### 5.1. Создание .env файла

```bash
cd /opt/timesheet

# Скопировать пример
cp .env.example .env

# Редактировать файл
nano .env
```

Содержимое `.env`:
```env
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=СИЛЬНЫЙ_ПАРОЛЬ_ЗДЕСЬ_123
POSTGRES_DB=timesheet_db
DATABASE_URL=postgresql://postgres:СИЛЬНЫЙ_ПАРОЛЬ_ЗДЕСЬ_123@db:5432/timesheet_db

# API
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=False

# CORS - ВАЖНО!
CORS_ORIGINS=["https://api.ваш-домен.ru","https://*.amocrm.ru","https://*.amocrm.com"]

# Security
SECRET_KEY=ГЕНЕРИРУЙТЕ_СЛУЧАЙНЫЙ_КЛЮЧ_ЗДЕСЬ_64_СИМВОЛА_МИНИМУМ
```

**Генерация секретного ключа:**
```bash
# Сгенерировать случайный ключ
openssl rand -hex 32
```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

### 5.2. Настройка прав доступа

```bash
# Защитить .env файл
chmod 600 .env

# Проверить
ls -la .env
# Должно быть: -rw------- (только root может читать)
```

---

## 6. НАСТРОЙКА HTTPS (SSL)

### 6.1. Настройка Nginx как обратного прокси

```bash
# Создать конфигурацию Nginx
nano /etc/nginx/sites-available/timesheet
```

Содержимое файла:
```nginx
server {
    listen 80;
    server_name api.ваш-домен.ru;

    # Временно для получения SSL
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Перенаправление на HTTPS (будет активировано после получения сертификата)
    # location / {
    #     return 301 https://$server_name$request_uri;
    # }

    # Временно проксируем напрямую
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Активировать конфигурацию:
```bash
# Создать символическую ссылку
ln -s /etc/nginx/sites-available/timesheet /etc/nginx/sites-enabled/

# Проверить конфигурацию
nginx -t

# Перезагрузить Nginx
systemctl reload nginx
```

### 6.2. Получение SSL сертификата

```bash
# Получить сертификат Let's Encrypt
certbot --nginx -d api.ваш-домен.ru

# Следуйте инструкциям:
# 1. Введите email
# 2. Согласитесь с условиями (Y)
# 3. Выберите опцию 2 (Redirect - перенаправлять HTTP на HTTPS)
```

Certbot автоматически:
- Получит сертификат
- Обновит конфигурацию Nginx
- Настроит автообновление сертификата

### 6.3. Проверка SSL

```bash
# Проверить сертификат
certbot certificates

# Проверить автообновление
certbot renew --dry-run
```

В браузере откройте: `https://api.ваш-домен.ru`

Должна появиться ошибка 502 (это нормально, backend ещё не запущен).

---

## 7. ЗАПУСК ПРИЛОЖЕНИЯ

### 7.1. Сборка и запуск Docker контейнеров

```bash
cd /opt/timesheet

# Запустить контейнеры
docker-compose up -d

# Проверить статус
docker-compose ps

# Должно показать:
# backend  Up  0.0.0.0:8000->8000/tcp
# db       Up  5432/tcp
```

### 7.2. Применение миграций БД

```bash
# Подождать 10 секунд для запуска БД
sleep 10

# Применить миграции
docker-compose exec backend alembic upgrade head

# Должно показать:
# INFO  [alembic.runtime.migration] Running upgrade -> xxx
# INFO  [alembic.runtime.migration] Running upgrade xxx -> yyy
```

### 7.3. Проверка работы

```bash
# Проверить логи backend
docker-compose logs backend --tail=50

# Проверить логи БД
docker-compose logs db --tail=20

# Проверить через curl
curl http://localhost:8000/health

# Должно вернуть: {"status":"healthy"}
```

### 7.4. Проверка через браузер

Откройте в браузере:
- `https://api.ваш-домен.ru/health` - должно вернуть `{"status":"healthy"}`
- `https://api.ваш-домен.ru/docs` - должна открыться документация Swagger

**Если всё работает** - backend успешно развёрнут! ✅

---

## 8. ПЕРЕСБОРКА И ЗАГРУЗКА ВИДЖЕТА

### 8.1. Пересборка виджета с production URL

На вашем компьютере (Windows):

```powershell
cd d:\табель

# Пересобрать виджет с вашим доменом
.\build_widget.ps1 -ApiUrl "https://api.ваш-домен.ru/api/v1" -SupportEmail "support@ваша-компания.ru"

# Пример:
.\build_widget.ps1 -ApiUrl "https://api.example.com/api/v1" -SupportEmail "support@example.com"
```

Должен создаться файл: `timesheet_il_widget.zip`

### 8.2. Загрузка в amoCRM

1. Откройте amoCRM
2. Перейдите: **Настройки → Интеграции → Виджеты**
3. Нажмите **"Загрузить свой виджет"**
4. Выберите файл: `timesheet_il_widget.zip`
5. Дождитесь проверки (~10-30 секунд)

### 8.3. Настройка виджета

1. **Включите виджет** - тумблер "Вкл"
2. **Выберите разделы:**
   - ✅ Карточка лида
   - ✅ Карточка контакта
   - ✅ Карточка компании
   - ✅ Карточка сделки
3. Нажмите **"Сохранить"**

### 8.4. Тестирование

1. Откройте любую карточку в amoCRM
2. Найдите виджет на правой панели
3. Нажмите **"Начать рабочий день"**
4. Проверьте, что:
   - Таймер работает
   - Данные сохраняются
   - Нет ошибок в консоли (F12)

**Если всё работает** - виджет успешно интегрирован! ✅

---

## 9. НАСТРОЙКА МОНИТОРИНГА

### 9.1. Автозапуск при перезагрузке

```bash
# Создать systemd service
nano /etc/systemd/system/timesheet.service
```

Содержимое:
```ini
[Unit]
Description=Timesheet IL Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/timesheet
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Активировать:
```bash
# Перезагрузить systemd
systemctl daemon-reload

# Включить автозапуск
systemctl enable timesheet.service

# Проверить статус
systemctl status timesheet.service
```

### 9.2. Настройка логирования

```bash
# Создать директорию для логов
mkdir -p /var/log/timesheet

# Настроить ротацию логов
nano /etc/logrotate.d/timesheet
```

Содержимое:
```
/var/log/timesheet/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
}
```

### 9.3. Простой мониторинг

Создать скрипт проверки:
```bash
nano /opt/timesheet/healthcheck.sh
```

Содержимое:
```bash
#!/bin/bash

# Проверка здоровья приложения
HEALTH_URL="http://localhost:8000/health"

response=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ "$response" -eq 200 ]; then
    echo "$(date): Service is healthy" >> /var/log/timesheet/health.log
else
    echo "$(date): Service is DOWN! Response: $response" >> /var/log/timesheet/health.log
    # Опционально: перезапуск
    # cd /opt/timesheet && docker-compose restart backend
fi
```

Сделать исполняемым:
```bash
chmod +x /opt/timesheet/healthcheck.sh
```

Добавить в cron (проверка каждые 5 минут):
```bash
crontab -e

# Добавить строку:
*/5 * * * * /opt/timesheet/healthcheck.sh
```

---

## 10. РЕЗЕРВНОЕ КОПИРОВАНИЕ

### 10.1. Скрипт backup базы данных

```bash
nano /opt/timesheet/backup.sh
```

Содержимое:
```bash
#!/bin/bash

# Настройки
BACKUP_DIR="/opt/timesheet/backups"
DATE=$(date +%Y-%m-%d_%H-%M-%S)
DB_NAME="timesheet_db"
DB_USER="postgres"
RETENTION_DAYS=7

# Создать директорию для backup
mkdir -p $BACKUP_DIR

# Создать backup
docker-compose exec -T db pg_dump -U $DB_USER $DB_NAME | gzip > "$BACKUP_DIR/backup_$DATE.sql.gz"

# Удалить старые backup (старше 7 дней)
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "$(date): Backup created: backup_$DATE.sql.gz" >> /var/log/timesheet/backup.log
```

Сделать исполняемым:
```bash
chmod +x /opt/timesheet/backup.sh
```

### 10.2. Автоматический backup

Добавить в cron (каждый день в 3:00 ночи):
```bash
crontab -e

# Добавить строку:
0 3 * * * /opt/timesheet/backup.sh
```

### 10.3. Восстановление из backup

При необходимости восстановить:
```bash
# Список backup
ls -lh /opt/timesheet/backups/

# Восстановить из backup
gunzip < /opt/timesheet/backups/backup_2026-07-31_03-00-00.sql.gz | docker-compose exec -T db psql -U postgres -d timesheet_db
```

---

## ✅ ЧЕКЛИСТ РАЗВЁРТЫВАНИЯ

### Сервер:
- [ ] Создан сервер (DigitalOcean/Yandex Cloud)
- [ ] Подключение по SSH работает
- [ ] Установлен Docker
- [ ] Установлен Docker Compose
- [ ] Установлен Nginx
- [ ] Установлен Certbot

### Домен и SSL:
- [ ] Куплен домен
- [ ] Настроены DNS записи (A запись)
- [ ] Домен резолвится в IP сервера
- [ ] Получен SSL сертификат
- [ ] HTTPS работает

### Приложение:
- [ ] Код скопирован на сервер
- [ ] Создан .env файл
- [ ] Запущены Docker контейнеры
- [ ] Применены миграции БД
- [ ] Backend отвечает на /health
- [ ] API docs доступны (/docs)

### Виджет:
- [ ] Виджет пересобран с production URL
- [ ] Загружен в amoCRM
- [ ] Настроен и включен
- [ ] Протестирован в карточках
- [ ] Данные сохраняются в БД

### Мониторинг и backup:
- [ ] Настроен автозапуск
- [ ] Настроено логирование
- [ ] Настроен healthcheck
- [ ] Настроен автоматический backup
- [ ] Протестировано восстановление

---

## 📊 ПОЛЕЗНЫЕ КОМАНДЫ

### Управление контейнерами:
```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Перезапуск
docker-compose restart backend

# Логи
docker-compose logs backend -f

# Статус
docker-compose ps
```

### Работа с БД:
```bash
# Подключиться к БД
docker-compose exec db psql -U postgres -d timesheet_db

# Запустить миграцию
docker-compose exec backend alembic upgrade head

# Создать backup
docker-compose exec db pg_dump -U postgres timesheet_db > backup.sql
```

### Nginx:
```bash
# Проверить конфигурацию
nginx -t

# Перезагрузить
systemctl reload nginx

# Логи
tail -f /var/log/nginx/error.log
```

### SSL:
```bash
# Обновить сертификат вручную
certbot renew

# Проверить сертификаты
certbot certificates
```

### Мониторинг:
```bash
# Использование ресурсов
docker stats

# Использование диска
df -h

# Нагрузка на систему
htop

# Логи системы
journalctl -u timesheet.service -f
```

---

## 🔒 БЕЗОПАСНОСТЬ

### Что уже реализовано:
✅ HTTPS с Let's Encrypt  
✅ CORS настроен только для amoCRM  
✅ База данных недоступна извне  
✅ .env файл защищён  

### Дополнительные меры:

#### 1. Настройка Firewall (UFW)
```bash
# Установить UFW
apt install -y ufw

# Разрешить SSH
ufw allow 22/tcp

# Разрешить HTTP и HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Включить firewall
ufw enable

# Проверить статус
ufw status
```

#### 2. Отключение root login по SSH
```bash
# Создать нового пользователя
adduser admin
usermod -aG sudo admin
usermod -aG docker admin

# Скопировать SSH ключи
mkdir -p /home/admin/.ssh
cp /root/.ssh/authorized_keys /home/admin/.ssh/
chown -R admin:admin /home/admin/.ssh

# Отключить root login
nano /etc/ssh/sshd_config

# Изменить:
PermitRootLogin no

# Перезапустить SSH
systemctl restart sshd
```

#### 3. Fail2ban (защита от brute-force)
```bash
# Установить
apt install -y fail2ban

# Запустить
systemctl enable fail2ban
systemctl start fail2ban
```

---

## 🆘 РЕШЕНИЕ ПРОБЛЕМ

### Проблема 1: Контейнеры не запускаются

```bash
# Проверить логи
docker-compose logs

# Проверить порты
netstat -tulpn | grep :8000

# Освободить порт если занят
kill -9 $(lsof -t -i:8000)
```

### Проблема 2: SSL не работает

```bash
# Проверить Nginx
nginx -t
systemctl status nginx

# Проверить сертификат
certbot certificates

# Переполучить сертификат
certbot delete --cert-name api.ваш-домен.ru
certbot --nginx -d api.ваш-домен.ru
```

### Проблема 3: CORS ошибки

```bash
# Проверить .env файл
cat /opt/timesheet/.env | grep CORS

# Должно быть:
# CORS_ORIGINS=["https://api.ваш-домен.ru","https://*.amocrm.ru","https://*.amocrm.com"]

# После изменений перезапустить
docker-compose restart backend
```

### Проблема 4: База данных не отвечает

```bash
# Проверить статус
docker-compose ps db

# Проверить логи
docker-compose logs db

# Перезапустить
docker-compose restart db

# Подождать 10 секунд
sleep 10

# Проверить подключение
docker-compose exec db psql -U postgres -c "SELECT 1;"
```

---

## 📈 МАСШТАБИРОВАНИЕ

Если сервер начнёт не справляться:

### 1. Увеличить ресурсы
- Увеличить RAM до 4GB или 8GB
- Добавить CPU ядра

### 2. Оптимизация
- Добавить Redis для кэширования
- Настроить connection pooling для БД
- Оптимизировать запросы

### 3. Мониторинг производительности
```bash
# Установить мониторинг
apt install -y prometheus node-exporter
```

---

## 📞 ПОСЛЕ РАЗВЁРТЫВАНИЯ

### Что делать дальше:

1. **Мониторить работу** первые дни
2. **Проверить backup** - восстановить тестовый backup
3. **Обучить пользователей** работе с виджетом
4. **Собирать отзывы** и улучшать

### Регулярное обслуживание:

- **Еженедельно:** Проверять логи, дисковое пространство
- **Ежемесячно:** Обновлять систему (`apt update && apt upgrade`)
- **Каждые 3 месяца:** Проверять backup, тестировать восстановление

---

**Время на развёртывание:** 2-4 часа  
**Результат:** Полностью рабочее production окружение ✅  
**Следующий шаг:** Мониторинг и сбор обратной связи

Удачи с развёртыванием! 🚀
