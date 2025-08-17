from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTableWidget, QTableWidgetItem
from database import SessionLocal
from models import PrintJob, Object3D

class QueueTab(QWidget):
    def __init__(self):
        super().__init__()
        self.session = SessionLocal()

        layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Objeto", "Estado"])
        layout.addWidget(self.table)

        add_btn = QPushButton("Agregar a Cola")
        add_btn.clicked.connect(self.add_job)
        layout.addWidget(add_btn)

        process_btn = QPushButton("Procesar Cola")
        process_btn.clicked.connect(self.process_queue)
        layout.addWidget(process_btn)

        self.setLayout(layout)
        self.load_jobs()

    def load_jobs(self):
        self.table.setRowCount(0)
        jobs = self.session.query(PrintJob).all()
        for row_idx, job in enumerate(jobs):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(job.id)))
            self.table.setItem(row_idx, 2, QTableWidgetItem(job.object.name if job.object else "-"))
            self.table.setItem(row_idx, 3, QTableWidgetItem(job.status))

    def add_job(self):
        obj = self.session.query(Object3D).first()
        if obj:
            job = PrintJob(object=obj)
            self.session.add(job)
            self.session.commit()
            self.load_jobs()

    def process_queue(self):
        jobs = self.session.query(PrintJob).filter(PrintJob.status=="pending").all()
        for job in jobs:
            job.status = "done"
        self.session.commit()
        self.load_jobs()