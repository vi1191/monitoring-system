import os

file_path = "gui.py"

if not os.path.exists(file_path):
    print("ОШИБКА: Файл gui.py не найден в текущей папке!")
    exit()

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 1. Исправляем верхнюю часть (try / from auth)
# Ищем строку с "from auth import"
start_idx = -1
for i, line in enumerate(lines):
    if "from auth import" in line:
        start_idx = i
        break

if start_idx != -1:
    # Принудительно ставим правильные отступы
    lines[start_idx] = "    from auth import (\n"
    lines[start_idx+1] = "        load_credentials, save_credentials,\n"
    lines[start_idx+2] = "        load_estp_credentials, save_estp_credentials,\n"
    lines[start_idx+3] = "        load_estp_employee, save_estp_employee\n"
    lines[start_idx+4] = "    )\n"
    
    # Ищем except
    for j in range(start_idx+5, start_idx+10):
        if "except ImportError" in lines[j]:
            lines[j] = "except ImportError:\n"
            lines[j+1] = '    def load_credentials(): return "", ""\n'
            lines[j+2] = '    def save_credentials(l, p): pass\n'
            lines[j+3] = '    def load_estp_credentials(): return "", ""\n'
            lines[j+4] = '    def save_estp_credentials(l, p): pass\n'
            lines[j+5] = '    def load_estp_employee(): return ""\n'
            lines[j+6] = '    def save_estp_employee(e): pass\n'
            break

# 2. Полностью переписываем конец файла (от export_to_csv до конца)
# Находим индекс начала export_to_csv
end_start = -1
for i, line in enumerate(lines):
    if "def export_to_csv" in line:
        end_start = i
        break

if end_start != -1:
    # Берем всё, что было до export_to_csv
    head = lines[:end_start]
    
    # Пишем новый низ
    new_tail = '''    def export_to_csv(self):
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
'''
    
    # Записываем склеенный файл
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(head)
        f.write(new_tail)
    print("Файл gui.py успешно перезаписан!")
else:
    print("ОШИБКА: не удалось найти def export_to_csv")