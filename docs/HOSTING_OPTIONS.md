# Варианты размещения

Актуальность цен и ограничений: 5 октября 2026 года. Проекту нужен постоянно работающий FastAPI-процесс с фоновым ingestion worker и PostgreSQL. Бесплатный web-сервис, который засыпает без входящих запросов, прекращает сбор данных и поэтому не подходит для рабочего табеля на 40 аккаунтов.

## Локальный сервер для проверки

Локальное окружение запускается без Docker:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1
```

Запуск создаёт отдельную PostgreSQL 15 на `127.0.0.1:55432`, применяет миграции до `014` и поднимает API на `http://127.0.0.1:8000`. Сбор amoCRM отключён, чтобы локальный smoke не изменял реальные данные.

Для проверки из amoCRM нужен публичный HTTPS-адрес. Бесплатный Cloudflare Quick Tunnel выдаёт временный `trycloudflare.com` URL без аккаунта и домена. Он предназначен только для разработки, меняет hostname после перезапуска, не имеет SLA и ограничен 200 одновременными запросами. Для стабильного адреса нужен именованный Cloudflare Tunnel и собственный домен.

Источник: [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

## Бесплатные серверы

| Вариант | Ограничения | Вывод для 40 аккаунтов |
|---|---|---|
| Oracle Cloud Always Free A1 | До 2 OCPU и 12 ГБ RAM суммарно, 200 ГБ block volume; ARM; возможен дефицит свободных VM и изъятие простаивающего экземпляра | Единственный реалистичный бесплатный сервер для Docker Compose, но без гарантии доступности |
| Google Cloud Free e2-micro | Одна VM в отдельных регионах США, 30 ГБ диска и 1 ГБ исходящего трафика; очень малая производительность | Недостаточно для FastAPI, worker и PostgreSQL на 40 аккаунтов |
| Railway Free | $1 кредита в месяц после trial, до 1 vCPU/0,5 ГБ RAM и 0,5 ГБ volume | Для постоянного приложения и PostgreSQL бесплатного кредита недостаточно |
| Koyeb Free | Web 0,1 vCPU/512 МБ засыпает через час; worker запрещён; бесплатная БД имеет только 5 активных часов в месяц | Постоянный ingestion невозможен |
| Render Free | Web засыпает через 15 минут; PostgreSQL 1 ГБ истекает через 30 дней и не имеет backup | Непригоден для постоянного табеля |

Официальные источники: [Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), [Google Cloud Free](https://docs.cloud.google.com/free/docs/free-cloud-features), [Railway](https://docs.railway.com/pricing/plans), [Koyeb instances](https://www.koyeb.com/docs/reference/instances), [Koyeb databases](https://www.koyeb.com/docs/databases), [Render Free](https://render.com/docs/free).

Практический бесплатный путь: сначала локальный backend через временный Cloudflare Tunnel, затем Oracle A1, если в выбранном регионе доступна Always Free VM. Для production нужен мониторинг и внешняя резервная копия; бесплатная VM остаётся менее надёжной, чем платный VPS.

## Beget

Beget тарифицирует VPS посуточно. Для расчёта используется 30 дней и публичный IPv4 по 5 ₽ в день.

| Сценарий | Состав | Расчёт | Итого |
|---|---|---:|---:|
| Минимальный пилот | Один VPS 2 CPU, 4 ГБ RAM, 40 ГБ NVMe; backend и PostgreSQL вместе | `(33 + 5) × 30` | **1 140 ₽/мес.** |
| Единый сервер с запасом | Один VPS 4 CPU, 6 ГБ RAM, 80 ГБ NVMe | `(68 + 5) × 30` | **2 190 ₽/мес.** |
| Рекомендуемый для 40 аккаунтов | VPS 2 CPU/4 ГБ + DBaaS PostgreSQL 15.2, 2 CPU/4 ГБ/40 ГБ | `1 140 + 45 × 30` | **2 490 ₽/мес.** |

Первый вариант дешевле и подходит для controlled pilot, но приложение и база конкурируют за 4 ГБ памяти. Разделение приложения и управляемой базы лучше соответствует исходному sizing, упрощает backup и уменьшает риск потери всей системы при сбое одной VM.

Beget включает автоматические резервные копии VPS; DBaaS заявляет автоматические backup и uptime 99,98%. Docker и Let's Encrypt не требуют отдельной лицензии. Домен оплачивается отдельно, если подходящего домена ещё нет.

Официальные источники: [VPS Beget](https://beget.com/ru/vps), [DBaaS Beget](https://beget.com/ru/cloud/dbaas), [PostgreSQL в Beget](https://beget.com/ru/kb/manual/cloud-postgresql), [S3-хранилище](https://beget.com/ru/cloud/storage), [Let's Encrypt](https://beget.com/ru/ssl/letsencrypt), [домены](https://beget.com/ru/domains).

## Рекомендация

1. Провести локальный smoke через временный HTTPS tunnel.
2. Для бесплатного длительного теста попробовать Oracle A1 и заранее настроить backup вне VM.
3. Если нужна предсказуемая работа в РФ, начать с единого Beget VPS за 1 140 ₽/мес.
4. После подтверждения реальной нагрузки 40 аккаунтов перейти на Beget VPS + DBaaS за 2 490 ₽/мес. либо увеличить единый VPS по фактическим метрикам.
