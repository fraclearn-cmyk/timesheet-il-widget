# ⚡ БЫСТРЫЙ СТАРТ: РАЗВЁРТЫВАНИЕ НА СЕРВЕР

**За 10 шагов до production!**

---

## 📋 ЧЕКЛИСТ ПОДГОТОВКИ

Перед началом убедитесь, что у вас есть:
- [ ] Аккаунт на облачном сервере (DigitalOcean/Yandex Cloud)
- [ ] Купленный домен (api.ваш-домен.ru)
- [ ] Доступ к amoCRM (права администратора)
- [ ] SSH клиент (встроен в Windows)

---

## 🚀 10 ШАГОВ ДО PRODUCTION

### ШАГ 1: Создайте сервер (5 минут)

**DigitalOcean:**
1. Зарегистрируйтесь: https://www.digitalocean.com/
2. Create → Droplets
3. Выберите: Ubuntu 22.04, Frankfurt, $12/mo (2GB RAM)
4. Создайте SSH ключ или используйте пароль
5. Создайте → Скопируйте IP адрес

**Ваш IP:** `___________________`

---

### ШАГ 2: Настройте домен (10 минут)

1. Купите домен на REG.RU или Namecheap
2. В DNS настройках добавьте A-запись:
   ```
   Тип: A
   Имя: api
   Значение: ВАШ_IP_АДРЕС
   TTL: 3600
   ```
3. Подождите 5-30 минут
4. Проверьте: `ping api.ваш-домен.ru`

**Ваш домен:** `___________________`

---

### ШАГ 3: Подключитесь к серверу (1 минута)

На вашем компьютере (PowerShell):
```powershell
ssh root@ВАШ_IP
```

Введите "yes" при первом подключении.

---

### ШАГ 4: Настройте сервер автоматически (10 минут)

На сервере выполните:
```bash
# Скачать скрипт настройки
wget https://raw.githubusercontent.com/YOUR-REPO/deploy/server-setup.sh

# ИЛИ создайте файл вручную:
nano server-setup.sh
# Вставьте содержимое из deploy/server-setup.sh
# Ctrl+O, Enter, Ctrl+X

# Сделать исполняемым и запустить
chmod +x server-setup.sh
bash server-setup.sh
```

Скрипт установит: Docker, Docker Compose, Nginx, Certbot, UFW.

---

### ШАГ 5: Скопируйте код на сервер (5 минут)

На вашем компьютере:
```powershell
cd d:\табель

# Создать архив
tar -czf timesheet-app.tar.gz backend/ widget/ docker-compose.yml .env.example deploy/

# Скопировать на сервер
scp timesheet-app.tar.gz root@ВАШ_IP:/opt/timesheet/
```

На сервере:
```bash
cd /opt/timesheet
tar -xzf timesheet-app.tar.gz
rm timesheet-app.tar.gz
ls -la
```

---

### ШАГ 6: Настройте окружение (5 минут)

На сервере:
```bash
cd /opt/timesheet

# Создать .env из шаблона
cp deploy/.env.production.template .env

# Редактировать .env
nano .env
```

**Замените:**
1. `POSTGRES_PASSWORD` - на сильный пароль
2. `DATABASE_URL` - обновите с тем же паролем
3. `CORS_ORIGINS` - укажите ваш домен
4. `SECRET_KEY` - сгенерируйте:
   ```bash
   openssl rand -hex 32
   ```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

```bash
# Защитить файл
chmod 600 .env
```

---

### ШАГ 7: Настройте Nginx (5 минут)

```bash
# Создать конфигурацию из шаблона
cp /opt/timesheet/deploy/nginx-template.conf /etc/nginx/sites-available/timesheet

# Редактировать - заменить DOMAIN на ваш домен
nano /etc/nginx/sites-available/timesheet

# Заменить все "DOMAIN" на "api.ваш-домен.ru"
# Сохранить: Ctrl+O, Enter, Ctrl+X

# Активировать
ln -s /etc/nginx/sites-available/timesheet /etc/nginx/sites-enabled/

# Проверить и перезагрузить
nginx -t
systemctl reload nginx
```

---

### ШАГ 8: Получите SSL сертификат (3 минуты)

```bash
certbot --nginx -d api.ваш-домен.ru
```

Следуйте инструкциям:
1. Введите email
2. Согласитесь (Y)
3. Выберите опцию 2 (Redirect)

Проверьте: откройте `https://api.ваш-домен.ru` в браузере.

