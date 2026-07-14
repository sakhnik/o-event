import re
import xml.etree.ElementTree as ET
from pathlib import Path

from sqlalchemy import select

from o_event.models import Competitor, Run, Status, Club, Course


class BazImporter:
    cyrillic = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
    latin = "ABVGHDEEZZYIIIKLMNOPRSTUFHCCSS'UA"
    vowels = "AOUIEY'"

    def __init__(self):
        self.clubs = {"": ""}
        self.regs = {"": ""}

    def get_group(self, group: str) -> str:
        return group

    def get_reg(self, club: str) -> str:
        reg = self.clubs.get(club)
        if reg is not None:
            return reg

        trans = ""
        for c in club.upper():
            if c in self.latin or c.isdigit():
                trans += c
                continue

            idx = self.cyrillic.find(c)
            if idx != -1:
                ch = self.latin[idx]
                if ch not in self.vowels:
                    trans += ch

        m = re.search(r"([0-9]+)", trans)
        if m:
            reg = m.group(1)
        else:
            def candidates():
                for i in range(2, len(trans)):
                    yield trans[:2] + trans[i]
                for i in range(10):
                    yield trans[:2] + str(i)

            for candidate in candidates():
                if candidate not in self.regs:
                    reg = candidate
                    break

        self.regs[reg] = club
        self.clubs[club] = reg
        return reg

    def calc_payment(self, group: str, days: int) -> int:
        g = group.replace(" ", "").upper()

        if any(x in g for x in ["21", "35", "45"]):
            base = 400 if days == 2 else 210
        elif any(x in g for x in ["ДОРОСЛІ", "СТУДЕНТИ", "18", "55"]):
            base = 300 if days == 2 else 160
        else:
            base = 200 if days == 2 else 110

        return base + 5 * days

    def import_competitors(self, db, xml_path: Path):
        tree = ET.parse(xml_path)
        root = tree.getroot()

        groups = set(db.execute(select(Course.name)).scalars())

        runners = []

        for s in root.findall("Sportsman"):
            group = self.get_group(s.findtext("Group", ""))

            name = s.findtext("FIO", "")

            prog_event = s.findtext("ProgEvent", "")
            declared_days = [
                int(x)
                for x in prog_event.split(",")
                if x.strip()
            ]

            qual = s.findtext("Qualification", "")
            birthday = s.findtext("Birthday", "")
            year = birthday.split(".")[-1] if birthday else ""

            club = (s.findtext("DUSSH") or s.findtext("Club") or "")

            region = s.findtext("Region", "")
            trainer = s.findtext("Trener", "")

            notes = (
                f"{prog_event}: "
                f"{year}, {qual}, {club}, {region}, {trainer}"
            )

            runners.append({
                "club": club,
                "group": group,
                "name": name,
                "notes": notes,
                "days": declared_days,
            })

        runners.sort(key=lambda r: self.get_reg(r["club"]))

        for sid, runner in enumerate(runners, start=1):
            reg = self.get_reg(runner["club"])

            if runner["club"]:
                exists = db.scalar(
                    select(Club).where(Club.reg == reg)
                )
                if exists is None:
                    db.add(Club(reg=reg, name=runner["club"]))

            if runner["group"] not in groups:
                print(f"{sid} {runner['name']}: невідома група {runner['group']}")

            comp = Competitor(
                reg=reg,
                group=runner["group"],
                sid=sid,
                name=runner["name"],
                notes=runner["notes"] or None,
                money=self.calc_payment(runner["group"], len(runner["days"]),),
                declared_days=runner["days"],
            )

            db.add(comp)
            db.flush()

            for day in runner["days"]:
                db.add(
                    Run(
                        competitor_id=comp.id,
                        day=day,
                        start=None,
                        finish=None,
                        result=None,
                        status=Status.DNS,
                    )
                )

        db.commit()
