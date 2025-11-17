#!/usr/bin/env python3

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Race
from iof_importer import IOFImporter

engine = create_engine("sqlite:///o.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Create a race first
race = Race(name="O-Halloween", description="2-day event")
session.add(race)
session.commit()

# Import stage 1
importer = IOFImporter(session)
importer.import_stage("../2025-halloween/15.xml", race_id=race.id, stage_number=1)

# Import stage 2
importer.import_stage("../2025-halloween/16.xml", race_id=race.id, stage_number=2)

print("Import finished!")
