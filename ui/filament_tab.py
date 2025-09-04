from database import SessionLocal
from PySide6 import QtWidgets
from typing import Optional
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
    QFormLayout,
    QHeaderView,
    QDoubleSpinBox
)
from models import Filament

def info(msg: str, parent=None):
    QMessageBox.information(parent, "Información", msg)

def error(msg: str, parent=None):
    QMessageBox.critical(parent, "Error", msg)

class FilamentDialog(QDialog):
    def __init__(self, parent=None, data: Optional[Filament] = None):
        super().__init__(parent)
        self.setWindowTitle("Filamento")
        self.resize(400, 200)
        layout = QFormLayout(self)

        self.e_name = QLineEdit()
        self.e_color = QLineEdit()
        self.e_material = QLineEdit()
        self.e_price = QDoubleSpinBox(); self.e_price.setDecimals(0); self.e_price.setMaximum(1e5)
        self.e_initial = QDoubleSpinBox(); self.e_initial.setDecimals(0); self.e_initial.setMaximum(1e4)
        self.e_remaining_effective = QDoubleSpinBox(); self.e_remaining_effective.setDecimals(0); self.e_remaining_effective.setMaximum(1e4)

        layout.addRow("Nombre*", self.e_name)
        layout.addRow("Color*", self.e_color)
        layout.addRow("Material*", self.e_material)
        layout.addRow("Precio*", self.e_price)
        layout.addRow("Gramos iniciales", self.e_initial)
        layout.addRow("Gramos restantes", self.e_remaining_effective)

        btns = QHBoxLayout()
        b_ok = QPushButton("Guardar")
        b_cancel = QPushButton("Cancelar")
        btns.addWidget(b_ok)
        btns.addWidget(b_cancel)
        layout.addRow(btns)

        b_ok.clicked.connect(self.accept)
        b_cancel.clicked.connect(self.reject)

        self.data = data
        if data:
            self.e_name.setText(data.name)
            self.e_color.setText(data.color)
            self.e_material.setText(data.material)
            self.e_price.setValue(data.price)
            self.e_initial.setValue(data.initial_g or 1000)
            self.e_remaining_effective.setValue(data.remaining_g_effective or 1000)

    def get_values(self) -> dict:
        name = self.e_name.text().strip()
        color = self.e_color.text().strip()
        material = self.e_material.text().strip()
        price = int(self.e_price.value())
        if not name:
            raise ValueError("El nombre es obligatorio")
        if not color:
            raise ValueError("El color es obligatorio")
        if not material:
            raise ValueError("El material es obligatorio")
        if not price:
            raise ValueError("El precio es obligatorio")
        return dict(
            name=name,
            color=color,
            material=material,
            price=price,
            initial_g=int(self.e_initial.value()),
            remaining_g_effective=int(self.e_remaining_effective.value()),
            remaining_g_projected=int(self.e_remaining_effective.value())
        )

class FilamentTab(QWidget):
    def __init__(self):
        super().__init__()
        self.session = SessionLocal()

        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar por nombre o color…")
        b_add = QPushButton("Nuevo")
        b_edit = QPushButton("Editar")
        b_del = QPushButton("Eliminar")
        controls.addWidget(self.search)
        controls.addWidget(b_add)
        controls.addWidget(b_edit)
        controls.addWidget(b_del)
        layout.addLayout(controls)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["ID","Nombre","Color","Material","Precio","Gramos Iniciales","Gramos Restantes Efectivos", "Gramos Restantes Proyectados"])
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
    
    def load_filaments(self):
        self.table.setRowCount(0)
        filaments = self.session.query(Filament).all()
        self.table.setRowCount(len(filaments))
        for r, it in enumerate(filaments):
            self.table.setItem(r, 0, QTableWidgetItem(str(it.id)))
            self.table.setItem(r, 1, QTableWidgetItem(it.name))
            self.table.setItem(r, 2, QTableWidgetItem(it.color))
            self.table.setItem(r, 3, QTableWidgetItem(it.material))
            self.table.setItem(r, 4, QTableWidgetItem(f"{it.price}"))
            self.table.setItem(r, 5, QTableWidgetItem(f"{it.initial_g}"))
            self.table.setItem(r, 6, QTableWidgetItem(f"{it.remaining_g_effective}"))
            self.table.setItem(r, 7, QTableWidgetItem(f"{it.remaining_g_projected}"))

    def refresh(self):
        text = (self.search.text() or "").lower()
        with self.session as s:
            q = s.query(Filament)
            items = q.all()
        if text:
            items = [i for i in items if (text in (i.name or "").lower()) or (text in (i.color or "").lower()) or (text in (i.material or "").lower())]
        self.table.setRowCount(len(items))
        for r, it in enumerate(items):
            self.table.setItem(r, 0, QTableWidgetItem(str(it.id)))
            self.table.setItem(r, 1, QTableWidgetItem(it.name))
            self.table.setItem(r, 2, QTableWidgetItem(it.color))
            self.table.setItem(r, 3, QTableWidgetItem(it.material))
            self.table.setItem(r, 4, QTableWidgetItem(f"{it.price}"))
            self.table.setItem(r, 5, QTableWidgetItem(f"{it.initial_g}"))
            self.table.setItem(r, 6, QTableWidgetItem(f"{it.remaining_g_effective}"))
            self.table.setItem(r, 7, QTableWidgetItem(f"{it.remaining_g_projected}"))

    def add_item(self):
        dlg = FilamentDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                values = dlg.get_values()
            except ValueError as e:
                error(str(e), self)
                return
            with self.session as s:
                obj = Filament(**values)
                s.add(obj)
                s.commit()
            self.refresh()

    def edit_item(self):
        fid = self.current_id()
        if not fid:
            info("Selecciona un filamento primero", self)
            return
        with self.session as s:
            obj = s.get(Filament, fid)
            if not obj:
                error("No encontrado", self); return
            dlg = FilamentDialog(self, data=obj)
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
        fid = self.current_id()
        if not fid:
            info("Selecciona un filamento primero", self)
            return
        if QMessageBox.question(self, "Confirmar", "¿Eliminar filamento seleccionado?") != QMessageBox.Yes:
            return
        with self.session as s:
            obj = s.get(Filament, fid)
            if obj:
                s.delete(obj)
                s.commit()
        self.refresh()