from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Filament(Base):
    __tablename__ = "filaments"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    color = Column(String(80), nullable=True)
    material = Column(String(80), nullable=True)
    price = Column(Integer, nullable=False)
    initial_g = Column(Integer, nullable=False, default=1000)
    remaining_g = Column(Integer, nullable=False, default=1000)
    
    print_job = relationship("PrintJob", back_populates="filament")

class Printer(Base):
    __tablename__ = "printers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    price = Column(Integer, nullable=False)
    wear_per_hour = Column(Float, nullable=False)  # USD/h o CLP/h
    power_kwh_per_hour = Column(Float, nullable=False)  # kWh/h

    print_job = relationship("PrintJob", back_populates="printer")

class Object3D(Base):
    __tablename__ = "objects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(160), nullable=False)
    stl_path = Column(String(255), nullable=False)
    gcode_path = Column(String(255), nullable=False)
    weight_grams = Column(Integer, nullable=False)
    print_time_hours = Column(Float, nullable=False)
    cost = Column(Integer, nullable=False, default=0)
    suggested_price = Column(Integer, nullable=False, default=0)

    print_job = relationship("PrintJob", back_populates="object")

class PrintJob(Base):
    __tablename__ = "print_jobs"

    now = datetime.utcnow

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    object_id = Column(Integer, ForeignKey("objects.id"), nullable=False)
    filament_id = Column(Integer, ForeignKey("filaments.id"), nullable=False)
    printer_id = Column(Integer, ForeignKey("printers.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    hours = Column(Float, nullable=False)
    filament_used_g = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="queued")  # queued|printing|done|canceled
    created_at = Column(DateTime, default=now)
    completed_at = Column(DateTime, default=now)

    object = relationship("Object3D", back_populates="print_job")
    printer = relationship("Printer", back_populates="print_job")
    filament = relationship("Filament", back_populates="print_job")

class GlobalConfig(Base):
    __tablename__ = "global_config"

    id = Column(Integer, primary_key=True, index=True)
    electricity_cost_kwh = Column(Float, default=120.0)  # CLP por kWh en Chile
    profit_margin = Column(Float, default=100.0)         # margen de ganacia
    manual_filament_cost = Column(Float, nullable=True)  # $/gramo
    manual_printer_cost = Column(Float, nullable=True)   # $/hora desgaste
    manual_energy_cost = Column(Float, nullable=True)    # $/hora electricidad
    manual_profit_margin = Column(Float, nullable=True)         # margen de ganacia
    use_manual = Column(Boolean, default=False)          # Si usar manual o promedios