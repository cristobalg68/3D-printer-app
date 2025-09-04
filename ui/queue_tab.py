from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QDialog, QFormLayout, 
    QComboBox, QDialogButtonBox, QDoubleSpinBox
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Signal, QObject
from database import SessionLocal
from models import PrintJob, Object3D, Filament, Printer
from datetime import datetime

class AddJobDialog(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agregar a la cola")
        self.session = session

        layout = QFormLayout()

        self.obj_combo = QComboBox()
        self.objects = self.session.query(Object3D).all()
        for obj in self.objects:
            self.obj_combo.addItem(obj.name, obj.id)
        layout.addRow("Objeto:", self.obj_combo)

        self.filament_combo = QComboBox()
        self.filaments = self.session.query(Filament).all()
        for f in self.filaments:
            self.filament_combo.addItem(f.name, f.id)
        layout.addRow("Filamento:", self.filament_combo)

        self.printer_combo = QComboBox()
        self.printers = self.session.query(Printer).all()
        for p in self.printers:
            self.printer_combo.addItem(p.name, p.id)
        layout.addRow("Impresora:", self.printer_combo)

        self.quantity_spinbox = QDoubleSpinBox(); self.quantity_spinbox.setDecimals(0); self.quantity_spinbox.setMaximum(1e2)
        layout.addRow("Cantidad:", self.quantity_spinbox)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

    def get_selection(self):
        obj_id = self.obj_combo.currentData()
        filament_id = self.filament_combo.currentData()
        printer_id = self.printer_combo.currentData()
        quantity = int(self.quantity_spinbox.value())

        obj = self.session.query(Object3D).get(obj_id)
        filament = self.session.query(Filament).get(filament_id)
        printer = self.session.query(Printer).get(printer_id)

        return obj, filament, printer, quantity
    
class ProcessJobDialog(QDialog):
    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Procesar trabajo")
        self.job = job

        layout = QFormLayout()

        self.action_combo = QComboBox()
        self.action_combo.addItems(["Terminado", "Imprimiendo", "Cancelado", "Eliminado"])
        layout.addRow("Acción:", self.action_combo)

        self.partial_time = QDoubleSpinBox()
        self.partial_time.setDecimals(2)
        self.partial_time.setMaximum(job.hours or 1000)
        self.partial_time.setEnabled(False)
        layout.addRow("Tiempo impreso (h):", self.partial_time)

        self.action_combo.currentTextChanged.connect(
            lambda text: self.partial_time.setEnabled(text == "Cancelado")
        )

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

    def get_action(self):
        return self.action_combo.currentText(), self.partial_time.value()

class QueueTab(QWidget):
    job_created = Signal(str)

    def __init__(self):
        super().__init__()
        self.session = SessionLocal()

        layout = QVBoxLayout()

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Objeto", "Filamento", "Cantidad", "Estado"])
        self.header = self.table.horizontalHeader()
        self.header.setSectionResizeMode(QHeaderView.Interactive)
        self.header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)

        add_btn = QPushButton("Agregar a Cola")
        add_btn.clicked.connect(self.add_job)
        layout.addWidget(add_btn)

        self.process_btn = QPushButton("Procesar Trabajo")
        self.process_btn.clicked.connect(self.process_queue)
        self.process_btn.setEnabled(False)
        layout.addWidget(self.process_btn)

        self.setLayout(layout)
        self.load_jobs()

    def load_jobs(self):
        self.table.setRowCount(0)
        jobs = self.session.query(PrintJob).filter(PrintJob.status.in_(["pending", "printing"])).all()
        for row_idx, job in enumerate(jobs):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(job.id)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(job.object.name if job.object else "-"))
            self.table.setItem(row_idx, 2, QTableWidgetItem(job.filament.name if job.filament else "-"))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(job.quantity)))
            status_item = QTableWidgetItem(job.status)

            # Colorear según estado
            if job.status == "printing":
                status_item.setBackground(QColor("yellow"))
            elif job.status == "pending":
                status_item.setBackground(QColor("lightgreen"))

            self.table.setItem(row_idx, 4, status_item)

    def on_selection_changed(self):
        selected = self.table.selectedItems()
        self.process_btn.setEnabled(bool(selected))

    def add_job(self):
        dialog = AddJobDialog(self.session, self)
        if dialog.exec() == QDialog.Accepted:
            obj, filament, printer, quantity = dialog.get_selection()
            if obj and filament and printer:

                total_hours = obj.print_time_hours * quantity
                total_filament = obj.weight_grams * quantity

                job = PrintJob(
                    object=obj,
                    filament=filament,
                    printer=printer,
                    quantity=quantity,
                    hours=total_hours,
                    filament_used_g=total_filament,
                    status="pending"
                )
                self.session.add(job)

                filament.remaining_g_projected -= total_filament

                self.session.commit()
                self.load_jobs()
                self.job_created.emit("Job Created")

    def process_queue(self):
        selected = self.table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        job_id = int(self.table.item(row, 0).text())
        job = self.session.query(PrintJob).get(job_id)
        filament = job.filament

        dialog = ProcessJobDialog(job, self)
        if dialog.exec() == QDialog.Accepted:
            action, partial_time = dialog.get_action()

            if action == "Eliminado":
                filament.remaining_g_projected += job.filament_used_g
                self.session.delete(job)

            elif action == "Cancelado":
                filament.remaining_g_projected += job.filament_used_g

                if partial_time > 0 and job.hours:
                    ratio = partial_time / job.hours
                    used = job.filament_used_g * ratio

                    job.hours = partial_time
                    job.filament_used_g = used

                    filament.remaining_g_projected -= used
                    filament.remaining_g_effective -= used

                job.status = "cancelled"

            elif action == "Imprimiendo":
                job.status = "printing"

            elif action == "Terminado":
                job.status = "done"
                job.completed_at = datetime.utcnow()
                filament.remaining_g_effective -= job.filament_used_g

            self.session.commit()
            self.load_jobs()
            self.job_created.emit("Job Update")