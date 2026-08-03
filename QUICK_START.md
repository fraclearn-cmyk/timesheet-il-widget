# 🚀 Быстрый старт разработки

**Проект:** Виджет "Табель IL"  
**Статус:** День 1 начат  
**Дата:** 09.07.2026

---

## ✅ УЖЕ СОЗДАНО

- [x] Структура проекта (папки)
- [x] README.md (полная документация)
- [x] DEVELOPMENT_PLAN.md (план на 12 дней)
- [x] docker-compose.yml ✅ **ТОЛЬКО ЧТО**

---

## 📝 СЛЕДУЮЩИЕ ФАЙЛЫ (создать сейчас)

### 1. Конфигурация (.env.example)
```bash
# d:\виджеты\timesheet-il-widget\.env.example
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/timesheet_db
POSTGRES_DB=timesheet_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_PORT=5432

AMOCRM_CLIENT_ID=your_client_id_here
AMOCRM_CLIENT_SECRET=your_client_secret_here
AMOCRM_REDIRECT_URI=https://your-domain.com/oauth/callback

SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

BACKEND_PORT=8000
POLLING_INTERVAL=15
INACTIVITY_TIMEOUT=300
```

### 2. Зависимости (requirements.txt)
```python
# d:\виджеты\timesheet-il-widget\backend\requirements.txt
fastapi==0.110.0
uvicorn[standard]==0.27.1
sqlalchemy==2.0.27
alembic==1.13.1
psycopg2-binary==2.9.9
pydantic==2.6.1
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
openpyxl==3.1.2
httpx==0.26.0
python-dotenv==1.0.1
```

### 3. Dev зависимости (requirements-dev.txt)
```python
# d:\виджеты\timesheet-il-widget\backend\requirements-dev.txt
pytest==8.0.0
pytest-cov==4.1.0
pytest-asyncio==0.23.3
black==24.1.1
flake8==7.0.0
mypy==1.8.0
```

### 4. Dockerfile
```dockerfile
# d:\виджеты\timesheet-il-widget\backend\Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 5. .dockerignore
```
# d:\виджеты\timesheet-il-widget\backend\.dockerignore
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv
pip-log.txt
pip-delete-this-directory.txt
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.git
.gitignore
.mypy_cache
.pytest_cache
.hypothesis
```

### 6. .gitignore
```
# d:\виджеты\timesheet-il-widget\.gitignore
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv
.env
*.db
*.sqlite3
.DS_Store
*.log
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/
exports/
postgres_data/
```

---

## 🏗️ ОСНОВНЫЕ ФАЙЛЫ КОДА

### Core files (создать дальше):

#### 1. backend/app/__init__.py
```python
"""Timesheet IL Widget Backend Application"""
__version__ = "1.0.0"
```

#### 2. backend/app/main.py
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import timesheet, activity
from app.core.config import settings
from app.core.database import engine, Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Timesheet IL Widget API",
    description="amoCRM timesheet widget with activity tracking",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(timesheet.router, prefix="/api/v1/timesheet", tags=["timesheet"])
app.include_router(activity.router, prefix="/api/v1/activity", tags=["activity"])

@app.get("/")
async def root():
    return {"message": "Timesheet IL Widget API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

#### 3. backend/app/core/config.py
```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # amoCRM
    AMOCRM_CLIENT_ID: str
    AMOCRM_CLIENT_SECRET: str
    AMOCRM_REDIRECT_URI: str
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Application
    POLLING_INTERVAL: int = 15
    INACTIVITY_TIMEOUT: int = 300
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

#### 4. backend/app/core/database.py
```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 🎯 ЧТО ДЕЛАТЬ ДАЛЬШЕ

### Этап 1: Завершить настройку (сегодня)
1. Создать все конфигурационные файлы выше
2. Создать core файлы (config.py, database.py, security.py)
3. Настроить Alembic для миграций
4. Протестировать запуск Docker

### Этап 2: Модели БД (завтра)
1. Создать 6 моделей SQLAlchemy
2. Создать миграции Alembic
3. Применить миграции
4. Создать Pydantic schemas

### Этап 3-6: Реализация функционала
Следовать плану из DEVELOPMENT_PLAN.md

---

## 🚀 КОМАНДЫ ДЛЯ ЗАПУСКА

```bash
# 1. Создать .env из примера
cp .env.example .env

# 2. Отредактировать .env (добавить реальные ключи amoCRM)

# 3. Запустить Docker
docker-compose up -d

# 4. Проверить логи
docker-compose logs -f backend

# 5. Применить миграции
docker-compose exec backend alembic upgrade head

# 6. Открыть API docs
# http://localhost:8000/docs
```

---

## 📊 ПРОГРЕСС

**День 1:**
- [x] docker-compose.yml создан
- [ ] .env.example
- [ ] requirements.txt
- [ ] Dockerfile
- [ ] .dockerignore
- [ ] .gitignore
- [ ] Core files (config, database, security)
- [ ] Alembic setup

**Осталось на сегодня:** ~3-4 часа работы

---

## 💡 РЕКОМЕНДАЦИЯ

**Сейчас создать в таком порядке:**
1. .env.example
2. requirements.txt + requirements-dev.txt
3. backend/Dockerfile
4. backend/.dockerignore
5. .gitignore (root)
6. backend/app/__init__.py
7. backend/app/core/__init__.py
8. backend/app/core/config.py
9. backend/app/core/database.py
10. backend/app/main.py

Затем запустить `docker-compose up` и проверить что всё работает.

---

**Статус:** 🟡 В процессе (День 1 из 12)  
**Следующий файл:** .env.example
