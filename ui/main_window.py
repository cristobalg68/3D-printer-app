from PySide6.QtWidgets import QMainWindow, QTabWidget
from ui.objects_tab import ObjectsTab
from ui.queue_tab import QueueTab
from ui.printer_tab import PrinterTab
from ui.filament_tab import FilamentTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestor de Impresión 3D")
        self.resize(1000, 650)

        tabs = QTabWidget()
        tabs.addTab(FilamentTab(), "Filamentos")
        tabs.addTab(PrinterTab(), "Impresoras")
        tabs.addTab(ObjectsTab(), "Objetos")
        tabs.addTab(QueueTab(), "Cola de impresión")

        self.setCentralWidget(tabs)