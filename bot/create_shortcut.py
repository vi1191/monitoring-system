import os
import sys
from pathlib import Path

try:
    import win32com.client
except ImportError:
    print("станавливаю библиотеку pywin32...")
    os.system("pip install pywin32")
    import win32com.client

def create_shortcut():
    desktop = Path(os.path.expanduser("~")) / "Desktop"
    shortcut_path = desktop / "ониторинг ТС.lnk"
    
    # уть к pythonw.exe (чтобы не было черного окна консоли)
    python_exe = sys.executable
    pythonw_exe = str(Path(python_exe).parent / "pythonw.exe")
    
    # уть к нашему скрипту
    script_path = str(Path.cwd() / "gui.py")
    
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(shortcut_path))
    shortcut.Targetpath = pythonw_exe
    shortcut.Arguments = f'"{script_path}"'
    shortcut.WorkingDirectory = str(Path.cwd())
    shortcut.IconLocation = pythonw_exe
    shortcut.save()
    
    print(f"Ярлык успешно создан на рабочем столе: {shortcut_path}")

if __name__ == "__main__":
    create_shortcut()
