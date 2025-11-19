from o_event.models import Base, Config
from o_event.iof_importer import IOFImporter
from o_event.csv_importer import CSVImporter

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date
from pathlib import Path


def test_all():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    Config.create(session, "O-Halloween", date(2025, 11, 15), "John Doe", "Jane Smith", "Kyiv")
    Config.set(session, Config.KEY_CURRENT_DAY, 1)

    importer = IOFImporter(session)

    data_path = Path(__file__).parent / "data" / "15.xml"
    importer.import_stage(data_path, day=1, stage_name="Спринт")
    data_path = Path(__file__).parent / "data" / "16.xml"
    importer.import_stage(data_path, day=2, stage_name="Середня")

    data_path = Path(__file__).parent / "data" / "runners.csv"
    CSVImporter.import_competitors(session, data_path)
