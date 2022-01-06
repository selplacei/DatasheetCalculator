import sys
from PySide2.QtWidgets import QApplication
import gui


app = QApplication()
window = gui.MainWindow()
window.show()
sys.exit(app.exec_())
