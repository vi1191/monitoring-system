# Закрепление маршрутов — ГБУ «Жилищник»

Управление маршрутами машин ГБУ «Жилищник» (район Тропарёво-Никулино, Москва) поверх данных ЕТС. Полноэкранная карта — выбор, назначение и контроль.

## Что умеет

| Возможность | Как работает |
|---|---|
| **Выбор маршрута** | Клик по зоне на карте — назначить/снять машину |
| **Порядок зон** | Drag-n-drop в панели «Смена» справа |
| **Покрытие** | Режим карты «Покрытие» — зелёные/красные зоны |
| **Реальные данные ЕТС** | Кнопка «📡 ЕТС» → Playwright собирает 50+ ТС |
| **Топливо** | Выезд / заправка / факт — в карточке машины |
| **Диагностика трека** | Срывы, телепорты, точки, БНСО |
| **Проблемы** | Панель с фильтрами: срыв трека / БНСО / не на связи |
| **Заявки ЕСТП** | Кнопка «ЕСТП» → SLA-классификация → очередь отправки |
| **Отчёт CSV** | «📥 CSV» — маршруты; «📊 Отчёт» — топливо, пробег, статус |
| **Горячие клавиши** | / — поиск · Esc — снять выбор · F5/F12/Ctrl+L |

## Быстрый старт

### 1. Зависимости

``````
python 3.10+
pip install -r routes_lab/requirements.txt
playwright install chromium
``````

### 2. Креды ЕТС

```json
// routes_lab/credentials.json
{
  "ets_login": "логин_ЕТС",
  "ets_pass": "пароль_ЕТС",
  "estp_login": "логин_ЕСТП",
  "estp_pass": "пароль_ЕСТП",
  "estp_employee": "ФИО сотрудника"
}
```

### 3. Зоны ЕТС (один раз)

```bash
cd routes_lab
python get_ets_geozones.py
python preprocess_zones.py
```
Создаст data/zones.json (~300-400 КБ, ~350 зон).

### 4. Запуск

**Ярлык на рабочем столе** — «Закрепление маршрутов.lnk» (без консоли):
```
C:\Python315\pythonw.exe run_routes.pyw
```

**Или вручную:**
```bash
cd routes_lab
python gui.py          # открыть с кэшем ЕТС
python gui.py --live   # сразу собрать из ЕТС
```

**Или dev-сервер (карта в браузере):**
```bash
python serve.py
# http://127.0.0.1:8001/
```

**Как приложение Edge (без Qt):**
```bash
cd routes_lab
python serve.py --live
# в другой консоли:
msedge --app=http://127.0.0.1:8001/
```

## Как работать

### Назначение машины на маршрут

1. Нажмите **📡 ЕТС** → выберите день → «Собрать»
2. Клик по строке машины в панели «Смена» → подсветка машины на карте
3. Режим карты **«Закрепление»** → клик по зоне → назначить
4. Перетаскивайте строки в панели «Смена» для изменения порядка
5. Режим **«Покрытие»** → зелёные = покрыты, красные = нет

### Горячие клавиши

| Клавиша | Действие |
|---|---|
| / | Поиск машины |
| Esc | Снять выбор машины |
| F5 | Перезагрузить карту |
| F12 | DevTools |
| Ctrl+L | Открыть в браузере |

### Отчётность

- **📥 CSV** — выгрузка маршрутов в data/routes_{day}.csv
- **📊 Отчёт** — CSV по машинам: статус, топливо, пробег, диагностика
- **ЕСТП** — отправка заявок в ЕСТП со SLA-классификацией

## Структура проекта

```
routes_lab/
├── gui.py                  # Qt-оболочка (PyQt6 + QWebEngineView)
├── run_routes.pyw          # Точка входа (без консоли)
├── serve.py                # Dev-сервер (без Qt)
├── store.py                # Состояние приложения (Store)
├── map_server.py           # API: /api/..., /api/health
├── bot_worker.py           # Playwright-сбор ЕТС
├── estp_worker.py          # Playwright-отправка ЕСТП
├── ets_stream.py           # WebSocket-поток треков
├── routes_db.py            # SQLite: зоны, машины, назначения
├── auth.py                 # Креды ЕТС/ЕСТП
├── preprocess_zones.py     # geojson → zones.json (МСК-77→WGS84)
├── get_ets_geozones.py     # Выгрузка зон из ЕТС
├── data/
│   ├── zones.json          # Зоны ЕТС (~350 шт.)
│   └── ets_cache.json      # Кэш последней выгрузки ЕТС
├── map/
│   └── index.html          # Полноэкранная карта (Leaflet)
└── credentials.json        # Секреты (gitignored)
```

## Перенос на другой ПК

### На старом ПК (очистка)

```powershell
# Всё в git на GitHub — удаляй папку смело
Remove-Item -Recurse -Force "$env:USERPROFILE\Desktop\monitoring-system"
```

### На новом ПК (восстановление)

```powershell
# 1. Python 3.10+ и VS Code
# 2. Код
cd $env:USERPROFILE\Desktop
git clone https://github.com/vi1191/monitoring-system.git
cd monitoring-system\routes_lab

# 3. Пакеты
pip install -r requirements.txt
playwright install chromium

# 4. VS Code предложит установить расширения (ms-vscode.powershell, koda.koda и др.)

# 5. Данные с флешки/облака:
#    - credentials.json
#    - routes.db, routes.db-wal, routes.db-shm (назначения маршрутов)

# 6. Зоны ЕТС (нужны креды)
python get_ets_geozones.py
python preprocess_zones.py

# 7. Пуск
python gui.py --live
```

### Что не в git (унести вручную)

| Файл | Если потерять |
|---|---|
| `credentials.json` | Креды ЕТС/ЕСТП |
| `routes.db` (+ `-wal`, `-shm`) | Назначения маршрутов |
| `data/road_areas_raw.geojson` | Перескачается `get_ets_geozones.py` |
| `data/ets_cache.json` | Пересоберётся кнопкой «📡 ЕТС» |

outes-lab — параллельная разработка.
