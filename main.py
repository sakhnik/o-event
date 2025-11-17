#!/usr/bin/env python3

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from iof_importer import IOFImporter

engine = create_engine("sqlite:///race.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

importer = IOFImporter(session)

importer.import_stage(
    "../2025-halloween/15.xml",
    stage_number=1,
    stage_name="Middle"
)
importer.import_stage(
    "../2025-halloween/16.xml",
    stage_number=2,
    stage_name="Sprint"
)
