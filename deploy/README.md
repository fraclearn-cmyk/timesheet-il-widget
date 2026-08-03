# 📦 Deploy Files для Production

Эта папка содержит все необходимые файлы для развёртывания на production сервер.

---

## 📁 Содержимое

### 🔧 Скрипты

**server-setup.sh**
- Автоматическая настройка нового сервера Ubuntu 22.04
- Устанавливает: Docker, Docker Compose, Nginx, Certbot, UFW
- Настраивает базовую безопасность
- Использование: `bash server-setup.sh`

### 📝 Шаблоны конфигураций

**.env.production.template**
- Шаблон файла окружения для production
- Скопируйте в `.env` и заполните своими значениями
- Содержит комментарии для каждого параметра

**nginx-template.conf**
- Шаблон конфигурации Nginx
- Замените `DOMAIN` на ваш реальный домен
- Копируйте в `/etc/nginx/sites-available/`

---

## 🚀 Быстрый старт

### 1. Подготовьте сервер

```bash
# На сервере (Ubuntu 22.04)
bash server-setup.sh
```

### 2. Скопируйте код

```bash
# На вашем компьютере
cd d:\табель
tar -czf timesheet-app.tar.gz backend/ widget/ docker-compose.yml .env.example deploy/
scp timesheet-app.tar.gz root@YOUR_IP:/opt/timesheet/

# На сервере
cd /opt/timesheet
tar -xzf timesheet-app.tar.gz
```

### 3. Настройте окружение

```bash
# На сервере
cd /opt/timesheet
cp deploy/.env.production.template .env
nano .env  # Заполните параметры
chmod 600 .env
```

### 4. Настройте Nginx

```bash
cp deploy/nginx-template.conf /etc/nginx/sites-available/timesheet
nano /etc/nginx/sites-available/timesheet  # Замените DOMAIN
ln -s /etc/nginx/sites-available/timesheet /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### 5. Получите SSL

```bash
certbot --nginx -d api.your-domain.com
```

### 6. Запустите приложение

```bash
cd /opt/timesheet
docker-compose up -d
sleep 15
docker-compose exec backend alembic upgrade head
```

### 7. Проверьте

```bash
curl https://api.your-domain.com/health
```

---

## 📚 Документация

Подробные инструкции см. в:
- **../DEPLOYMENT_QUICKSTART.md** - Быстрый старт (10 шагов)
- **../PRODUCTION_DEPLOYMENT.md** - Полное руководство
- **../ARCHITECTURE_EXPLANATION_RU.md** - Объяснение архитектуры

---

## ⚙️ Параметры конфигурации

### Обязательные параметры .env:

- `POSTGRES_PASSWORD` - Пароль базы данных (сильный!)
- `DATABASE_URL` - URL подключения к БД
- `CORS_ORIGINS` - Разрешённые домены (ваш домен + amoCRM)
- `SECRET_KEY` - Секретный ключ (генерируйте: `openssl rand -hex 32`)

### Nginx конфигурация:

- Замените `DOMAIN` на ваш реальный домен
- После получения SSL раскомментируйте HTTPS секцию

---

## 🔒 Безопасность

После развёртывания:
1. ✅ Защитите .env файл: `chmod 600 .env`
2. ✅ Настройте UFW (сделано в server-setup.sh)
3. ✅ Получите SSL сертификат
4. ✅ Используйте сильные пароли
5. ⚠️ Рассмотрите отключение root login по SSH

---

## 💾 Backup

Создайте скрипт backup:

```bash
cat > /opt/timesheet/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/timesheet/backups"
DATE=$(date +%Y-%m-%d_%H-%M-%S)
mkdir -p $BACKUP_DIR
docker-compose exec -T db pg_dump -U postgres timesheet_db | gzip > "$BACKUP_DIR/backup_$DATE.sql.gz"
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete
EOF

chmod +x /opt/timesheet/backup.sh

# Добавить в cron (каждый день в 3:00)
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/timesheet/backup.sh") | crontab -
```

---

## 🆘 Troubleshooting

### Контейнеры не запускаются
```bash
docker-compose logs
docker-compose down
docker-compose up -d
```

### SSL не работает
```bash
certbot certificates
certbot --nginx -d api.your-domain.com --force-renewal
```

### CORS ошибки
```bash
# Проверьте .env
cat .env | grep CORS
# Должно содержать ваш домен и *.amocrm.ru
docker-compose restart backend
```

---

## 📞 Поддержка

Вопросы? Читайте:
- PRODUCTION_DEPLOYMENT.md - полное руководство
- DEPLOYMENT_QUICKSTART.md - быстрый старт
- ARCHITECTURE_EXPLANATION_RU.md - как всё устроено

---

**Версия:** 1.0.0  
**Дата:** 31 июля 2026  
**Проект:** Timesheet IL Widget
