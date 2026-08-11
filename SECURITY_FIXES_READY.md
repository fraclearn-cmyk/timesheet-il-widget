# 🔐 ГОТОВЫЕ SECURITY FIXES - ПРИМЕНИТЬ ВРУЧНУЮ

**Дата:** 11.08.2026  
**Статус:** Готово к применению

---

## ✅ УЖЕ ПРИМЕНЕНО (Автоматически)

1. ✅ **backend/app/core/config.py** - Pydantic validation
2. ✅ **backend/app/main.py** - CORS + Security headers + Rate limiting
3. ✅ **.env.example** - Configuration template

---

## ⏳ ТРЕБУЕТСЯ ПРИМЕНИТЬ ВРУЧНУЮ

### 🔴 КРИТИЧНО #1: widget/script.js - Убрать hardcoded URL

**Проблема:** Строка 6 содержит hardcoded URL к ngrok

**КАК ИСПРАВИТЬ:**

Откройте `widget/script.js` и замените строку 6:

**БЫЛО:**
```javascript
this.API_URL = 'https://storage-turkey-multitask.ngrok-free.dev/api/v1';
```

**СТАЛО:**
```javascript
this.API_URL = null; // Will be loaded from widget settings
```

Также убедитесь, что в `callbacks.init()` есть обязательная проверка (строки 32-36):

```javascript
// Load custom settings if provided
var settings = widget.get_settings();
if (settings && settings.api_url) {
    widget.API_URL = settings.api_url;
} else {
    console.error('API URL not configured in widget settings!');
    widget.showError('Please configure API URL in widget settings');
    return;
}
```

---

### 🔴 КРИТИЧНО #2: backend/app/api/v1/sessions.py - Input Validation

**Проблема:** Отсутствует валидация входных данных

**КАК ИСПРАВИТЬ:**

Откройте `backend/app/api/v1/sessions.py` и добавьте в начало файла:

```python
from pydantic import BaseModel, Field, validator
from typing import Optional
import re

class SessionCreateRequest(BaseModel):
    account_id: str = Field(..., min_length=1, max_length=100)
    user_id: int = Field(..., gt=0)
    
    @validator('account_id')
    def validate_account_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Invalid account_id format')
        return v

class SessionUpdateRequest(BaseModel):
    status: Optional[str] = Field(None, regex='^(active|paused|finished)$')
    comment: Optional[str] = Field(None, max_length=500)
    
    @validator('comment')
    def sanitize_comment(cls, v):
        if v:
            # Remove HTML tags
            return re.sub(r'<[^>]+>', '', v)
        return v
```

Затем в endpoint'ах используйте эти схемы вместо прямых параметров.

---

### 🔴 КРИТИЧНО #3: backend/app/services/team_service.py - SQL Injection

**Проблема:** Прямая конкатенация SQL (если используется raw SQL)

**КАК ИСПРАВИТЬ:**

Проверьте файл `backend/app/services/team_service.py`. Если есть raw SQL запросы типа:

```python
# ❌ ПЛОХО
query = f"SELECT * FROM users WHERE name = '{user_name}'"
```

Замените на параметризованные запросы:

```python
# ✅ ХОРОШО
from sqlalchemy import text

query = text("SELECT * FROM users WHERE name = :name")
result = db.execute(query, {"name": user_name})
```

Или используйте SQLAlchemy ORM:

```python
# ✅ ОТЛИЧНО
from sqlalchemy.orm import Session
from app.models import User

users = db.query(User).filter(User.name == user_name).all()
```

---

### 🟠 ВАЖНО #4: frontend/index.html - XSS Protection

**Проблема:** Отсутствует CSP meta tag

**КАК ИСПРАВИТЬ:**

Откройте `frontend/index.html` и добавьте в `<head>`:

