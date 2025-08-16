"""
App de gestión de impresión 3D (MVP)
Tecnologías: Python 3.10+, PySide6, SQLAlchemy (SQLite)

Características incluidas en este MVP:
- Base de datos SQLite con tablas: Filament, Printer, Object3D, PrintJob.
- Ventana principal con pestañas (QTabWidget): Filamentos, Impresoras, Objetos, Cola de impresión.
- CRUD básico funcional para Filamentos e Impresoras (crear, editar, eliminar).
- Modelos y capa de acceso a datos con SQLAlchemy ORM.
- Validaciones mínimas y cálculos auxiliares (ej: costo por hora de energía = consumo_kwh * precio_kwh).

Próximos pasos sugeridos (no incluidos aún para mantener el tamaño del MVP):
- CRUD completo para Objetos y Cola.
- Cálculo automático del costo total del objeto (energía + filamento + desgaste por hora) y precio con markup.
- Vistas de reportes (recupero de inversión de impresoras, historial de uso por filamento).
- Exportar a CSV/Excel y gráficos.

Cómo ejecutar:
1) Crear venv e instalar dependencias
   python -m venv .venv
   \
   # Windows
   .venv\\Scripts\\activate
   \
   # macOS/Linux
   source .venv/bin/activate
   
   pip install PySide6 SQLAlchemy

2) Ejecutar
   python app_3dprint_mvp.py

3) Empaquetar como ejecutable (opcional)
   pip install pyinstaller
   pyinstaller --noconfirm --windowed --name "GestionImpresion3D" --icon=icon.ico app_3dprint_mvp.py

"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional, List

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QTabWidget,
    QDialog,
    QFormLayout,
    QSpinBox,
    QDoubleSpinBox,
)

from sqlalchemy import (
    create_engine,
    Integer,
    Float,
    String,
    ForeignKey,
    DateTime,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

# ==========================
#  Base de datos (ORM)
# ==========================

class Base(DeclarativeBase):
    pass

class Filament(Base):
    __tablename__ = "filaments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str] = mapped_column(String(80), nullable=True)
    price_per_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    initial_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    remaining_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # relación con trabajos de impresión
    print_jobs: Mapped[List[PrintJob]] = relationship(back_populates="filament")

class Printer(Base):
    __tablename__ = "printers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # precio de compra
    wear_per_hour: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # USD/h o CLP/h
    power_kwh_per_hour: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # kWh/h
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    print_jobs: Mapped[List[PrintJob]] = relationship(back_populates="printer")

class Object3D(Base):
    __tablename__ = "objects3d"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    stl_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gcode_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    est_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    est_filament_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    margin_pct: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)  # 100% = x2
    
    # parámetros por defecto para cálculo (se pueden sobreescribir por pedido)
    energy_price_per_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    filament_id: Mapped[Optional[int]] = mapped_column(ForeignKey("filaments.id"), nullable=True)
    printer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("printers.id"), nullable=True)

class PrintJob(Base):
    __tablename__ = "print_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(ForeignKey("objects3d.id"), nullable=False)
    filament_id: Mapped[int] = mapped_column(ForeignKey("filaments.id"), nullable=False)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    filament_used_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    energy_price_per_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # precio final por unidad (con margen)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")  # queued|printing|done|canceled
    created_at: Mapped[QtCore.QDateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    filament: Mapped[Filament] = relationship(back_populates="print_jobs")
    printer: Mapped[Printer] = relationship(back_populates="print_jobs")

# ==========================
#  Capa de persistencia
# ==========================

def get_engine(db_path: str = "sqlite:///impresion3d.db"):
    return create_engine(db_path, echo=False, future=True)

Engine = get_engine()
SessionLocal = sessionmaker(bind=Engine, expire_on_commit=False)
Base.metadata.create_all(Engine)

# ==========================
#  Utilidades de UI
# ==========================

def info(msg: str, parent=None):
    QMessageBox.information(parent, "Información", msg)

def error(msg: str, parent=None):
    QMessageBox.critical(parent, "Error", msg)

# ==========================
#  Diálogos de Filamentos
# ==========================

class FilamentDialog(QDialog):
    def __init__(self, parent=None, data: Optional[Filament] = None):
        super().__init__(parent)
        self.setWindowTitle("Filamento")
        self.resize(400, 200)
        layout = QFormLayout(self)

        self.e_name = QLineEdit()
        self.e_color = QLineEdit()
        self.e_price = QDoubleSpinBox()
        self.e_price.setDecimals(4)
        self.e_price.setMaximum(1e9)
        self.e_initial = QDoubleSpinBox()
        self.e_initial.setDecimals(4)
        self.e_initial.setMaximum(1e6)
        self.e_remaining = QDoubleSpinBox()
        self.e_remaining.setDecimals(4)
        self.e_remaining.setMaximum(1e6)
        self.e_notes = QLineEdit()

        layout.addRow("Nombre*", self.e_name)
        layout.addRow("Color", self.e_color)
        layout.addRow("Precio/kg", self.e_price)
        layout.addRow("Kg iniciales", self.e_initial)
        layout.addRow("Kg restantes", self.e_remaining)
        layout.addRow("Notas", self.e_notes)

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
            self.e_color.setText(data.color or "")
            self.e_price.setValue(data.price_per_kg or 0.0)
            self.e_initial.setValue(data.initial_kg or 0.0)
            self.e_remaining.setValue(data.remaining_kg or 0.0)
            self.e_notes.setText(data.notes or "")

    def get_values(self) -> dict:
        name = self.e_name.text().strip()
        if not name:
            raise ValueError("El nombre es obligatorio")
        return dict(
            name=name,
            color=self.e_color.text().strip() or None,
            price_per_kg=float(self.e_price.value()),
            initial_kg=float(self.e_initial.value()),
            remaining_kg=float(self.e_remaining.value()),
            notes=self.e_notes.text().strip() or None,
        )

# ==========================
#  Diálogos de Impresoras
# ==========================

class PrinterDialog(QDialog):
    def __init__(self, parent=None, data: Optional[Printer] = None):
        super().__init__(parent)
        self.setWindowTitle("Impresora")
        self.resize(400, 220)
        layout = QFormLayout(self)

        self.e_name = QLineEdit()
        self.e_price = QDoubleSpinBox(); self.e_price.setMaximum(1e9)
        self.e_wear = QDoubleSpinBox(); self.e_wear.setMaximum(1e6); self.e_wear.setDecimals(4)
        self.e_power = QDoubleSpinBox(); self.e_power.setMaximum(1e6); self.e_power.setDecimals(4)
        self.e_notes = QLineEdit()

        layout.addRow("Nombre*", self.e_name)
        layout.addRow("Precio compra", self.e_price)
        layout.addRow("Desgaste/hora", self.e_wear)
        layout.addRow("kWh por hora", self.e_power)
        layout.addRow("Notas", self.e_notes)

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
            self.e_price.setValue(data.price or 0.0)
            self.e_wear.setValue(data.wear_per_hour or 0.0)
            self.e_power.setValue(data.power_kwh_per_hour or 0.0)
            self.e_notes.setText(data.notes or "")

    def get_values(self) -> dict:
        name = self.e_name.text().strip()
        if not name:
            raise ValueError("El nombre es obligatorio")
        return dict(
            name=name,
            price=float(self.e_price.value()),
            wear_per_hour=float(self.e_wear.value()),
            power_kwh_per_hour=float(self.e_power.value()),
            notes=self.e_notes.text().strip() or None,
        )

# ==========================
#  Widgets de lista (Tablas)
# ==========================

class FilamentTab(QWidget):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
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

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID","Nombre","Color","Precio/kg","Kg iniciales","Kg restantes"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
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
        with self.session_factory() as s:
            q = s.query(Filament)
            items = q.all()
        if text:
            items = [i for i in items if (text in (i.name or "").lower()) or (text in (i.color or "").lower())]
        self.table.setRowCount(len(items))
        for r, it in enumerate(items):
            self.table.setItem(r, 0, QTableWidgetItem(str(it.id)))
            self.table.setItem(r, 1, QTableWidgetItem(it.name))
            self.table.setItem(r, 2, QTableWidgetItem(it.color or ""))
            self.table.setItem(r, 3, QTableWidgetItem(f"{it.price_per_kg:.3f}"))
            self.table.setItem(r, 4, QTableWidgetItem(f"{it.initial_kg:.3f}"))
            self.table.setItem(r, 5, QTableWidgetItem(f"{it.remaining_kg:.3f}"))

    def add_item(self):
        dlg = FilamentDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                values = dlg.get_values()
            except ValueError as e:
                error(str(e), self)
                return
            with self.session_factory() as s:
                obj = Filament(**values)
                s.add(obj)
                s.commit()
            self.refresh()

    def edit_item(self):
        fid = self.current_id()
        if not fid:
            info("Selecciona un filamento primero", self)
            return
        with self.session_factory() as s:
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
        with self.session_factory() as s:
            obj = s.get(Filament, fid)
            if obj:
                s.delete(obj)
                s.commit()
        self.refresh()

class PrinterTab(QWidget):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.session_factory = session_factory
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

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID","Nombre","Precio","Desgaste/h","kWh/h","Notas"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
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
        with self.session_factory() as s:
            items = s.query(Printer).all()
        if text:
            items = [i for i in items if text in (i.name or "").lower()]
        self.table.setRowCount(len(items))
        for r, it in enumerate(items):
            self.table.setItem(r, 0, QTableWidgetItem(str(it.id)))
            self.table.setItem(r, 1, QTableWidgetItem(it.name))
            self.table.setItem(r, 2, QTableWidgetItem(f"{it.price:.2f}"))
            self.table.setItem(r, 3, QTableWidgetItem(f"{it.wear_per_hour:.4f}"))
            self.table.setItem(r, 4, QTableWidgetItem(f"{it.power_kwh_per_hour:.4f}"))
            self.table.setItem(r, 5, QTableWidgetItem(it.notes or ""))

    def add_item(self):
        dlg = PrinterDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                values = dlg.get_values()
            except ValueError as e:
                error(str(e), self)
                return
            with self.session_factory() as s:
                obj = Printer(**values)
                s.add(obj)
                s.commit()
            self.refresh()

    def edit_item(self):
        pid = self.current_id()
        if not pid:
            info("Selecciona una impresora primero", self)
            return
        with self.session_factory() as s:
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
        with self.session_factory() as s:
            obj = s.get(Printer, pid)
            if obj:
                s.delete(obj)
                s.commit()
        self.refresh()

# ==========================
#  Ventana principal
# ==========================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestión de Impresión 3D – MVP")
        self.resize(1000, 650)

        tabs = QTabWidget()
        tabs.addTab(FilamentTab(SessionLocal), "Filamentos")
        tabs.addTab(PrinterTab(SessionLocal), "Impresoras")
        # Tabs placeholder para futuras iteraciones
        tabs.addTab(QWidget(), "Objetos (próx)")
        tabs.addTab(QWidget(), "Cola de impresión (próx)")

        self.setCentralWidget(tabs)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
