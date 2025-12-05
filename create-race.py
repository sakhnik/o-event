#!/usr/bin/env python3

from o_event.models import Config, Base
from o_event.iof_importer import IOFImporter
from o_event.db import SessionLocal, ENGINE

from datetime import date

Base.metadata.create_all(ENGINE)
session = SessionLocal()


Config.create(session, "ХІІ відкриті змагання з орієнтування в приміщеннях до Дня Святого Миколая", date(2025, 12, 6), "Білошицький В.М.", "Сахнік А.М.", "Київ")
Config.set(session, Config.KEY_CURRENT_DAY, 1)

importer = IOFImporter(session)

importer.import_stage(
    "06.xml",
    day=1,
    stage_name="Корпус №12 НУБіП"
)
importer.import_stage(
    "07.xml",
    day=2,
    stage_name="Ліцей №76"
)
