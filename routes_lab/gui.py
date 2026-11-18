# gui.py
# Thin desktop shell: the map IS the application.
#
# There is no Qt table anymore — the shift list, the route card and the control
# panel all live inside map/index.html and talk to the local API. Qt keeps only
# the two jobs a browser cannot do: host the window and run the ETS collector
# (Playwright) in a QThread when the page presses «ЕТС».
#
#   python gui.py            # demo shift, no ETS login
#   python gui.py --live     # collect from ETS right away
import json
import os
import subprocess
import sys
import time

from PyQt6.QtCore import QTimer, QUrl, QThread, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox

from store import Store
from map_server import MapServerThread
from routes_db import RoutesDB
import preprocess_zones

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_CARS = os.path.join(HERE, "data", "demo_cars.json")
ZONES_JSON = os.path.join(HERE, "data", "zones.json")
# Last ETS collection, so the next start shows real cars immediately instead of
# falling back to the demo fixture. The raw API payload is stripped: it is huge
# and nothing in the UI reads it.
ETS_CACHE = os.path.join(HERE, "data", "ets_cache.json")
PORT = 8001


class EstpThread(QThread):
    """Runs the blocking Playwright ESTP submission off the GUI thread."""
    progress = pyqtSignal(dict)
    finished_ok = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, tickets, login, password, employee):
        super().__init__()
        self.tickets = tickets
        self.login = login
        self.password = password
        self.employee = employee

    def run(self):
        try:
            from estp_worker import run_estp_dry_run
            self.progress.emit({"phase": "start", "plate": None,
                                "done": 0, "total": len(self.tickets)})
            results = run_estp_dry_run(self.tickets, self.login, self.password,
                                       self.employee, on_progress=self.progress.emit)
            self.finished_ok.emit(results or [])
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MainWindow(QMainWindow):
    def __init__(self, live=False):
        super().__init__()
        self.setWindowTitle("Закрепление маршрутов — ГБУ «Жилищник», Тропарёво-Никулино")
        self.resize(1600, 900)

        self.store = Store()
        self.worker = None
        self._job_started = time.time()

        self._prepare_zones()

        self.server = MapServerThread(self.store, port=PORT)
        self.server.start()
        time.sleep(0.4)
        if self.server.error:
            QMessageBox.critical(self, "Порт занят",
                                 f"Не удалось поднять сервер карты на 127.0.0.1:{PORT}:\n{self.server.error}")

        self.web = QWebEngineView()
        self.web.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        self.web.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.setCentralWidget(self.web)

        index = os.path.join(HERE, "map", "index.html")
        stamp = int(os.path.getmtime(index)) if os.path.exists(index) else int(time.time())
        self.url = f"http://127.0.0.1:{PORT}/?v={stamp}"
        self.web.setUrl(QUrl(self.url))

        # The page queues collection jobs over HTTP; this timer picks them up
        # because BotWorker is a QThread and must be owned by the GUI thread.
        self.poll = QTimer(self)
        self.poll.setInterval(400)
        self.poll.timeout.connect(self.drain_requests)
        self.poll.start()

        QShortcut(QKeySequence("F5"), self, activated=self.reload_view)
        QShortcut(QKeySequence("F12"), self, activated=self.open_dev_tools)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.open_in_browser)

        # No status bar: it only ever showed filesystem paths, which is noise
        # for the dispatcher. Diagnostics go to data/gui.log instead.
        self.statusBar().hide()

        if live:
            self.start_collection("live", self.store.day)
        elif not self.load_cached():
            self.load_demo()

    # ------------------------------------------------------------------ data
    def save_cache(self, cars):
        slim = [{k: v for k, v in c.items() if k != "_raw_json"} for c in cars]
        try:
            with open(ETS_CACHE, "w", encoding="utf-8") as f:
                json.dump({"day": self.store.day, "cars": slim,
                           "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S")},
                          f, ensure_ascii=False)
            return True
        except Exception as exc:
            print(f"ets cache not saved: {exc}", flush=True)
            return False

    def load_cached(self):
        """Show the previous ETS collection without waiting for a login."""
        if not os.path.exists(ETS_CACHE):
            return False
        try:
            with open(ETS_CACHE, encoding="utf-8") as f:
                blob = json.load(f)
        except Exception as exc:
            print(f"ets cache unreadable: {exc}", flush=True)
            return False
        cars = blob.get("cars") or []
        if not cars:
            return False
        self.store.set_cars(cars)
        self.store.set_ets(status="done", kind="cache", source=f"кэш ЕТС {blob.get('saved_at', '')[:16]}",
                           day=blob.get("day"), progress="", cars=len(cars))
        return True

    def _prepare_zones(self):
        if not os.path.exists(ZONES_JSON):
            print("Готовлю zones.json из выгрузки ЕТС...", flush=True)
            zones, _, _ = preprocess_zones.build(2.0)
            with open(ZONES_JSON, "w", encoding="utf-8") as f:
                json.dump({"zones": zones}, f, ensure_ascii=False, separators=(",", ":"))
        with open(ZONES_JSON, encoding="utf-8") as f:
            data = json.load(f)
        db = RoutesDB()
        db.import_zones(data["zones"])
        db.close()
        self.store.zones_meta = {
            z["id"]: {"name": z["name"], "kind": z["kind"]} for z in data["zones"]
        }

    def load_demo(self):
        if not os.path.exists(DEMO_CARS):
            self.store.set_ets(status="error", kind="demo",
                               error="Нет data/demo_cars.json — выполни: python seed_demo.py")
            return
        with open(DEMO_CARS, encoding="utf-8") as f:
            cars = json.load(f)
        self.store.set_cars(cars)
        self.store.set_ets(status="done", kind="demo", source="демо-смена",
                           day=self.store.day, progress="", cars=len(cars))

    # ------------------------------------------------------ ETS collection
    def drain_requests(self):
        req = self.store.take_collection()
        if req:
            if req["kind"] == "demo":
                self.load_demo()
            else:
                self.start_collection("live", req["day"])
            return
        tickets = self.store.take_estp()
        if tickets:
            self.start_estp(tickets)

    def start_estp(self, tickets):
        if hasattr(self, "estp_thread") and self.estp_thread.isRunning():
            self.store.set_estp(status="running",
                                error=None, current="заявки уже отправляются, ждите")
            return
        from auth import load_estp_credentials, load_estp_employee
        login, password = load_estp_credentials()
        employee = load_estp_employee()
        if not login or not password or not employee:
            self.store.set_estp(status="error",
                                error="Нет доступов ЕСТП. Заполни routes_lab/credentials.json: "
                                      "estp_login, estp_pass, estp_employee")
            return
        self.store.set_estp(status="running", total=len(tickets), done=0,
                            current=None, results=[], error=None,
                            started_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        # ETS gov numbers are the plates we normalized; keep both for the form.
        for t in tickets:
            t.setdefault("gov_number", t["plate"])
        self.estp_thread = EstpThread(tickets, login, password, employee)
        self.estp_thread.progress.connect(self.on_estp_progress)
        self.estp_thread.finished_ok.connect(self.on_estp_done)
        self.estp_thread.failed.connect(self.on_estp_error)
        self.estp_thread.start()

    def on_estp_progress(self, p):
        p = p or {}
        self.store.set_estp(status="running",
                            total=p.get("total") or self.store.estp.get("total", 0),
                            done=p.get("done", self.store.estp.get("done", 0)),
                            current=p.get("plate"))
        if p.get("phase") == "done":
            self.store.estp_result(p.get("plate"), p.get("ok"), p.get("message") or "")

    def on_estp_done(self, results):
        ok = sum(1 for r in results if r.get("ok"))
        self.store.set_estp(status="done", total=len(results), done=ok,
                            current=None, results=results,
                            finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        print(f"ЕСТП: заявок {len(results)}, успешно {ok}", flush=True)

    def on_estp_error(self, msg):
        self.store.set_estp(status="error", error=msg)

    def start_collection(self, kind, day):
        if self.worker is not None and self.worker.isRunning():
            self.store.set_ets(status="running",
                               progress="сбор уже идёт, дождитесь окончания")
            return
        try:
            from bot_worker import BotWorker
        except Exception as exc:
            self.store.set_ets(status="error", kind=kind, day=day,
                               error=f"bot_worker не загружен: {exc}")
            return
        self._job_started = time.time()
        self.store.set_ets(status="running", kind=kind, day=day,
                           progress="запуск браузера…", elapsed=0)
        self.worker = BotWorker(target_date=day)
        self.worker.finished.connect(self.on_ets_done)
        self.worker.error.connect(self.on_ets_error)
        self.worker.status_msg.connect(self.on_ets_progress)
        self.worker.start()

    def on_ets_progress(self, msg):
        self.store.set_ets(status="running", progress=msg,
                           elapsed=round(time.time() - self._job_started, 1))

    def on_ets_done(self, cars):
        day = self.worker.target_date if self.worker else self.store.day
        self.store.day = day
        self.store.set_cars(cars)
        cached = self.save_cache(cars)
        self.store.set_ets(status="done", kind="live",
                           source="ЕТС" + (" · кэш обновлён" if cached else ""),
                           day=day, progress="", cars=len(cars),
                           elapsed=round(time.time() - self._job_started, 1))
        print(f"ЕТС: загружено {len(cars)} ТС за {day}", flush=True)

    def on_ets_error(self, msg):
        self.store.set_ets(status="error", kind="live", error=msg,
                           elapsed=round(time.time() - self._job_started, 1))

    # ---------------------------------------------------------------- extras
    def reload_view(self):
        self.web.reload()

    def open_in_browser(self):
        subprocess.Popen(["cmd", "/c", "start", "", f"http://127.0.0.1:{PORT}/"])

    def open_dev_tools(self):
        if not hasattr(self, "devtools"):
            self.devtools = QMainWindow()
            self.devtools.setWindowTitle("Консоль разработчика")
            self.devtools.resize(1100, 640)
            view = QWebEngineView()
            self.devtools.setCentralWidget(view)
            self.web.page().setDevToolsPage(view.page())
        self.devtools.show()
        self.devtools.raise_()
        self.devtools.activateWindow()

    def closeEvent(self, event):
        self.poll.stop()
        try:
            self.server.stop()
        except Exception:
            pass
        self.store.db.close()
        event.accept()


def redirect_console_to_file():
    """Launching with pythonw.exe leaves stdout/stderr as None.

    bot_worker.log() prints to them, so without a real console every status
    line would raise. Send both streams to data/gui.log instead: the window
    stays the only thing on screen, and the log is still there when needed.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return None
    path = os.path.join(HERE, "data", "gui.log")
    fh = open(path, "a", encoding="utf-8", buffering=1)
    fh.write(f"\n===== start {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    sys.stdout = fh
    sys.stderr = fh
    return fh


if __name__ == "__main__":
    _LOG = redirect_console_to_file()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow(live="--live" in sys.argv)
    win.show()
    sys.exit(app.exec())
