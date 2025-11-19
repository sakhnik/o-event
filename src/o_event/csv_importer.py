from o_event.models import Competitor, Run, Status

import csv
from pathlib import Path


class CSVImporter:

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
                    group=row["Group"].strip().replace(' ', ''),
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
