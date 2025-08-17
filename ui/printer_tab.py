from database import SessionLocal
from typing import Optional
from PySide6 import QtWidgets
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHeaderView
)
from models import Printer

def info(msg: str, parent=None):
    QMessageBox.information(parent, "Información", msg)

def error(msg: str, parent=None):
    QMessageBox.critical(parent, "Error", msg)

class PrinterDialog(QDialog):
    def __init__(self, parent=None, data: Optional[Printer] = None):
        super().__init__(parent)
        self.setWindowTitle("Impresora")
        self.resize(400, 220)
        layout = QFormLayout(self)

        self.e_name = QLineEdit()
        self.e_price = QDoubleSpinBox(); self.e_price.setDecimals(0); self.e_price.setMaximum(1e7)
        self.e_wear = QDoubleSpinBox(); self.e_wear.setMaximum(1e5); self.e_wear.setDecimals(2)
        self.e_power = QDoubleSpinBox(); self.e_power.setMaximum(1e5); self.e_power.setDecimals(2)

        layout.addRow("Nombre*", self.e_name)
        layout.addRow("Precio compra*", self.e_price)
        layout.addRow("Desgaste/hora*", self.e_wear)
        layout.addRow("kWh por hora*", self.e_power)

        btns = QHBoxLayout()
        b_ok = QPushButton("Guardar")
        b_cancel = QPushButton("Cancelar")
        btns.addWidget(b_ok)
        btns.addWidget(b_cancel)
        layout.addRow(btns)

        b_ok.clicked.connect(self.accept)
        b_cancel.clicked.connect(self.reject)

        if data:
            self.e_name.setText(data.name)
            self.e_price.setValue(data.price)
            self.e_wear.setValue(data.wear_per_hour)
            self.e_power.setValue(data.power_kwh_per_hour)

    def get_values(self) -> dict:
        name = self.e_name.text().strip()
        price = int(self.e_price.value())
        wear = float(self.e_wear.value())
        power = float(self.e_power.value())
        if (not name) or (not price) or (not wear) or (not power):
            raise ValueError("Todos los parametros son obligatorios")
        return dict(
            name=name,
            price=price,
            wear_per_hour=wear,
            power_kwh_per_hour=power
        )

class PrinterTab(QWidget):
    def __init__(self):
        super().__init__()
        self.session = SessionLocal()

        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar por nombre…")
        b_add = QPushButton("Nueva")
        b_edit = QPushButton("Editar")
        b_del = QPushButton("Eliminar")
        controls.addWidget(self.search)
        controls.addWidget(b_add)
        controls.addWidget(b_edit)
        controls.addWidget(b_del)
        layout.addLayout(controls)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID","Nombre","Precio","Desgaste/h","kWh/h"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.header = self.table.horizontalHeader()
        self.header.setSectionResizeMode(QHeaderView.Interactive)
        self.header.setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.search.textChanged.connect(self.refresh)
        b_add.clicked.connect(self.add_item)
        b_edit.clicked.connect(self.edit_item)
        b_del.clicked.connect(self.delete_item)

        self.refresh()

    def current_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        return int(self.table.item(row, 0).text())

    def refresh(self):
        text = (self.search.text() or "").lower()
        with self.session as s:
            items = s.query(Printer).all()
        if text:
            items = [i for i in items if text in (i.name or "").lower()]
        self.table.setRowCount(len(items))
        for r, it in enumerate(items):
            self.table.setItem(r, 0, QTableWidgetItem(str(it.id)))
            self.table.setItem(r, 1, QTableWidgetItem(it.name))
            self.table.setItem(r, 2, QTableWidgetItem(f"{it.price}"))
            self.table.setItem(r, 3, QTableWidgetItem(f"{it.wear_per_hour:.2f}"))
            self.table.setItem(r, 4, QTableWidgetItem(f"{it.power_kwh_per_hour:.2f}"))

    def add_item(self):
        dlg = PrinterDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                values = dlg.get_values()
            except ValueError as e:
                error(str(e), self)
                return
            with self.session as s:
                obj = Printer(**values)
                s.add(obj)
                s.commit()
            self.refresh()

    def edit_item(self):
        pid = self.current_id()
        if not pid:
            info("Selecciona una impresora primero", self)
            return
        with self.session as s:
            obj = s.get(Printer, pid)
            if not obj:
                error("No encontrada", self); return
            dlg = PrinterDialog(self, data=obj)
            if dlg.exec() == QDialog.Accepted:
                try:
                    values = dlg.get_values()
                except ValueError as e:
                    error(str(e), self); return
                for k, v in values.items():
                    setattr(obj, k, v)
                s.commit()
        self.refresh()

    def delete_item(self):
        pid = self.current_id()
        if not pid:
            info("Selecciona una impresora primero", self)
            return
        if QMessageBox.question(self, "Confirmar", "¿Eliminar impresora seleccionada?") != QMessageBox.Yes:
            return
        with self.session as s:
            obj = s.get(Printer, pid)
            if obj:
                s.delete(obj)
                s.commit()
        self.refresh()