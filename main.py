import sys
from PySide6.QtWidgets import QApplication
from database import Base, engine
from ui.main_window import MainWindow

# Crear tablas
Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())