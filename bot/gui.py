import sys
import csv
import os
import time
import http.server
import socketserver
import threading
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from functools import partial
from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, 
    QHBoxLayout, QWidget, QPushButton, QLabel, QMessageBox, QGroupBox, 
    QRadioButton, QHeaderView, QLineEdit, QFileDialog, QDialog, QFormLayout,
    QDateEdit, QSplitter, QComboBox, QCompleter
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QShortcut, QKeySequence
from bot_worker import BotWorker

try:
    from auth import (
        load_credentials, save_credentials,
        load_estp_credentials, save_estp_credentials,
        load_estp_employee, save_estp_employee
    )
except ImportError:
    def load_credentials(): return "", ""
    def save_credentials(l, p): pass
    def load_estp_credentials(): return "", ""
    def save_estp_credentials(l, p): pass
    def load_estp_employee(): return ""
    def save_estp_employee(e): pass


class LocalServerThread(threading.Thread):
    def __init__(self, directory="../map_clean", port=8000):
        super().__init__()
        self.daemon = True
        self.directory = directory
        self.port = port
        self.server = None

    def run(self):
        try:
            handler = partial(http.server.SimpleHTTPRequestHandler, directory=self.directory)
            self.server = socketserver.TCPServer(("", self.port), handler)
            self.server.serve_forever()
        except Exception as e:
            print(f"Ошибка сервера карты: {e}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Доступы к порталам")
        self.setFixedWidth(460)
        self.setStyleSheet('''
            QDialog { background-color: #f7f9fc; }
            QLabel { font-size: 13px; color: #17212b; }
            QLineEdit {
                padding: 7px 10px; border: 1px solid #c8d2e0; border-radius: 6px;
                background: white; font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #3b82f6; }
            QPushButton {
                padding: 8px 16px; border-radius: 6px; font-size: 13px;
                background-color: #f0f0f0; border: 1px solid #ccc;
            }
            QPushButton:hover { background-color: #e4e9f0; }
            QPushButton#primary {
                background-color: #2563eb; color: white; border: 1px solid #1d4ed8;
            }
            QPushButton#primary:hover { background-color: #1d4ed8; }
            QLabel#hint { color: #6b7280; font-size: 12px; }
            QLabel#section { font-size: 14px; font-weight: bold; color: #17212b;
                             padding-top: 6px; }
        ''')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        title = QLabel("Доступы к порталам")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #17212b;")
        layout.addWidget(title)

        hint = QLabel("Логины и пароли сохраняются локально на этом компьютере.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        ets_section = QLabel("ЕТС")
        ets_section.setObjectName("section")
        layout.addWidget(ets_section)

        form_ets = QFormLayout()
        form_ets.setSpacing(10)
        form_ets.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Введите логин ЕТС")
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Введите пароль ЕТС")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.btn_toggle_pass = QPushButton("👁")
        self.btn_toggle_pass.setCheckable(True)
        self.btn_toggle_pass.setFixedWidth(38)
        self.btn_toggle_pass.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_pass.setToolTip("Показать / скрыть пароль")
        self.btn_toggle_pass.toggled.connect(self._toggle_password)

        pass_row = QHBoxLayout()
        pass_row.setSpacing(6)
        pass_row.addWidget(self.pass_input, 1)
        pass_row.addWidget(self.btn_toggle_pass)

        form_ets.addRow("Логин:", self.login_input)
        form_ets.addRow("Пароль:", pass_row)
        layout.addLayout(form_ets)

        estp_section = QLabel("ЕСТП")
        estp_section.setObjectName("section")
        layout.addWidget(estp_section)

        form_estp = QFormLayout()
        form_estp.setSpacing(10)
        form_estp.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.estp_login_input = QLineEdit()
        self.estp_login_input.setPlaceholderText("Введите логин ЕСТП")
        self.estp_pass_input = QLineEdit()
        self.estp_pass_input.setPlaceholderText("Введите пароль ЕСТП")
        self.estp_pass_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.btn_toggle_estp_pass = QPushButton("👁")
        self.btn_toggle_estp_pass.setCheckable(True)
        self.btn_toggle_estp_pass.setFixedWidth(38)
        self.btn_toggle_estp_pass.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_estp_pass.setToolTip("Показать / скрыть пароль")
        self.btn_toggle_estp_pass.toggled.connect(self._toggle_estp_password)

        estp_pass_row = QHBoxLayout()
        estp_pass_row.setSpacing(6)
        estp_pass_row.addWidget(self.estp_pass_input, 1)
        estp_pass_row.addWidget(self.btn_toggle_estp_pass)

        form_estp.addRow("Логин:", self.estp_login_input)
        form_estp.addRow("Пароль:", estp_pass_row)

        self.estp_employee_input = QLineEdit()
        self.estp_employee_input.setPlaceholderText("Иванов И.И.")
        form_estp.addRow("ФИО сотрудника:", self.estp_employee_input)
        
        layout.addLayout(form_estp)

        curr_login, curr_pass = load_credentials()
        self.login_input.setText(curr_login)
        self.pass_input.setText(curr_pass)

        curr_estp_login, curr_estp_pass = load_estp_credentials()
        self.estp_login_input.setText(curr_estp_login)
        self.estp_pass_input.setText(curr_estp_pass)

        curr_employee = load_estp_employee()
        self.estp_employee_input.setText(curr_employee)

        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        btn_save = QPushButton("Сохранить")
        btn_save.setObjectName("primary")
        btn_save.setDefault(True)
        btn_cancel = QPushButton("Отмена")
        btn_save.clicked.connect(self.save)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def _toggle_password(self, shown: bool):
        self.pass_input.setEchoMode(
            QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        )
        self.btn_toggle_pass.setText("🙈" if shown else "👁")

    def _toggle_estp_password(self, shown: bool):
        self.estp_pass_input.setEchoMode(
            QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        )
        self.btn_toggle_estp_pass.setText("🙈" if shown else "👁")

    def save(self):
        l = self.login_input.text().strip()
        p = self.pass_input.text()
        if not l or not p:
            QMessageBox.warning(self, "Ошибка", "Логин и пароль ЕТС не могут быть пустыми.")
            return

        estp_l = self.estp_login_input.text().strip()
        estp_p = self.estp_pass_input.text()
        emp = self.estp_employee_input.text().strip()

        try:
            save_credentials(l, p)
            save_estp_credentials(estp_l, estp_p)
            save_estp_employee(emp)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить данные: {e}")


class ConfirmTicketsDialog(QDialog):
    def __init__(self, selected_cars, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Подтверждение заявок в ЕСТП")
        self.resize(1000, 500)
        self.selected_cars = selected_cars
        
        layout = QVBoxLayout(self)
        
        lbl = QLabel("Выберите классификацию из списка ЕСТП, шаблон и добавьте свой комментарий.")
        lbl.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(lbl)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Номер ТС", "Проблема (из ЕТС)", "Классификация и Комментарий"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 200)
        self.table.setRowCount(len(selected_cars))
        
        self.sla_options = [
            "Удаленное изменение настроек БНСО",
            "Проведение работ по восстановлению неработающего БНСО",
            "Проведение замены/ремонта датчиков учета топлива",
            "Внесение изменений в информацию по ТС в АСУ ОДС ДЖКХиБ",
            "Дистанционная поддержка",
            "Нет данных по ТС в системе предприятия",
            "Нет данных по ТС в АСУ ОДС",
            "Некорректный трек ТС",
            "Другое",
            "Ввод в эксплуатацию",
            "Претензия"
        ]
        
        self.comment_options = [
            "Некорректное местоположение ТС",
            "машина не выходит на связь",
            "не отображается трек"
        ]
        
        for row, car in enumerate(selected_cars):
            item_gov = QTableWidgetItem(car['gov_number'])
            item_gov.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 0, item_gov)
            
            item_prob = QTableWidgetItem(car['problem_type'])
            item_prob.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 1, item_prob)
            
            container = QWidget()
            c_layout = QVBoxLayout(container)
            c_layout.setContentsMargins(2, 2, 2, 2)
            c_layout.setSpacing(2)
            
            combo = QComboBox()
            combo.addItems(self.sla_options)
            
            prob_text = car['problem_type']
            
            # Определяем классификацию и комментарий на основе статуса
            if 'Некорректное местоположение' in prob_text or 'Некорректный трек' in prob_text:
                combo.setCurrentText("Некорректный трек ТС")
                default_comment = "Некорректное местоположение ТС"
            elif 'Не работает БНСО' in prob_text:
                # Оранжевый статус (связь есть, но трек не идет)
                combo.setCurrentText("Проведение работ по восстановлению неработающего БНСО")
                default_comment = "не отображается трек"
            elif 'не на связи' in prob_text:
                # Серый статус (связи нет вообще)
                combo.setCurrentText("Проведение работ по восстановлению неработающего БНСО")
                default_comment = "машина не выходит на связь"
            else:
                combo.setCurrentText("Другое")
                default_comment = ""
                
            line_comment = QLineEdit()
            line_comment.setText(default_comment)
            
            completer = QCompleter(self.comment_options, self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            line_comment.setCompleter(completer)

            def show_all_on_click(event, line=line_comment, comp=completer):
                line.setCompleter(comp)
                QLineEdit.mousePressEvent(line, event)
                if line.text() == "":
                    comp.setCompletionPrefix("")
                    comp.complete()

            line_comment.mousePressEvent = show_all_on_click
            
            c_layout.addWidget(combo)
            c_layout.addWidget(line_comment)
            
            self.table.setCellWidget(row, 2, container)
            self.table.setRowHeight(row, 60)
            
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        
        btn_send = QPushButton("ОТПРАВИТЬ В ЕСТП")
        btn_send.setStyleSheet("background-color: #2e9e5b; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        btn_send.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_send)
        layout.addLayout(btn_layout)

    def get_final_data(self):
        final_cars = []
        for row in range(self.table.rowCount()):
            gov = self.table.item(row, 0).text()
            problem = self.table.item(row, 1).text()
            
            container = self.table.cellWidget(row, 2)
            combo = container.findChild(QComboBox)
            line_comment = container.findChild(QLineEdit)
            
            final_cars.append({
                "gov_number": gov,
                "problem_type": problem,
                "sla": combo.currentText(),
                "comment": line_comment.text()
            })
        return final_cars


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Мониторинг техники (ЕТС)')
        self.resize(1650, 760)
        self.setStyleSheet('''
            QTableWidget { background-color: white; gridline-color: #e2e8f0; }
            QTableWidget::item { padding-left: 9px; padding-right: 7px; }
            QTableWidget::item:selected { color: #17212b; background-color: #a8d4f2; }
            
            QHeaderView::section { 
                background-color: #e8edf3; 
                padding: 8px;
                border: 1px solid #d4dce6; 
                font-weight: bold; 
            }
            
            QHeaderView::section:nth-child(5), 
            QHeaderView::section:nth-child(6), 
            QHeaderView::section:nth-child(7) {
                background-color: #fdf6e3; 
                border: 1px solid #e2d5b8;
            }
            
            QPushButton { padding: 8px 15px; border-radius: 4px; background-color: #f0f0f0; border: 1px solid #ccc; }
            QPushButton:hover { background-color: #e0e0e0; }
        ''')
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)
        central_widget.setLayout(main_layout)

        # --- ВЕРХНЯЯ ПАНЕЛЬ С КНОПКАМИ ---
        top_layout = QHBoxLayout()
        self.btn_refresh = QPushButton('Обновить данные')
        self.btn_refresh.setFixedHeight(40)
        self.btn_refresh.clicked.connect(self.start_collection)
        
        self.btn_export = QPushButton('Экспорт в CSV')
        self.btn_export.setFixedHeight(40)
        self.btn_export.clicked.connect(self.export_to_csv)
        
        self.btn_settings = QPushButton('Доступы')
        self.btn_settings.setFixedHeight(40)
        self.btn_settings.clicked.connect(self.open_settings)

        self.btn_devtools = QPushButton('Консоль')
        self.btn_devtools.setFixedHeight(40)
        self.btn_devtools.clicked.connect(self.open_dev_tools)

        self.lbl_status = QLabel('Готов к работе')
        self.lbl_status.setStyleSheet('font-weight: bold;')
        
        top_layout.addWidget(self.btn_refresh)
        top_layout.addWidget(self.btn_export)
        top_layout.addWidget(self.btn_settings)
        top_layout.addWidget(self.btn_devtools)
        top_layout.addWidget(self.lbl_status, 1)
        main_layout.addLayout(top_layout)

        # --- ДАТА ПРОВЕРКИ ---
        date_layout = QHBoxLayout()
        date_layout.setSpacing(8)
        lbl_date = QLabel('Дата проверки:')
        lbl_date.setStyleSheet('font-weight: bold;')
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat('dd.MM.yyyy')
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setFixedHeight(34)
        self.date_edit.setFixedWidth(140)
        date_layout.addWidget(lbl_date)
        date_layout.addWidget(self.date_edit)
        date_layout.addStretch(1)
        main_layout.addLayout(date_layout)

        # --- ПОИСК ---
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Поиск по номеру, марке, статусу или деталям...')
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.filter_rows)
        search_layout.addWidget(self.search_input, 1)
        self.lbl_count = QLabel('Машин: 0')
        search_layout.addWidget(self.lbl_count)
        main_layout.addLayout(search_layout)

        # --- ТАБЛИЦА ---
        self.table = QTableWidget()
        headers = [
            '✓', 'Номер ТС', 'Марка', 'Задание', 'Вып.\n%', 
            'Топливо\nвыезд', 'Топливо\nзаправка', 'Топливо\nфакт', 
            'Пробег,\nкм', 'Связь /\nтрек', 'Детали'
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
        header.setMinimumSectionSize(40)
        header.setFixedHeight(50)
        
        widths = (30, 100, 160, 160, 45, 80, 100, 90, 80, 180, 250)
        for col, width in enumerate(widths):
            self.table.setColumnWidth(col, width)
            
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setWordWrap(False)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        self.table.itemDoubleClicked.connect(self.on_row_double_clicked)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.table)
        
        # --- КАРТА ---
        self.map_container = QWidget()
        map_layout = QVBoxLayout(self.map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        
        self.web_view = QWebEngineView()
        
        # Настройки WebEngine
        self.web_view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, True
        )
        self.web_view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        
        map_layout.addWidget(self.web_view)
        self.splitter.addWidget(self.map_container)
        self.splitter.setSizes([650, 1000])
        main_layout.addWidget(self.splitter, 1)
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        map_path = os.path.join(current_dir, "..", "map_clean")
        
        self.server_thread = LocalServerThread(directory=map_path, port=8000)
        self.server_thread.start()
        time.sleep(0.5)
        self.web_view.setUrl(QUrl("http://127.0.0.1:8000/index.html?v=25"))

        # --- КНОПКА ЕСТП ---
        ticket_btn_layout = QHBoxLayout()
        ticket_btn_layout.addStretch(1)
        self.btn_create_ticket = QPushButton('Создать заявки в ЕСТП')
        self.btn_create_ticket.setFixedHeight(45)
        self.btn_create_ticket.setMinimumWidth(320)
        self.btn_create_ticket.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_create_ticket.setStyleSheet('''
            QPushButton {
                background-color: #2e9e5b;
                color: white;
                border: 1px solid #248048;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton:hover { background-color: #248048; }
            QPushButton:pressed { background-color: #1d6b3b; }
        ''')
        self.btn_create_ticket.clicked.connect(self.create_tickets)
        ticket_btn_layout.addWidget(self.btn_create_ticket)
        main_layout.addLayout(ticket_btn_layout)

        self.worker = None
        self.is_running = False
        self.start_collection()

    def open_dev_tools(self):
        try:
            from PyQt6.QtWidgets import QMainWindow
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            
            if not hasattr(self, 'dev_tools_window'):
                self.dev_tools_window = QMainWindow()
                self.dev_tools_window.setWindowTitle("Консоль разработчика")
                self.dev_tools_window.resize(1000, 600)
                
                self.dev_tools_view = QWebEngineView()
                self.dev_tools_window.setCentralWidget(self.dev_tools_view)
                
                self.web_view.page().setDevToolsPage(self.dev_tools_view.page())
            
            self.dev_tools_window.show()
            self.dev_tools_window.raise_()
            self.dev_tools_window.activateWindow()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть консоль: {e}")

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.lbl_status.setText("Доступы сохранены.")

    @staticmethod
    def row_color(status):
        text = status.casefold()
        
        if 'некорректное местоположение' in text or 'некорректный трек' in text or 'срыв трека' in text:
            return QColor('#ffd9dd')
            
        if 'не работает бнсо' in text or 'не отображается трек' in text:
            return QColor('#ffe2bd')
            
        if 'машина не на связи' in text or 'не на связи' in text:
            return QColor('#e6e6e6')
            
        if 'ошибка' in text or 'не удалось' in text:
            return QColor('#e7ebf0')
            
        if text == 'норма':
            return QColor('#e8f7e9')
            
        return QColor('#ffffff')

    @staticmethod
    def display_value(value):
        return '-' if value is None or value == '' else str(value)

    def start_collection(self):
        if self.is_running:
            return
        self.is_running = True
        self.btn_refresh.setEnabled(False)

        target_date = self.date_edit.date().toString("yyyy-MM-dd")
        self.lbl_status.setText(f'Сбор данных за {self.date_edit.date().toString("dd.MM.yyyy")}...')

        self.worker = BotWorker(target_date=target_date)
        self.worker.finished.connect(self.populate_table)
        self.worker.error.connect(self.on_error)
        self.worker.status_msg.connect(self.lbl_status.setText)
        self.worker.start()

    def on_error(self, message):
        self.lbl_status.setText('Ошибка сбора данных')
        QMessageBox.critical(self, 'Ошибка', message)
        self.btn_refresh.setEnabled(True)
        self.is_running = False

    def populate_table(self, cars):
        self.cars_data = cars
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(cars))
        bold = QFont(self.table.font())
        bold.setBold(True)
        
        for row, car in enumerate(cars):
            status = self.display_value(car.get('problem_type', 'Нет данных'))
            vals = (
                '', car.get('gov_number'), car.get('model_name'),
                car.get('mission_status'), car.get('percent'), 
                car.get('fuel_start'), car.get('fuel_refuel'),
                car.get('fuel_fact'), car.get('distance', 0),
                status, car.get('track_detail')
            )
            color = self.row_color(status)
            
            for col, value in enumerate(vals):
                text = self.display_value(value) if col != 0 else ''
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                item.setBackground(color)

                if col == 1:
                    item.setFont(bold)
                    item.setData(Qt.ItemDataRole.UserRole, car.get('car_id'))
                    
                if col == 3: 
                    order_num = car.get('order_number')
                    status_text = str(car.get('mission_status', 'Выполняется'))
                    if order_num and order_num != '-' and str(order_num).strip() != '':
                        item.setText(f"{status_text} {order_num}")
                    else:
                        item.setText(status_text)
                    
                if col in (4, 5, 6, 7, 8):   
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    
                if col == 0:
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Unchecked)
                    
                self.table.setItem(row, col, item)

        self.table.setSortingEnabled(True)
        self.filter_rows()
        self.lbl_status.setText(f'Загружено машин: {len(cars)}')
        self.btn_refresh.setEnabled(True)
        self.is_running = False

    def filter_rows(self):
        query = self.search_input.text().strip().casefold()
        visible = 0
        for row in range(self.table.rowCount()):
            matches = not query or any(
                query in self.table.item(row, col).text().casefold()
                for col in range(1, self.table.columnCount())
                if self.table.item(row, col) is not None
            )
            self.table.setRowHidden(row, not matches)
            visible += matches
        self.lbl_count.setText(f'Машин: {visible} из {self.table.rowCount()}')

    def copy_selected_rows(self):
        from PyQt6.QtWidgets import QApplication
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            return
        text = ""
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        text += "\t".join(headers) + "\n"
        for r in selected_ranges:
            for row in range(r.topRow(), r.bottomRow() + 1):
                row_data = []
                for col in range(r.leftColumn(), r.rightColumn() + 1):
                    item = self.table.item(row, col)
                    row_data.append(item.text() if item else "")
                text += "\t".join(row_data) + "\n"
        QApplication.clipboard().setText(text)
        self.lbl_status.setText("Скопировано в буфер обмена!")

    def show_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu()
        copy_action = menu.addAction("Копировать выделенные строки")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == copy_action:
            self.copy_selected_rows()

    def export_to_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить отчет", "Отчет_ЕТС.xlsx", "Excel files (*.xlsx)")
        if not path:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Мониторинг"

            headers = [
                '✓', 'Номер ТС', 'Марка', 'Задание', 'Вып. %', 
                'Топливо выезд', 'Топливо заправка', 'Топливо факт', 
                'Пробег, км', 'Связь / трек', 'Детали'
            ]
            
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            center_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                 top=Side(style='thin'), bottom=Side(style='thin'))

            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_num)
                cell.value = header
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_alignment
                cell.border = thin_border

            for row_idx in range(self.table.rowCount()):
                for col_idx in range(self.table.columnCount()):
                    item = self.table.item(row_idx, col_idx)
                    value = item.text() if item else ""
                    
                    cell = ws.cell(row=row_idx + 2, column=col_idx + 1)
                    cell.value = value
                    cell.border = thin_border
                    cell.alignment = Alignment(vertical="center", wrap_text=True)

                    if col_idx == 9:
                        status = str(value).casefold()
                        if 'некорректное' in status or 'срыв' in status:
                            cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
                        elif 'не работает' in status:
                            cell.fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
                        elif 'не на связи' in status:
                            cell.fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
                        elif status == 'норма':
                            cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")

            column_widths = [5, 15, 25, 20, 10, 15, 15, 15, 15, 25, 50]
            for i, width in enumerate(column_widths, 1):
                ws.column_dimensions[get_column_letter(i)].width = width

            ws.freeze_panes = "A2"
            wb.save(path)
            self.lbl_status.setText(f"Отчет сохранен в {path}")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить отчет: {e}")

    def create_tickets(self):
        selected_cars = []
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            if chk and chk.checkState() == Qt.CheckState.Checked:
                gov = self.table.item(row, 1).text()
                status = self.table.item(row, 9).text()
                selected_cars.append({"gov_number": gov, "problem_type": status})

        if not selected_cars:
            QMessageBox.warning(self, 'Внимание', 'Выберите хотя бы одну машину галочкой.')
            return

        dialog = ConfirmTicketsDialog(selected_cars, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            final_cars = dialog.get_final_data()
            
            from auth import load_estp_credentials, load_estp_employee
            estp_login, estp_pass = load_estp_credentials()
            employee = load_estp_employee()

            if not estp_login or not estp_pass or not employee:
                QMessageBox.warning(self, "Ошибка", "Заполните доступы ЕСТП в меню 'Доступы'.")
                return

            self.lbl_status.setText(f"Отправка заявок в ЕСТП ({len(final_cars)} шт)...")
            
            import threading
            from estp_worker import run_estp_dry_run
            
            def run_bot():
                try:
                    run_estp_dry_run(final_cars, estp_login, estp_pass, employee)
                    self.lbl_status.setText("ЕСТП: Заявки успешно созданы.")
                except Exception as e:
                    self.lbl_status.setText("Ошибка ЕСТП.")
                    print(f"Ошибка: {e}")

            threading.Thread(target=run_bot, daemon=True).start()

    def on_row_selected(self):
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        car_number = self.table.item(row, 1).text()
        car_id = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
        
        car_track = []
        if hasattr(self, 'cars_data') and car_id:
            car_data = next((c for c in self.cars_data if str(c.get('car_id')) == str(car_id)), None)
            if car_data:
                car_track = car_data.get('_track_raw', [])
                if car_track:
                    car_track = [point['coords'] for point in car_track if 'coords' in point]
        
        if not car_track:
            self.lbl_status.setText(f"Машина {car_number}: нет данных о треке")
            return
            
        self.lbl_status.setText(f"Машина {car_number}: отрисовка трека...")
        
        import json
        coords_json = json.dumps(car_track)
        js_code = f"window.drawTrack({coords_json}, '{car_number}');"
        self.web_view.page().runJavaScript(js_code)

    def on_row_double_clicked(self):
        self.web_view.page().runJavaScript("window.clearTrack();")
        self.lbl_status.setText("Трек скрыт")

    def auto_update(self):
        if self.is_running:
            return
        self.start_collection()

    def closeEvent(self, event):
        if hasattr(self, 'server_thread'):
            self.server_thread.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    win = MainWindow()
    win.show()
    sys.exit(app.exec())