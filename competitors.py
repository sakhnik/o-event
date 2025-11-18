import csv
from sqlalchemy.orm import Session
from models import Competitor, Run, Status


def import_competitors(session: Session, filename: str):
    with open(filename, newline='', encoding="utf-8") as f:
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
            session.flush()  # assign comp.id

            # Create empty run info records
            for day in declared_days:
                run = Run(
                    competitor_id=comp.id,
                    day=day,
                    start=None,
                    finish=None,
                    result=None,
                    status=Status.DNS
                )
                session.add(run)

        session.commit()
