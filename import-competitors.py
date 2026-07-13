#!/usr/bin/env python3

from o_event.baz_importer import BazImporter
from o_event.db import SessionLocal
from pathlib import Path

session = SessionLocal()


BazImporter().import_competitors(session, Path('baz3982.xml'))
