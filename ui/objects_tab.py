from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QLineEdit, QFormLayout, QDoubleSpinBox, QHeaderView, QMessageBox, QDialog, QCheckBox, QHBoxLayout
from database import SessionLocal
from models import Object3D, GlobalConfig, Filament, Printer

class ConfigDialog(QDialog):
    def __init__(self, session):
        super().__init__()
        self.setWindowTitle("Configuración de Costos")
        self.session = session

        config = session.query(GlobalConfig).first()
        if not config:
            config = GlobalConfig()
            session.add(config)
            session.commit()
        self.config = config

        layout = QVBoxLayout()
        form = QFormLayout()

        self.manual_check = QCheckBox("Usar valores manuales")
        self.manual_check.setChecked(config.use_manual)

        self.filament_cost = QDoubleSpinBox(); self.filament_cost.setMaximum(1000); self.filament_cost.setValue(config.manual_filament_cost or 0)
        self.energy_cost = QDoubleSpinBox(); self.energy_cost.setMaximum(10000); self.energy_cost.setValue(config.manual_energy_cost or 0)
        self.wear_cost = QDoubleSpinBox(); self.wear_cost.setMaximum(10000); self.wear_cost.setValue(config.manual_printer_cost or 0)

        form.addRow(self.manual_check)
        form.addRow("Costo por gramo:", self.filament_cost)
        form.addRow("Costo por hora electricidad:", self.energy_cost)
        form.addRow("Costo por hora desgaste:", self.wear_cost)

        save_btn = QPushButton("Guardar")
        save_btn.clicked.connect(self.save_config)

        layout.addLayout(form)
        layout.addWidget(save_btn)
        self.setLayout(layout)

    def save_config(self):
        self.config.use_manual = self.manual_check.isChecked()
        self.config.manual_filament_cost = self.filament_cost.value()
        self.config.manual_energy_cost = self.energy_cost.value()
        self.config.manual_printer_cost = self.wear_cost.value()
        self.session.commit()
        self.accept()

class ObjectsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.session = SessionLocal()
        self.selected_id = None

        layout = QVBoxLayout()

        # Tabla de objetos
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "Ruta del Modelo", "Ruta del Gcode", "Objetos", "Peso (g)", "Tiempo de Impresión (h)", "Costo Unitario", "Precio Unitario Sugerido"])
        self.header = self.table.horizontalHeader()
        self.header.setSectionResizeMode(QHeaderView.Interactive)
        self.header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.cellClicked.connect(self.on_row_selected)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)

        # Formulario
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.model_input = QLineEdit()
        self.gcode_input = QLineEdit()
        self.objects_input = QDoubleSpinBox(); self.objects_input.setDecimals(0); self.objects_input.setMaximum(1e2)
        self.weight_input = QDoubleSpinBox(); self.weight_input.setDecimals(0); self.weight_input.setMaximum(1e4)
        self.time_input = QDoubleSpinBox(); self.time_input.setDecimals(2); self.time_input.setMaximum(1e3)
        form.addRow("Nombre:", self.name_input)
        form.addRow("Ruta del Modelo:", self.model_input)
        form.addRow("Ruta del Gcode:", self.gcode_input)
        form.addRow("Objetos en el archivo:", self.objects_input)
        form.addRow("Peso (g):", self.weight_input)
        form.addRow("Tiempo de impresión (h):", self.time_input)
        layout.addLayout(form)

        # Botones
        self.add_btn = QPushButton("Agregar Objeto")
        self.add_btn.clicked.connect(self.add_object)

        self.update_btn = QPushButton("Guardar Cambios")
        self.update_btn.clicked.connect(self.update_object)
        self.update_btn.setEnabled(False)

        self.delete_btn = QPushButton("Eliminar Objeto")
        self.delete_btn.clicked.connect(self.delete_object)
        self.delete_btn.setEnabled(False)

        layout.addWidget(self.add_btn)
        layout.addWidget(self.update_btn)
        layout.addWidget(self.delete_btn)

        self.setLayout(layout)
        self.load_objects()

        self.config_btn = QPushButton("⚙️ Configuración")
        self.config_btn.clicked.connect(self.open_config_window)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.config_btn)
        layout.addLayout(bottom_layout)

    def get_cost_parameters_and_profit_margin(self):
        config = self.session.query(GlobalConfig).first()
        if not config:
            config = GlobalConfig()
            self.session.add(config)
            self.session.commit()

        if config.use_manual:
            return (
                config.manual_filament_cost or 0,
                config.manual_energy_cost or 0,
                config.manual_printer_cost or 0,
                config.manual_profit_margin or 0
            )

        filaments = self.session.query(Filament).all()
        printers = self.session.query(Printer).all()

        costo_gramo = sum(f.price/f.initial_g for f in filaments)/len(filaments) if filaments else 0
        costo_kwh = (sum(p.power_kwh_per_hour for p in printers)/len(printers))*config.electricity_cost_kwh if printers else config.electricity_cost_kwh
        costo_desgaste = sum(p.wear_per_hour for p in printers)/len(printers) if printers else 0

        return (costo_gramo, costo_kwh, costo_desgaste, config.profit_margin)

    def on_row_selected(self, row, col):
        self.update_btn.setEnabled(True)
        self.selected_id = int(self.table.item(row, 0).text())
        self.name_input.setText(self.table.item(row, 1).text())
        self.model_input.setText(self.table.item(row, 2).text())
        self.gcode_input.setText(self.table.item(row, 3).text())
        self.objects_input.setValue(int(self.table.item(row, 4).text()))
        self.weight_input.setValue(int(self.table.item(row, 5).text()))
        self.time_input.setValue(float(self.table.item(row, 6).text()))

    def load_form_from_selection(self, selected):
        row = selected[0].row()
        self.current_object_data = {
            "id": self.table.item(row, 0),
            "nombre": self.table.item(row, 1).text(),
            "model_path": self.table.item(row, 2).text(),
            "gcode_path": self.table.item(row, 3).text(),
            "objetos": int(self.table.item(row, 4).text()),
            "peso": int(self.table.item(row, 5).text()),
            "tiempo": float(self.table.item(row, 6).text()),
        }
        self.name_input.setText(self.current_object_data["nombre"])
        self.model_input.setText(self.current_object_data["model_path"])
        self.gcode_input.setText(self.current_object_data["gcode_path"])
        self.objects_input.setValue(self.current_object_data["objetos"])
        self.weight_input.setValue(self.current_object_data["peso"])
        self.time_input.setValue(self.current_object_data["tiempo"])

    def on_selection_changed(self):
        selected = self.table.selectedItems()
        if not selected:
            self.clear_form()
            self.add_btn.setEnabled(True)
            self.update_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
        else:
            self.load_form_from_selection(selected)
            self.add_btn.setEnabled(False)
            self.update_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)

    def add_object(self):

        q = int(self.objects_input.value())

        obj = Object3D(
            name=self.name_input.text(),
            stl_path=self.model_input.text(),
            gcode_path=self.gcode_input.text(),
            objects=q,
            weight_grams=int(self.weight_input.value()),
            print_time_hours=float(self.time_input.value())
        )

        costo_gramo, costo_kwh, costo_desgaste, profit_margin = self.get_cost_parameters_and_profit_margin()
        cost = int((obj.weight_grams * costo_gramo + obj.print_time_hours * costo_kwh + obj.print_time_hours * costo_desgaste) / q)
        obj.cost = (cost)

        suggested_price = int(cost * ((profit_margin / 100.0) + 1))
        obj.suggested_price = (suggested_price)

        self.session.add(obj)
        self.session.commit()
        self.load_objects()
        self.clear_form()

    def load_objects(self):
        self.table.setRowCount(0)
        objects = self.session.query(Object3D).all()
        for row_idx, obj in enumerate(objects):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(obj.id)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(obj.name))
            self.table.setItem(row_idx, 2, QTableWidgetItem(obj.stl_path))
            self.table.setItem(row_idx, 3, QTableWidgetItem(obj.gcode_path))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(obj.objects)))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(obj.weight_grams)))
            self.table.setItem(row_idx, 6, QTableWidgetItem(str(obj.print_time_hours)))
            self.table.setItem(row_idx, 7, QTableWidgetItem(str(obj.cost)))
            self.table.setItem(row_idx, 8, QTableWidgetItem(str(obj.suggested_price)))

    def update_object(self):
        new_data = {
            "nombre": self.name_input.text(),
            "model_path": self.model_input.text(),
            "gcode_path": self.gcode_input.text(),
            "objetos": int(self.objects_input.value()),
            "peso": int(self.weight_input.value()),
            "tiempo": self.time_input.value()
        }

        if (new_data["nombre"] == self.current_object_data["nombre"]) and (new_data["model_path"] == self.current_object_data["model_path"]) and (new_data["gcode_path"] == self.current_object_data["gcode_path"]) and (new_data["objetos"] == self.current_object_data["objetos"]) and (new_data["peso"] == self.current_object_data["peso"]) and (new_data["tiempo"] == self.current_object_data["tiempo"]):
            QMessageBox.information(self, "Sin cambios", "No se han realizado modificaciones.")
            return
        
        self.apply_update()

    def apply_update(self):
        if not self.selected_id:
            QMessageBox.warning(self, "Error", "No has seleccionado ningún objeto para actualizar.")
            return

        obj = self.session.query(Object3D).filter_by(id=self.selected_id).first()
        if obj:

            w = int(self.weight_input.value())
            h = float(self.time_input.value())
            q = int(self.objects_input.value())

            obj.name = self.name_input.text()
            obj.stl_path = self.model_input.text()
            obj.gcode_path = self.gcode_input.text()
            obj.objects = q
            obj.weight_grams = w
            obj.print_time_hours = h

            costo_gramo, costo_kwh, costo_desgaste, profit_margin = self.get_cost_parameters_and_profit_margin()
            cost = int(
                (w * costo_gramo +
                h * costo_kwh +
                h * costo_desgaste) / q
            )
            obj.cost = (cost)

            suggested_price = int(cost * ((profit_margin / 100.0) + 1))
            obj.suggested_price = (suggested_price)

            self.session.commit()
            self.load_objects()
            self.clear_form()
            QMessageBox.information(self, "Éxito", "Objeto actualizado correctamente.")

    def delete_object(self):
        if not self.selected_id:
            return

        confirm = QMessageBox.question(
            self,
            "Confirmar eliminación",
            "¿Estás seguro de que deseas eliminar este objeto?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            obj = self.session.query(Object3D).filter_by(id=self.selected_id).first()
            if obj:
                self.session.delete(obj)
                self.session.commit()
                self.load_objects()
                self.clear_form()
                QMessageBox.information(self, "Éxito", "Objeto eliminado correctamente.")

    def clear_form(self):
        self.selected_id = None
        self.name_input.clear()
        self.model_input.clear()
        self.gcode_input.clear()
        self.objects_input.setValue(0)
        self.weight_input.setValue(0)
        self.time_input.setValue(0.0)

    def open_config_window(self):
        dlg = ConfigDialog(self.session)
        if dlg.exec():
            self.load_objects()