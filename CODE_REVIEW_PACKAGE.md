# 📋 CODE REVIEW REQUEST: amoCRM Widget

**Дата:** 11.08.2026  
**Версия:** 3.0.2  
**Цель:** Code review виджета учёта времени для amoCRM перед загрузкой в production

---

## 🎯 ЧТО НУЖНО ПРОВЕРИТЬ

1. **Совместимость с amoCRM API** - правильность использования AMOCRM.constant() и widget API
2. **Качество кода** - best practices JavaScript, потенциальные баги
3. **Безопасность** - XSS, CSRF, утечки данных
4. **Performance** - memory leaks, оптимизация AJAX запросов
5. **UX** - логика работы виджета, edge cases
6. **Готовность к production** - что надо исправить перед загрузкой в amoCRM

---

## 📦 СТРУКТУРА ВИДЖЕТА

```
timesheet_il_widget.zip (22.38 KB)
├── manifest.json (1.6 KB) - Конфигурация виджета
├── script.js (21.2 KB) - Основной код
├── styles.css (6.0 KB) - Стили
├── i18n/ - Локализации
│   ├── en.json
│   └── ru.json
└── images/ - Иконки и логотипы
```

---

## 📄 manifest.json

```json
{
  "widget": {
    "name": "widget.timesheet_il",
    "description": "Учёт рабочего времени сотрудников в режиме реального времени",
    "short_description": "Табель учёта рабочего времени",
    "version": "3.0.2",
    "interface_version": 2,
    "init_once": false,
    "locale": ["ru", "en"],
    "installation": true,
    "support": {
      "link": "https://example.com/support",
      "email": "support@example.com"
    }
  },
  "locations": [
    "advancedSettings"
  ],
  "settings": {
    "api_url": {
      "name": "settings.api_url",
      "type": "text"
    },
    "department_id": {
      "name": "settings.department_id",
      "type": "text"
    }
  },
  "tour": {
    "is_tour": true,
    "tour_images": {
      "ru": ["/images/tour_ru.png"],
      "en": ["/images/tour_en.png"]
    },
    "tour_description": "widget.tour_description"
  }
}
```

**Вопросы по manifest:**
1. Правильно ли выбрано `locations: ["advancedSettings"]`? Может лучше `["card-lead", "card-contact"]`?
2. `init_once: false` - это правильно для overlay виджета?

---

## 💻 script.js (ОСНОВНОЙ КОД)

### Структура кода (655 строк):

