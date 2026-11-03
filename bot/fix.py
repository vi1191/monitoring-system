import re

with open('gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Ищем начало функции export_to_csv
start_idx = content.find('    def export_to_csv(self):')
if start_idx == -1:
    print("ОШИБКА: Не найдена функция export_to_csv!")
    exit()

# Отрезаем все, что идет до export_to_csv (оставляем нетронутым)
head = content[:start_idx]

# Новый код (с правильными отступами)
new_code = '''    def export_to_csv(self):
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
            QMessageBox.warning(self, "Внимание", "Сначала обновите данные из ЕТС.")
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
            QMessageBox.warning(self, "Ошибка", "Заполните доступы и ФИО сотрудника.")
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
'''

# Перезаписываем файл
with open('gui.py', 'w', encoding='utf-8') as f:
    f.write(head + new_code)

print("ГОТОВО! Файл gui.py успешно исправлен.")