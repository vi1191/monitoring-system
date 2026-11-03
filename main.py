import sys
import os
import http.server
import socketserver
import threading
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget, QVBoxLayout, 
                             QHBoxLayout, QWidget, QPushButton, QLabel, QSplitter, 
                             QFrame, QSizePolicy, QDateEdit, QLineEdit)
from PyQt6.QtCore import Qt, QUrl, QDate
from PyQt6.QtWebEngineWidgets import QWebEngineView

PORT = 8000
MAP_DIRECTORY = "map" 

class LocalServerThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.server = None

    def run(self):
        if os.path.exists(MAP_DIRECTORY):
            os.chdir(MAP_DIRECTORY)
        handler = http.server.SimpleHTTPRequestHandler
        self.server = socketserver.TCPServer(("", PORT), handler)
        self.server.serve_forever()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Мониторинг техники (ЕТС) - Объединенный')
        self.resize(1650, 800)
        
        self.setStyleSheet('''
            QMainWindow { background-color: #f0f0f0; }
            /* Стили для кнопок как в старом приложении */
            QPushButton {
                background-color: #fdfdfd;
                border: 1px solid #c8d2e0;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #e8edf3; }
            
            /* Стили для таблицы */
            QTableWidget {
                background-color: white;
                gridline-color: #e2e8f0;
                border: 1px solid #cbd5e1;
            }
            QTableWidget::item { padding: 4px; }
            QTableWidget::item:selected { background-color: #dbeafe; color: #1e293b; }
            QHeaderView::section {
                background-color: #e8edf3;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #cbd5e1;
                border-right: 1px solid #d4dce6;
                font-weight: bold;
            }
            /* Контейнеры */
            QFrame#MapContainer {
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
            }
        ''')

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # ==========================================
        # 1. ВЕРХНЯЯ ПАНЕЛЬ (Красная зона на вашем скрине)
        # ==========================================
        top_panel = QWidget()
        top_panel.setStyleSheet("background-color: #f0f0f0;")
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(5)

        # -- Ряд 1: Кнопки инструментов --
        tools_layout = QHBoxLayout()
        
        btn_update = QPushButton("Обновить данные")
        btn_export = QPushButton("Экспорт в CSV")
        btn_access = QPushButton("Доступы")
        btn_ready = QPushButton("Готов к работе")
        
        # Пока добавляем кнопку скрытия карты сюда же, чтобы не нарушать дизайн
        self.btn_toggle_map = QPushButton("Скрыть карту")
        self.btn_toggle_map.clicked.connect(self.toggle_map)

        tools_layout.addWidget(btn_update)
        tools_layout.addWidget(btn_export)
        tools_layout.addWidget(btn_access)
        tools_layout.addWidget(btn_ready)
        tools_layout.addStretch() # Отталкиваем кнопку карты вправо
        tools_layout.addWidget(self.btn_toggle_map)
        
        top_layout.addLayout(tools_layout)

        # -- Ряд 2: Дата проверки --
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Дата проверки:"))
        date_edit = QDateEdit()
        date_edit.setDate(QDate.currentDate())
        date_edit.setCalendarPopup(True)
        date_layout.addWidget(date_edit)
        date_layout.addStretch()
        top_layout.addLayout(date_layout)

        # -- Ряд 3: Поиск --
        search_layout = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText("Поиск по номеру, марке, статусу или деталям...")
        search_layout.addWidget(search_input)
        search_layout.addWidget(QLabel("Машин: 0"))
        top_layout.addLayout(search_layout)

        main_layout.addWidget(top_panel)

        # ==========================================
        # 2. ОСНОВНАЯ ОБЛАСТЬ (Таблица слева, Карта справа)
        # ==========================================
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- ЛЕВАЯ ЧАСТЬ (Таблица) ---
        self.table = QTableWidget()
        # Устанавливаем колонки точно как на вашем скрине
        columns = ["Выбор", "Номер ТС", "Марка", "Задание", "Выполнено %", 
                   "Топливо (Выезд)", "Заправка (ЕТС)", "Топливо (Факт)", 
                   "Пробег, км", "Связь / трек", "Детали"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # --- ПРАВАЯ ЧАСТЬ (Карта) ---
        self.map_container = QFrame()
        self.map_container.setObjectName("MapContainer")
        map_layout = QVBoxLayout(self.map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        
        self.web_view = QWebEngineView()
        map_layout.addWidget(self.web_view)

        # Добавляем в сплиттер (по умолчанию карта занимает 50% ширины)
        self.splitter.addWidget(self.table)
        self.splitter.addWidget(self.map_container)
        self.splitter.setSizes([800, 800]) 
        
        main_layout.addWidget(self.splitter)

        # Запуск сервера карты
        self.server_thread = LocalServerThread()
        self.server_thread.start()
        time.sleep(0.5) 
        self.web_view.setUrl(QUrl(f"http://127.0.0.1:{PORT}/index.html"))

    def toggle_map(self):
        is_visible = self.map_container.isVisible()
        self.map_container.setVisible(not is_visible)
        self.btn_toggle_map.setText("Показать карту" if is_visible else "Скрыть карту")

    def closeEvent(self, event):
        self.server_thread.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())