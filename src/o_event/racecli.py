#!/usr/bin/env python3

from o_event.csv_importer import CSVImporter
from o_event.models import Base

import argparse
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def open_db(path: Path):
    """Create engine + session factory for a race database."""
    engine = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def main():
    parser = argparse.ArgumentParser(
        description="Orienteering race management tools"
    )
    sub = parser.add_subparsers(dest="cmd")

    # ------------------------------------------------------------
    # import competitors
    # ------------------------------------------------------------
    imp = sub.add_parser("import-competitors",
                         help="Import competitors from CSV")
    imp.add_argument("db", type=Path, help="Race DB file (SQLite)")
    imp.add_argument("csv", type=Path, help="Competitors CSV file")

    args = parser.parse_args()

    if args.cmd == "import-competitors":
        Session = open_db(args.db)
        session = Session()
        CSVImporter.import_competitors(session, args.csv)
        print("Imported competitors.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
