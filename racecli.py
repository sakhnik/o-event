#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Competitor, Run, Status


def open_db(path: Path):
    """Create engine + session factory for a race database."""
    engine = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def import_competitors(session, csv_path: Path):
    """Import competitors from CSV into the race DB."""
    with csv_path.open(newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            days_raw = row["Days"].strip()
            declared_days = (
                [int(x) for x in days_raw.split(",")]
                if days_raw else []
            )

            comp = Competitor(
                reg=row["Reg"].strip() or None,
                group=row["Group"].strip(),
                sid=int(row["SID"]),
                first_name=row["First name"].strip(),
                last_name=row["Last name"].strip(),
                notes=(row["Notes"].strip() or None),
                money=int(row["Money"]),
                declared_days=declared_days,
            )

            session.add(comp)
            session.flush()  # comp.id available

            for day in declared_days:
                session.add(
                    Run(
                        competitor_id=comp.id,
                        day=day,
                        start=None,
                        finish=None,
                        result=None,
                        status=Status.DNS,
                    )
                )

        session.commit()


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
        import_competitors(session, args.csv)
        print("Imported competitors.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