```javascript
define(['jquery'], function($) {
    var CustomWidget = function() {
        // Constructor
        this.API_URL = 'https://storage-turkey-multitask.ngrok-free.dev/api/v1';
        this.currentSession = null;
        this.updateTimer = null;
        this.sessionStart = null;
        this.overlayShown = false;
        
        this.callbacks = {
            render: function() { return true; },
            init: function() {
                // Инициализация виджета
                console.log('Timesheet Widget v3.0.2 initializing...');
                
                // Get user from amoCRM
                try {
                    widget.accountId = AMOCRM.constant('account').id;
                    widget.userId = AMOCRM.constant('user').id;
                    widget.userName = AMOCRM.constant('user').name;
                } catch (e) {
                    // Fallback для демо
                    widget.accountId = 'demo_account';
                    widget.userId = 1;
                    widget.userName = 'Demo User';
                }
                
                // Load settings
                var settings = widget.get_settings();
                if (settings && settings.api_url) {
                    widget.API_URL = settings.api_url;
                }
                
                // Load current session
                $.ajax({
                    url: widget.API_URL + '/sessions/current',
                    method: 'GET',
                    data: { account_id: widget.accountId, user_id: widget.userId },
                    success: function(response) {
                        if (response && response.session_id && response.status !== 'finished') {
                            widget.currentSession = response;
                            widget.sessionStart = new Date(response.start_time);
                        }
                        widget.createOverlay();
                        widget.updateOverlayState();
                    },
                    error: function() {
                        widget.currentSession = null;
                        widget.createOverlay();
                        widget.updateOverlayState();
                    }
                });
                
                widget.startUpdateTimer();
                return true;
            },
            destroy: function() {
                if (widget.updateTimer) clearInterval(widget.updateTimer);
                if (widget.removeOverlay) widget.removeOverlay();
                return true;
            }
        };
    };

    // Создание overlay (плавающей панели)
    CustomWidget.prototype.createOverlay = function() {
        var widget = this;
        
        if (this.overlayShown) return;
        this.overlayShown = true;
        
        var overlay = $('<div>')
            .attr('id', 'timesheet-overlay')
            .addClass('timesheet-overlay')
            .css({
                position: 'fixed',
                bottom: '20px',
                right: '20px',
                width: '280px',
                background: '#fff',
                borderRadius: '12px',
                boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
                zIndex: 999999,
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
            });
        
        var header = $('<div>')
            .addClass('timesheet-header')
            .css({
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                padding: '16px',
                borderRadius: '12px 12px 0 0',
                color: '#fff'
            })
            .html('<div style="font-size: 16px; font-weight: 600;">⏱️ Табель</div>');
        
        var content = $('<div>')
            .attr('id', 'timesheet-content')
            .css({ padding: '16px' });
        
        overlay.append(header).append(content);
        $('body').append(overlay);
        
        // Minimize button
        var minimizeBtn = $('<button>')
            .css({
                position: 'absolute',
                top: '12px',
                right: '12px',
                background: 'rgba(255,255,255,0.2)',
                border: 'none',
                borderRadius: '50%',
                width: '28px',
                height: '28px',
                cursor: 'pointer',
                color: '#fff',
                fontSize: '18px'
            })
            .html('−')
            .on('click', function() {
                $('#timesheet-content').slideToggle();
                $(this).html($(this).html() === '−' ? '+' : '−');
            });
        
        header.append(minimizeBtn);
        
        // Drag functionality
        var isDragging = false;
        var currentX, currentY, initialX, initialY;
        
        header.on('mousedown', function(e) {
            if ($(e.target).is('button')) return;
            isDragging = true;
            initialX = e.clientX - overlay.offset().left;
            initialY = e.clientY - overlay.offset().top;
        });
        
        $(document).on('mousemove', function(e) {
            if (!isDragging) return;
            e.preventDefault();
            currentX = e.clientX - initialX;
            currentY = e.clientY - initialY;
            overlay.css({ left: currentX + 'px', top: currentY + 'px', right: 'auto', bottom: 'auto' });
        });
        
        $(document).on('mouseup', function() {
            isDragging = false;
        });
        
        this.removeOverlay = function() {
            overlay.remove();
            widget.overlayShown = false;
        };
    };

    // Обновление состояния overlay
    CustomWidget.prototype.updateOverlayState = function() {
        var content = $('#timesheet-content');
        if (!content.length) return;
        
        content.empty();
        
        if (!this.currentSession || this.currentSession.status === 'finished') {
            // Not working
            this.renderIdleState(content);
        } else if (this.currentSession.status === 'working') {
            // Working
            this.renderWorkingState(content);
        } else if (this.currentSession.status === 'break') {
            // On break
            this.renderBreakState(content);
        }
    };

    // Idle state (не работает)
    CustomWidget.prototype.renderIdleState = function(container) {
        var widget = this;
        
        container.append(
            $('<div>').css({ textAlign: 'center', padding: '20px 0' }).html(
                '<div style="font-size: 48px; margin-bottom: 12px;">⏸️</div>' +
                '<div style="color: #6b7280; margin-bottom: 20px;">Рабочий день не начат</div>'
            )
        );
        
        var startBtn = $('<button>')
            .text('🚀 Начать работу')
            .css({
                width: '100%',
                padding: '14px',
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                fontSize: '15px',
                fontWeight: '600',
                cursor: 'pointer'
            })
            .on('click', function() {
                widget.startWork();
            });
        
        container.append(startBtn);
    };

    // Working state (работает)
    CustomWidget.prototype.renderWorkingState = function(container) {
        var widget = this;
        var elapsed = this.getElapsedTime();
        
        container.append(
            $('<div>').css({ marginBottom: '16px' }).html(
                '<div style="font-size: 14px; color: #6b7280; margin-bottom: 8px;">Рабочее время</div>' +
                '<div style="font-size: 32px; font-weight: 700; color: #10b981; font-family: monospace;">' +
                elapsed + '</div>' +
                '<div style="font-size: 12px; color: #10b981; margin-top: 4px;">● Идёт работа</div>'
            )
        );
        
        var buttonsRow = $('<div>').css({ display: 'flex', gap: '8px' });
        
        var breakBtn = $('<button>')
            .text('☕ Перерыв')
            .css({
                flex: '1',
                padding: '12px',
                background: '#fbbf24',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer'
            })
            .on('click', function() { widget.startBreak(); });
        
        var stopBtn = $('<button>')
            .text('⏹️ Завершить')
            .css({
                flex: '1',
                padding: '12px',
                background: '#ef4444',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer'
            })
            .on('click', function() { widget.finishWork(); });
        
        buttonsRow.append(breakBtn).append(stopBtn);
        container.append(buttonsRow);
    };

    // Break state (перерыв)
    CustomWidget.prototype.renderBreakState = function(container) {
        var widget = this;
        var elapsed = this.getElapsedTime();
        
        container.append(
            $('<div>').css({ marginBottom: '16px' }).html(
                '<div style="font-size: 14px; color: #6b7280; margin-bottom: 8px;">Перерыв</div>' +
                '<div style="font-size: 32px; font-weight: 700; color: #fbbf24; font-family: monospace;">' +
                elapsed + '</div>' +
                '<div style="font-size: 12px; color: #fbbf24; margin-top: 4px;">☕ На перерыве</div>'
            )
        );
        
        var resumeBtn = $('<button>')
            .text('▶️ Продолжить работу')
            .css({
                width: '100%',
                padding: '14px',
                background: '#10b981',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer'
            })
            .on('click', function() { widget.endBreak(); });
        
        container.append(resumeBtn);
    };

    // API Methods
    CustomWidget.prototype.startWork = function() {
        var widget = this;
        
        $.ajax({
            url: this.API_URL + '/sessions/start',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                account_id: this.accountId,
                user_id: this.userId,
                user_name: this.userName,
                department_id: this.departmentId || null
            }),
            success: function(response) {
                widget.currentSession = response;
                widget.sessionStart = new Date();
                widget.updateOverlayState();
                console.log('Session started:', response.session_id);
            },
            error: function(xhr) {
                alert('Ошибка при начале работы: ' + (xhr.responseJSON?.detail || 'Сервер недоступен'));
            }
        });
    };

    CustomWidget.prototype.startBreak = function() {
        var widget = this;
        
        $.ajax({
            url: this.API_URL + '/sessions/' + this.currentSession.session_id + '/break',
            method: 'POST',
            success: function(response) {
                widget.currentSession = response;
                widget.updateOverlayState();
                console.log('Break started');
            },
            error: function(xhr) {
                alert('Ошибка при начале перерыва');
            }
        });
    };

    CustomWidget.prototype.endBreak = function() {
        var widget = this;
        
        $.ajax({
            url: this.API_URL + '/sessions/' + this.currentSession.session_id + '/resume',
            method: 'POST',
            success: function(response) {
                widget.currentSession = response;
                widget.updateOverlayState();
                console.log('Work resumed');
            },
            error: function(xhr) {
                alert('Ошибка при возобновлении работы');
            }
        });
    };

    CustomWidget.prototype.finishWork = function() {
        var widget = this;
        
        if (!confirm('Завершить рабочий день?')) return;
        
        $.ajax({
            url: this.API_URL + '/sessions/' + this.currentSession.session_id + '/finish',
            method: 'POST',
            success: function(response) {
                alert('Рабочий день завершён! Всего отработано: ' + widget.formatDuration(response.total_seconds));
                widget.currentSession = null;
                widget.sessionStart = null;
                widget.updateOverlayState();
            },
            error: function(xhr) {
                alert('Ошибка при завершении работы');
            }
        });
    };

    // Helper methods
    CustomWidget.prototype.getElapsedTime = function() {
        if (!this.sessionStart) return '00:00:00';
        var now = new Date();
        var diff = Math.floor((now - this.sessionStart) / 1000);
        return this.formatDuration(diff);
    };

    CustomWidget.prototype.formatDuration = function(seconds) {
        var h = Math.floor(seconds / 3600);
        var m = Math.floor((seconds % 3600) / 60);
        var s = seconds % 60;
        return [h, m, s].map(v => String(v).padStart(2, '0')).join(':');
    };

    CustomWidget.prototype.startUpdateTimer = function() {
        var widget = this;
        this.updateTimer = setInterval(function() {
            if (widget.currentSession && widget.currentSession.status !== 'finished') {
                widget.updateOverlayState();
            }
        }, 1000);
    };

    return CustomWidget;
});
```

