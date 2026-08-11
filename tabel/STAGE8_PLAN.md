# ЭТАП 8: FRONTEND - ОТЧЁТЫ UI

**Оценка:** 1-2 дня (для MVP: 1-2 часа)  
**Приоритет:** P1 (высокий)  
**Статус:** Планирование 🚀

---

## 🎯 ЦЕЛИ

1. Интерфейс генерации отчётов
2. Фильтры (период, подразделение, пользователь, тип)
3. Preview отчёта
4. Экспорт в Excel
5. Интеграция с backend Excel API

---

## 📋 ЗАДАЧИ

### 1. HTML Структура
**frontend/reports.html**
- Header
- Фильтры (период, подразделение, пользователь, тип отчёта)
- Кнопка генерации
- Preview таблица
- Кнопка экспорта Excel
- Loading состояния

### 2. CSS Стили
**frontend/assets/css/reports.css**
- Фильтры стили
- Preview таблица
- Кнопки
- Loading spinner
- Responsive

### 3. JavaScript Логика
**frontend/assets/js/reports.js**
- Фильтры логика
- Генерация preview
- Экспорт Excel
- API интеграция
- Error handling

---

## 🎨 ИНТЕРФЕЙС ОТЧЁТОВ

```
┌─────────────────────────────────────────────────────┐
│ 📊 Генерация отчётов                                │
├─────────────────────────────────────────────────────┤
│ Фильтры:                                            │
│ Период: [от][до] или [Сегодня][Неделя][Месяц]     │
│ Подразделение: [Select]                             │
│ Пользователь: [Select]                              │
│ Тип отчёта: [Select - Summary/Detailed/Timeline]   │
│                                                     │
│ [Сгенерировать отчёт] [Экспорт в Excel]            │
├─────────────────────────────────────────────────────┤
│ Preview:                                            │
│ ┌───────────────────────────────────────────────┐  │
│ │ Имя      │ Часы │ Перерывы │ Опоздания │...  │  │
│ │ Иванов   │ 8.2  │ 2        │ 0         │...  │  │
│ │ Петров   │ 7.5  │ 3        │ 1         │...  │  │
│ └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## 📊 ТИПЫ ОТЧЁТОВ

### 1. Summary (Сводный)
- Список пользователей
- Всего часов
- Среднее время
- Количество опозданий
- Процент выполнения нормы

### 2. Detailed (Детальный)
- Ежедневная разбивка
- Время начала/конца
- Количество перерывов
- Комментарии
- CRM активность

### 3. Timeline (Таймлайн)
- Почасовая визуализация
- Статусы по часам
- Перерывы
- График работы

---

## 🔌 API ИНТЕГРАЦИЯ

### Используемые endpoints:

**Excel Export (уже есть в backend):**
- `GET /api/v1/excel/export/summary?start_date=X&end_date=Y&department_id=Z`
- `GET /api/v1/excel/export/detailed?start_date=X&end_date=Y&user_id=Z`
- `GET /api/v1/excel/export/timeline?date=X&user_id=Y`

**Preview data (новый endpoint или использовать существующие):**
- `GET /api/v1/reports/preview?type=summary&...` (опционально)
- ИЛИ использовать существующие `/api/v1/team/stats`, `/api/v1/kpi/...`

### Headers:
- `X-User-Id`: User ID (Admin/ROP)
- `X-Account-Id`: amoCRM account ID

### Response:
- Excel file (blob) для экспорта
- JSON для preview

---

## 🎨 ДИЗАЙН

### Фильтры:
- 2 колонки на десктопе
- 1 колонка на мобильном
- Quick select кнопки (Сегодня/Неделя/Месяц)
- Date pickers для кастомного периода

### Preview таблица:
- Responsive scroll
- Zebra striping
- Hover эффекты
- Loading skeleton

### Кнопки:
- Primary: Генерировать
- Success: Экспорт Excel
- Loading states

### Цвета:
- Primary: #4A90E2 (синий)
- Success: #7ED321 (зелёный)
- Gray: #9B9B9B

---

## ⏱️ ПЛАН ВЫПОЛНЕНИЯ

**MVP (1-2 часа):**
1. HTML структура (30 мин)
2. CSS стили (30 мин)
3. JS логика (30-60 мин)

**Полная версия (1-2 дня):**
- MVP +
- Advanced фильтры
- Rich preview
- Multiple export formats
- Charts/визуализация

---

## 📁 СТРУКТУРА ФАЙЛОВ

```
frontend/
├── reports.html ⭐ NEW
├── assets/
│   ├── css/
│   │   └── reports.css ⭐ NEW
│   └── js/
│       └── reports.js ⭐ NEW
```

---

## ✅ ГОТОВНОСТЬ

**Перед началом:**
- [x] Backend Excel API готов (ЭТАП 3)
- [x] API клиент готов
- [x] Departments API готов
- [ ] Preview API (опционально, можно использовать mock)

**Для MVP:**
Использовать существующий Excel API backend, mock preview данные

---

## 🚀 СТРАТЕГИЯ

### Вариант 1: Быстрый MVP (1-2 часа)
- Только Frontend
- Mock preview данные
- Реальный Excel экспорт через существующий API
- Базовые фильтры

### Вариант 2: Полная реализация (1-2 дня)
- Frontend + Backend preview API
- Реальный preview через API
- Advanced фильтры
- Визуализация данных

**Рекомендую:** Вариант 1 (MVP) сейчас

---

## 🎯 ФУНКЦИОНАЛ MVP

**Фильтры:**
- Date range (от/до)
- Quick select (Сегодня/Неделя/Месяц)
- Подразделение (select)
- Тип отчёта (Summary/Detailed/Timeline)

**Actions:**
- Генерировать preview (mock данные)
- Экспорт Excel (реальный API)

**Preview:**
- Таблица с mock данными
- Responsive
- Показывает структуру отчёта

**UX:**
- Loading states
- Error messages
- Success feedback

---

## 📝 ПРИМЕЧАНИЯ

**Backend Excel API уже готов (ЭТАП 3):**
- Summary export ✅
- Detailed export ✅
- Timeline export ✅

Нужно только создать UI для вызова этих endpoints!

---

## 🎯 НАЧИНАЕМ!

План готов. Создаю MVP отчётов интерфейса (~1-2 часа).

**Фокус:**
- Фильтры с date pickers
- Mock preview таблица
- Реальный Excel экспорт
- Clean UX

Начинаю с HTML!
