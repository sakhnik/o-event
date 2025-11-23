#!/usr/bin/env python3

from o_event.csv_importer import CSVImporter
from o_event.db import SessionLocal
from pathlib import Path

session = SessionLocal()


CSVImporter().import_competitors(session, Path('runners.csv'))
CSVImporter().import_clubs(session, Path('clubs.csv'))
