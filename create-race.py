#!/usr/bin/env python3

from o_event.models import Config, Base
from o_event.iof_importer import IOFImporter
from o_event.db import SessionLocal, ENGINE

from datetime import date

Base.metadata.create_all(ENGINE)
session = SessionLocal()


Config.create(session, "O-Halloween", date(2025, 11, 15), "John Doe", "Jane Smith", "Kyiv")
Config.set(session, Config.KEY_CURRENT_DAY, 1)

importer = IOFImporter(session)

importer.import_stage(
    "../2025-halloween/15.xml",
    day=1,
    stage_name="Спринт"
)
importer.import_stage(
    "../2025-halloween/16.xml",
    day=2,
    stage_name="Середня"
)
