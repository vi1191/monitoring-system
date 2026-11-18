# run_routes.pyw
# Double-click launcher. The .pyw extension is bound to pythonw.exe, so Windows
# starts it WITHOUT a console window — only the application window appears.
# Everything the app prints goes to data/gui.log (see redirect_console_to_file).
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

runpy.run_path(os.path.join(HERE, "gui.py"), run_name="__main__")
