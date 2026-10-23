# Single Row Activity Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Отображать активность каждого дня одной горизонтальной полосой и объединять визуально пересекающиеся события в одну доступную отметку.

**Architecture:** Нормализация больше не распределяет интервалы по вертикальным рядам. Рендер строит визуальные элементы одного ряда и объединяет пересекающиеся экранные диапазоны, передавая все элементы группы в общую безопасную подсказку.

**Tech Stack:** JavaScript, CSS, Node.js test runner, JSDOM, amoCRM widget archive.

**Spec:** `docs/superpowers/specs/2026-10-23-single-row-activity-timeline-design.md`

## Global Constraints

- Один день всегда имеет один горизонтальный ряд фиксированной высоты.
- Интервалы сохраняют длительность и положение по времени.
- Все визуально пересекающиеся элементы объединяются без потери данных и времени в подсказке.
- Смешанная группа подтверждённых и неподтверждённых событий имеет отдельное оформление.
- Существующая защита от небезопасного HTML и ссылок сохраняется.

## Review Focus

- Перекрывающиеся интервалы не увеличивают высоту полосы.
- Перекрывающиеся интервалы и два точечных события одного времени дают по одной доступной отметке и сохраняют все записи в подсказке.
- Одиночные события продолжают открывать прежнюю подробную подсказку.
- Масштаб 1/2/4 не меняет длительность данных.
- Сборка виджета содержит обновлённые runtime-файлы и версию для сброса кэша amoCRM.

---

### Task 1: Single-row timeline rendering

**Files:**
- Modify: `frontend/tests/monitoring-timeline.test.js`
- Modify: `frontend/monitoring/timeline.js`
- Modify: `frontend/monitoring/styles.css`
- Modify: `widget/script.js`
- Modify: `widget/manifest.json`
- Modify: `Plan.md`

**Interfaces:**
- Consumes: activity day payload with `intervals[]`, `started_at`, `ended_at`.
- Produces: `Timeline.normalizeDay`, `Timeline.layoutDay`, `Timeline.render` with one-row visual layout and grouped point marker details.

- [x] **Step 1: Write the failing regression test**

Update the overlap contract to require `laneCount === 1` and every item in lane `0`. Add a render test with overlapping spans and two point events at the same timestamp that asserts one track height, one top offset, one grouped point marker, and both descriptions in its tooltip.

- [x] **Step 2: Run the focused test and verify RED**

Run: `node --test frontend/tests/monitoring-timeline.test.js`

Expected: FAIL because the current implementation assigns overlap lanes and renders duplicate point buttons.

- [x] **Step 3: Implement the minimal single-row layout**

Keep normalized items in lane `0`, set `laneCount` to `1`, group visually overlapping render ranges, mark mixed groups, and render every member's time and details without using `innerHTML`.

- [x] **Step 4: Synchronize widget runtime and bump cache version**

Copy the tested timeline and styles into `widget/monitoring/`, update references and manifest version from `3.0.22` to `3.0.23`, then rebuild `widget.zip` with the existing project command.

- [x] **Step 5: Verify GREEN and the complete relevant suite**

Run: `npm run test:monitoring`, the package validation tests, `git diff --check`, and the project test suite used by the release checklist.

- [ ] **Step 6: Record and publish the phase**

Mark this task complete in `Plan.md`, commit the implementation and documentation, push to GitHub, upload the rebuilt archive to the private integration, and verify the horizontal strip in Edge.