---

## 🔍 КРИТИЧНЫЕ ВОПРОСЫ ДЛЯ REVIEW

### 1. API Integration
```javascript
widget.accountId = AMOCRM.constant('account').id;
widget.userId = AMOCRM.constant('user').id;
```
❓ **Вопрос:** Правильно ли использовать `AMOCRM.constant()` в amoCRM виджетах? Это надёжный способ?

### 2. Error Handling
```javascript
try {
    widget.accountId = AMOCRM.constant('account').id;
} catch (e) {
    widget.accountId = 'demo_account';
}
```
❓ **Вопрос:** Достаточно ли такого fallback? Или нужно показывать ошибку пользователю?

### 3. Memory Leaks
```javascript
this.updateTimer = setInterval(function() {
    widget.updateOverlayState();
}, 1000);
```
❓ **Вопрос:** Таймер очищается в `destroy()`, но может ли быть утечка если виджет перезагрузится?

### 4. AJAX без токенов
```javascript
$.ajax({
    url: widget.API_URL + '/sessions/start',
    method: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({ account_id, user_id })
});
```
❓ **Вопрос:** Нет авторизации/токенов в AJAX. Это безопасно? Или надо добавить headers?

### 5. Overlay Z-Index
```javascript
.css({ zIndex: 999999 })
```
❓ **Вопрос:** `z-index: 999999` может конфликтовать с amoCRM UI. Какой правильный z-index?

