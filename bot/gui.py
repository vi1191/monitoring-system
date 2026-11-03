import sys
import csv
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, 
    QHBoxLayout, QWidget, QPushButton, QLabel, QMessageBox, QGroupBox, 
    QRadioButton, QHeaderView, QLineEdit, QFileDialog, QDialog, QFormLayout,
    QDateEdit
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont
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


# START:SETTINGS
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

        # ---------- ЕТС ----------
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

        # ---------- ЕСТП ----------
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
        layout.addLayout(form_estp)

        # ---------- Заполнение текущими значениями ----------
        curr_login, curr_pass = load_credentials()
        self.login_input.setText(curr_login)
        self.pass_input.setText(curr_pass)

        curr_estp_login, curr_estp_pass = load_estp_credentials()
        self.estp_login_input.setText(curr_estp_login)
        self.estp_pass_input.setText(curr_estp_pass)

        # ---------- Кнопки ----------
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
# END:SETTINGS
        l = self.login_input.text().strip()
        p = self.pass_input.text()
        if not l or not p:
            QMessageBox.warning(self, "Ошибка", "Логин и пароль ЕТС не могут быть пустыми.")
            return

        estp_l = self.estp_login_input.text().strip()
        estp_p = self.estp_pass_input.text()

        try:
            save_credentials(l, p)
            save_estp_credentials(estp_l, estp_p)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить данные: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Мониторинг техники (ЕТС)')
        self.resize(1650, 760)
        self.setStyleSheet('''
            QTableWidget { background-color: white; gridline-color: #e2e8f0; }
            QTableWidget::item { padding-left: 9px; padding-right: 7px; }
            QTableWidget::item:selected { color: #17212b; background-color: #a8d4f2; }
            QHeaderView::section { background-color: #e8edf3; padding: 8px;
                                   border: 1px solid #d4dce6; font-weight: bold; }
            QPushButton { padding: 8px 15px; border-radius: 4px; background-color: #f0f0f0; border: 1px solid #ccc; }
            QPushButton:hover { background-color: #e0e0e0; }
        ''')
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)
        central_widget.setLayout(main_layout)

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

        # --- НОВАЯ КНОПКА ---
        self.btn_estp = QPushButton('Сформировать заявки в ЕСТП')
        self.btn_estp.setFixedHeight(40)
        self.btn_estp.clicked.connect(self.start_estp_tickets)
        self.btn_estp.setStyleSheet('background-color: #d9eed9; border: 1px solid #a8d4a8;')
        # --------------------

        self.lbl_status = QLabel('Готов к работе')
        self.lbl_status.setStyleSheet('font-weight: bold;')
        
        top_layout.addWidget(self.btn_refresh)
        top_layout.addWidget(self.btn_export)
        top_layout.addWidget(self.btn_settings)
        top_layout.addWidget(self.lbl_status, 1)
        main_layout.addLayout(top_layout)

        # ---------- Выбор даты проверки ----------
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

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Поиск по номеру, марке, статусу или деталям...')
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.filter_rows)
        search_layout.addWidget(self.search_input, 1)
        self.lbl_count = QLabel('Машин: 0')
        search_layout.addWidget(self.lbl_count)
        main_layout.addLayout(search_layout)

        group_ticket = QGroupBox('Тип заявки (предпросмотр, без отправки)')
        group_layout = QHBoxLayout()
        self.radio_bnso = QRadioButton('Не работает БНСО (нет связи)')
        self.radio_track = QRadioButton('Некорректный трек (сбой местоположения)')
        self.radio_bnso.setChecked(True)
        group_layout.addWidget(self.radio_bnso)
        group_layout.addWidget(self.radio_track)
        group_ticket.setLayout(group_layout)

        self.table = QTableWidget()
        headers = [
            'Выбор', 'Номер ТС', 'Марка', 'Задание', 'Выполнено %', 
            'Топливо (Выезд)', 'Заправка (ЕТС)', 'Топливо (Факт)', 'Пробег, км',
            'Связь / трек', 'Детали'
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
        header.setMinimumSectionSize(60)
        
        widths = (50, 120, 150, 110, 110, 120, 130, 120, 90, 200, 300)
        for col, width in enumerate(widths):
            self.table.setColumnWidth(col, width)
            
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setWordWrap(False)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.installEventFilter(self)
        
        main_layout.addWidget(self.table, 1)
        main_layout.addWidget(group_ticket)

        # ---------- Кнопка "Просмотр заявок" справа, зелёная ----------
        ticket_btn_layout = QHBoxLayout()
        ticket_btn_layout.addStretch(1)  # прижимаем кнопку вправо
        self.btn_create_ticket = QPushButton('Просмотр заявок для выбранных машин')
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

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.lbl_status.setText("Доступы сохранены.")

    @staticmethod
    def row_color(status):
        text = status.casefold()
        if 'некорректное местоположение' in text or 'срыв трека' in text:
            return QColor('#ffd9dd')
        if 'некорректный трек' in text:
            return QColor('#fff2c9')
        if 'не на связи' in text:
            return QColor('#e6e6e6')
        if 'не работает' in text or 'срыв связи' in text:
            return QColor('#ffe2bd')
        if 'нет трека' in text or 'молчит' in text:
            return QColor('#fff2c9')
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

        # Берём дату из QDateEdit и передаём в BotWorker
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
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(cars))
        bold = QFont(self.table.font())
        bold.setBold(True)
        for row, car in enumerate(cars):
            status = self.display_value(car.get('problem_type', 'Нет данных'))
            vals = (
                '', 
                car.get('gov_number'), 
                car.get('model_name'),
                car.get('mission_status'), 
                car.get('percent'), 
                car.get('fuel_start'), 
                car.get('fuel_refuel'),        # «Заправка (ЕТС)» с деталями
                car.get('fuel_fact'), 
                car.get('distance', 0),
                status, 
                car.get('track_detail')
            )
            color = self.row_color(status)
            for col, value in enumerate(vals):
                text = self.display_value(value) if col != 0 else ''
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                item.setBackground(color)
                if col == 1:
                    item.setFont(bold)
                if col in (4, 5, 6, 7, 8):   # числовые колонки
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

    def create_tickets(self):
        selected = []
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            if chk and chk.checkState() == Qt.CheckState.Checked:
                gov = self.table.item(row, 1).text()
                status = self.table.item(row, 9).text()  # «Связь / трек» теперь индекс 9
                selected.append((gov, status))

        if not selected:
            QMessageBox.warning(self, 'Внимание', 'Выберите хотя бы одну машину галочкой.')
            return

        ticket_type = 'Не работает БНСО (нет связи)' if self.radio_bnso.isChecked() else 'Некорректный трек (сбой местоположения)'
        msg = f'Выбрано машин: {len(selected)}.\nТип заявки: {ticket_type}\n\nСписок:\n'
        for g, s in selected:
            msg += f'- {g} ({s})\n'
        msg += '\nЭто только предпросмотр: заявки не отправлены.'
        QMessageBox.information(self, 'Предпросмотр заявок', msg)

    def show_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu()
        copy_action = menu.addAction("Копировать выделенные строки")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == copy_action:
            self.copy_selected_rows()

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

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj == self.table and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.copy_selected_rows()
                return True
        return super().eventFilter(obj, event)

    def export_to_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить как CSV", "report.csv", "CSV files (*.csv)")
        if not path:
            return
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
            writer.writerow(headers)
            for row in range(self.table.rowCount()):
                row_data = []
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    row_data.append(item.text() if item else "")
                writer.writerow(row_data)
        self.lbl_status.setText(f"Сохранено в {path}")

    def start_estp_tickets(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Внимание", "Сначала обновите данные.")
            return

        target_car = None
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 9)
            if status_item and status_item.text() != "Норма":
                target_car = {
                    "gov_number": self.table.item(row, 1).text(),
                    "problem_type": status_item.text()
                }
                break

        if not target_car:
            QMessageBox.information(self, "Информация", "Все машины в норме.")
            return

        from auth import load_estp_credentials, load_estp_employee
        estp_login, estp_pass = load_estp_credentials()
        employee = load_estp_employee()

        if not estp_login or not estp_pass or not employee:
            QMessageBox.warning(self, "Ошибка", "Заполните доступы в меню 'Доступы'.")
            return

        self.lbl_status.setText(f"Запуск ЕСТП для {target_car['gov_number']}...")
        
        import threading
        from estp_worker import run_estp_dry_run
        
        def run_bot():
            try:
                run_estp_dry_run(target_car, estp_login, estp_pass, employee)
                self.lbl_status.setText("ЕСТП: Окно закрыто.")
            except Exception as e:
                self.lbl_status.setText("Ошибка ЕСТП.")
                print(f"Ошибка: {e}")

        threading.Thread(target=run_bot, daemon=True).start()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