---

### ШАГ 9: Запустите приложение (5 минут)

```bash
cd /opt/timesheet

# Запустить контейнеры
docker-compose up -d

# Подождать 15 секунд
sleep 15

# Применить миграции
docker-compose exec backend alembic upgrade head

# Проверить статус
docker-compose ps

# Проверить работу
curl http://localhost:8000/health
```

Должно вернуть: `{"status":"healthy"}`

Проверьте в браузере:
- `https://api.ваш-домен.ru/health` ✅
- `https://api.ваш-домен.ru/docs` ✅

---

### ШАГ 10: Загрузите виджет в amoCRM (10 минут)

На вашем компьютере:
```powershell
cd d:\табель

# Пересобрать виджет с вашим доменом
.\build_widget.ps1 -ApiUrl "https://api.ваш-домен.ru/api/v1" -SupportEmail "support@ваша-компания.ru"
```

В amoCRM:
1. Настройки → Интеграции → Виджеты
2. Загрузить свой виджет
3. Выбрать: `timesheet_il_widget.zip`
4. Включить виджет
5. Выбрать разделы (лиды, контакты, компании, сделки)
6. Сохранить

**Тестируйте:**
1. Откройте любую карточку в amoCRM
2. Найдите виджет на боковой панели
3. Нажмите "Начать рабочий день"
4. Проверьте, что всё работает!

---

## ✅ ГОТОВО!

Если всё работает - поздравляю! 🎉

Виджет успешно развёрнут в production!

---

## 📊 ФИНАЛЬНАЯ ПРОВЕРКА

- [ ] Backend отвечает на https://api.ваш-домен.ru/health
- [ ] SSL сертификат работает (замочек в браузере)
- [ ] Виджет загружен в amoCRM
- [ ] Виджет отображается в карточках
- [ ] Кнопка "Начать день" работает
- [ ] Таймер считает время
- [ ] Данные сохраняются в БД

---

## 🔧 НАСТРОЙКА АВТОЗАПУСКА (Опционально)

```bash
# Создать systemd service
cat > /etc/systemd/system/timesheet.service << 'EOF'
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

[Install]
WantedBy=multi-user.target
EOF

# Активировать
systemctl daemon-reload
systemctl enable timesheet.service
```

---

## 💾 НАСТРОЙКА BACKUP (Опционально)

```bash
# Создать скрипт backup
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

## 📞 ПОЛЕЗНЫЕ КОМАНДЫ

```bash
# Проверить логи
docker-compose logs backend -f

# Перезапустить backend
docker-compose restart backend

# Остановить всё
docker-compose down

# Запустить всё
docker-compose up -d

# Проверить статус
docker-compose ps

# Подключиться к БД
docker-compose exec db psql -U postgres -d timesheet_db

# Проверить использование ресурсов
docker stats

# Проверить сертификат SSL
certbot certificates
```

---

## 🆘 ЕСЛИ ЧТО-ТО НЕ РАБОТАЕТ

### Проблема: Backend не отвечает
```bash
# Проверить логи
docker-compose logs backend --tail=50

# Перезапустить
docker-compose restart backend
```

### Проблема: SSL не работает
```bash
# Проверить Nginx
nginx -t
systemctl status nginx

# Переполучить сертификат
certbot --nginx -d api.ваш-домен.ru --force-renewal
```

### Проблема: CORS ошибка в браузере
```bash
# Проверить .env
cat /opt/timesheet/.env | grep CORS

# Должно содержать ваш домен и *.amocrm.ru
# После изменений:
docker-compose restart backend
```

---

## 📚 ПОДРОБНАЯ ДОКУМЕНТАЦИЯ

- **PRODUCTION_DEPLOYMENT.md** - Полное руководство (100+ страниц)
- **ARCHITECTURE_EXPLANATION_RU.md** - Объяснение архитектуры
- **LOCAL_TESTING_GUIDE.md** - Локальное тестирование

---

## 📈 СЛЕДУЮЩИЕ ШАГИ

1. **Мониторьте работу** первую неделю
2. **Соберите отзывы** от пользователей
3. **Настройте backup** (см. выше)
4. **Обучите команду** работе с виджетом

---

**Время развёртывания:** 60-90 минут  
**Стоимость:** ~$12-15/месяц  
**Результат:** Production-ready виджет ✅

**Создано:** 31 июля 2026  
**Версия:** 1.0.0