### 6. Global jQuery
```javascript
define(['jquery'], function($) { ... });
```
❓ **Вопрос:** Правильно ли использовать глобальный jQuery в amoCRM? Версия совместимая?

### 7. Hardcoded API URL
```javascript
this.API_URL = 'https://storage-turkey-multitask.ngrok-free.dev/api/v1';
```
❓ **Вопрос:** Ngrok URL захардкожен. Это для dev/test? В production надо заменить?

### 8. Session Persistence
```javascript
// Load current session
$.ajax({ url: widget.API_URL + '/sessions/current' });
```
❓ **Вопрос:** Сессия грузится каждый раз при init. Если юзер закрыл вкладку и открыл снова - сессия восстановится?

---

## 🐛 ПОТЕНЦИАЛЬНЫЕ БАГИ

### Bug #1: Duplicate Overlay
```javascript
if (this.overlayShown) return; // Проверка есть, но при перезагрузке виджета?
```

### Bug #2: Timer не останавливается
```javascript
// Если пользователь закрыл карточку, но не вызвался destroy()?
```

### Bug #3: Нет проверки response
```javascript
success: function(response) {
    widget.currentSession = response; // Что если response = null?
}
```

### Bug #4: Confirm блокирует UI
```javascript
if (!confirm('Завершить рабочий день?')) return;
```

---

## 📝 РЕКОМЕНДАЦИИ ПО УЛУЧШЕНИЮ

### 1. Добавить debounce для AJAX
```javascript
// Избежать повторных запросов при быстрых кликах
```

### 2. Добавить retry logic
```javascript
// Если API недоступен, повторить попытку через N секунд
```

### 3. Использовать localStorage
```javascript
// Сохранять sessionStart локально для восстановления после перезагрузки
```

### 4. Добавить error boundary
```javascript
// Глобальный try-catch чтобы виджет не крашил всю страницу
```

### 5. Добавить loading states
```javascript
// Показывать спиннер при AJAX запросах
```

---

## ✅ ЧТО УЖЕ ХОРОШО

1. ✅ Чистая структура кода
2. ✅ Использование AMD (define)
3. ✅ Fallback для демо режима
4. ✅ Drag & drop для overlay
5. ✅ Минимизация панели
6. ✅ Форматирование времени
7. ✅ Cleanup в destroy()
8. ✅ Responsive дизайн

---

## 🎯 ГЛАВНЫЙ ВОПРОС

**Готов ли этот виджет к загрузке в amoCRM production?**

Если НЕТ - что КРИТИЧНО надо исправить в первую очередь?

---

## 📊 МЕТРИКИ КОДА

- **Строк кода:** 655
- **Функций:** 12
- **AJAX endpoints:** 5
- **Error handlers:** 4 (базовые)
- **Memory cleanup:** Есть (destroy)
- **Tests:** Нет (ручное тестирование)

---

## 🚀 КОНТЕКСТ ИСПОЛЬЗОВАНИЯ

**Виджет устанавливается в amoCRM и:**
1. Создаёт floating overlay внизу справа
2. Показывает текущее состояние (работа/перерыв/idle)
3. Общается с FastAPI backend (PostgreSQL)
4. Обновляется каждую секунду (таймер)
5. Drag & drop + минимизация

**Backend API:**
- POST /sessions/start
- POST /sessions/{id}/break
- POST /sessions/{id}/resume
- POST /sessions/{id}/finish
- GET /sessions/current

---

## 📞 ЗАПРОС НА CODE REVIEW

Прошу провести code review этого виджета с фокусом на:

1. **Совместимость с amoCRM** - правильность использования API
2. **Безопасность** - XSS, CSRF, утечки
3. **Баги** - потенциальные проблемы
4. **Best practices** - что улучшить
5. **Production readiness** - что КРИТИЧНО исправить

**Формат ответа:**
- 🔴 Критично (блокирует загрузку)
- 🟠 Важно (надо исправить скоро)
- 🟡 Желательно (можно потом)
- 🟢 Норм (всё ок)

Спасибо! 🙏
