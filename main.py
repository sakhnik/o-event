#!/usr/bin/env python3

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Config
from iof_importer import IOFImporter
from datetime import date

engine = create_engine("sqlite:///race.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()


Config.set(session, "name", "O-Halloween")
Config.set(session, "start_date", date(2025, 11, 15))
Config.set(session, "current_day", 1)
Config.set(session, "judge", "John Doe")
Config.set(session, "secretary", "Jane Smith")
Config.set(session, "place", "Kyiv")

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