```html
<meta http-equiv="Content-Security-Policy" content="
    default-src 'self';
    script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
    style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
    font-src 'self' https://fonts.gstatic.com;
    img-src 'self' data: https:;
    connect-src 'self' https://your-api-domain.com;
">
<meta http-equiv="X-Content-Type-Options" content="nosniff">
<meta http-equiv="X-Frame-Options" content="DENY">
```

---

### 🟠 ВАЖНО #5: Создать backend/app/services/session_service.py

**Зачем:** Вынести бизнес-логику из API endpoints

**КАК СОЗДАТЬ:**

Создайте новый файл `backend/app/services/session_service.py`:

```python
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.work_session import WorkSession
from app.schemas.session import SessionCreate, SessionUpdate
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class SessionService:
    """Business logic for work sessions"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_current_session(
        self, 
        account_id: str, 
        user_id: int
    ) -> Optional[WorkSession]:
        """Get active or paused session for user"""
        try:
            session = self.db.query(WorkSession).filter(
                WorkSession.account_id == account_id,
                WorkSession.user_id == user_id,
                WorkSession.status.in_(['active', 'paused'])
            ).first()
            return session
        except Exception as e:
            logger.error(f"Error getting current session: {e}")
            return None
    
    def create_session(
        self, 
        account_id: str, 
        user_id: int,
        user_name: str
    ) -> WorkSession:
        """Create new work session"""
        try:
            # Check for existing active session
            existing = self.get_current_session(account_id, user_id)
            if existing:
                raise ValueError("Active session already exists")
            
            # Create new session
            session = WorkSession(
                account_id=account_id,
                user_id=user_id,
                user_name=user_name,
                start_time=datetime.utcnow(),
                status='active'
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            
            logger.info(f"Session created: {session.session_id}")
            return session
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating session: {e}")
            raise
    
    def update_session(
        self, 
        session_id: int,
        update_data: SessionUpdate
    ) -> Optional[WorkSession]:
        """Update existing session"""
        try:
            session = self.db.query(WorkSession).filter(
                WorkSession.session_id == session_id
            ).first()
            
            if not session:
                return None
            
            # Update fields
            for key, value in update_data.dict(exclude_unset=True).items():
                setattr(session, key, value)
            
            if update_data.status == 'finished':
                session.end_time = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(session)
            
            logger.info(f"Session updated: {session_id}")
            return session
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating session: {e}")
            raise
    
    def finish_session(self, session_id: int) -> Optional[WorkSession]:
        """Finish work session"""
        return self.update_session(
            session_id, 
            SessionUpdate(status='finished', end_time=datetime.utcnow())
        )
```

---

## 📝 CHECKLIST ДЛЯ ПРИМЕНЕНИЯ

- [ ] 1. Открыть `widget/script.js` и убрать hardcoded URL
- [ ] 2. Добавить валидацию в `backend/app/api/v1/sessions.py`
- [ ] 3. Проверить `backend/app/services/team_service.py` на SQL injection
- [ ] 4. Добавить CSP в `frontend/index.html`
- [ ] 5. Создать `backend/app/services/session_service.py`
- [ ] 6. Пересобрать виджет: `.\build_widget.ps1`
- [ ] 7. Сделать git commit
- [ ] 8. Протестировать всё

---

## 🚀 ПОСЛЕ ПРИМЕНЕНИЯ

```bash
# 1. Проверить изменения
git status
git diff

# 2. Пересобрать виджет
.\build_widget.ps1 -ApiUrl "YOUR_PRODUCTION_API_URL"

# 3. Commit + Push
git add -A
git commit -m "🔒 Apply remaining security fixes from DeepSeek review"
git push origin main

# 4. Протестировать
python validate_widget_zip.py
```

---

## ❓ НУЖНА ПОМОЩЬ?

Если файл слишком большой для ручного редактирования, я могу:
1. Создать скрипт Python для автоматической замены
2. Создать новые файлы с исправлениями (widget_FIXED.js)
3. Применить через Git patch

**Просто скажите что предпочитаете!**

---

**Файл создан:** 11.08.2026  
**Backup существует:** `backup_before_fixes_20260811_190825`
