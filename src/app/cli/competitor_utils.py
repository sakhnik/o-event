from rapidfuzz import fuzz
from typing import Tuple, List
import subprocess

from o_event.models import Competitor, Run, Status
from sqlalchemy.inspection import inspect
from app.cli.editor import Editor


class CompetitorUtils:
    def __init__(self, db):
        self.db = db

    def get_columns(self, model):
        return [c.key for c in inspect(model).mapper.column_attrs]

    def competitor_to_dict(self, c: Competitor):
        comp_dict = {col: getattr(c, col) for col in self.get_columns(Competitor)}
        comp_dict["runs"] = [
            {col: getattr(r, col) if col != "status" else (r.status.value if r.status else None)
             for col in self.get_columns(Run)}
            for r in c.runs
        ]
        return comp_dict

    def update_competitor_from_dict(self, d: dict):
        comp_columns = self.get_columns(Competitor)
        run_columns = self.get_columns(Run)

        # Create or fetch competitor
        if "id" not in d or d["id"] is None:
            comp = Competitor()
            self.db.add(comp)
            self.db.flush()
        else:
            comp = self.db.get(Competitor, d["id"])
            if comp is None:
                raise ValueError(f"Competitor id {d['id']} not found")

        # Update competitor fields dynamically
        for col in comp_columns:
            if col in d and col != "id":  # don't overwrite primary key
                setattr(comp, col, d[col])

        # Update runs
        existing_by_id = {r.id: r for r in comp.runs if r.id is not None}
        seen_existing_ids = set()

        for rd in d.get("runs", []):
            if "id" in rd and rd["id"] in existing_by_id:
                r = existing_by_id[rd["id"]]
                seen_existing_ids.add(rd["id"])
            else:
                r = Run()
                r.competitor = comp
                self.db.add(r)

            for col in run_columns:
                if col in rd and col != "id":  # don't overwrite primary key
                    setattr(r, col, rd[col])

            # Handle enum status separately
            st = rd.get("status")
            if hasattr(Run, "status"):
                if st is None:
                    r.status = None
                else:
                    r.status = Status(st) if st in Status._value2member_map_ else None

        # Remove deleted runs
        for r in list(comp.runs):
            if r.id is not None and r.id not in seen_existing_ids:
                self.db.delete(r)

        self.db.flush()
        return comp

    def filter_competitors(self, query: str = None) -> List[Tuple[int, Competitor]]:
        comps = self.db.query(Competitor).all()
        results = []

        for c in comps:
            name = c.name or ""
            group = c.group or ""
            notes = c.notes or ""
            reg = c.reg or ""

            # If no query, include everything
            if not query:
                results.append((100, c))  # 100 score to keep original order
                continue

            # Compute fuzzy score across multiple fields
            score = max(
                fuzz.partial_ratio(query.lower(), name.lower()),
                fuzz.partial_ratio(query.lower(), group.lower()),
                fuzz.partial_ratio(query.lower(), notes.lower()),
                fuzz.partial_ratio(query.lower(), reg.lower()),
            )

            if score >= 75:  # threshold for matching
                results.append((score, c))

        results.sort(key=lambda x: x[0])
        return results

    def ls_competitors(self, query: str = None):
        for score, c in self.filter_competitors(query):
            name = c.name or ""
            group = c.group or ""
            declared = c.declared_days or []
            notes = c.notes or ''
            print(f"{c.sid:3} | {c.reg or '':6} | {name:20} | {group:6} | {declared} | {notes}")

    def pick_competitor(self, query: str = None) -> Competitor | None:
        """
        Show competitors in fzf and return the chosen Competitor.
        """
        items = self.filter_competitors(query)

        # Prepare the input for fzf
        lines = []
        for score, c in reversed(items):
            name = c.name or ""
            group = c.group or ""
            declared = c.declared_days or []
            notes = c.notes or ''
            line = f"{c.id:3} | {c.reg or '':6} | {c.sid:3} | {name:20} | {group:6} | {declared} | {notes}"
            lines.append(line)

        # Invoke fzf
        try:
            out = subprocess.check_output(
                ["fzf", "--ansi"],
                input="\n".join(lines),
                text=True,
            ).strip()
        except subprocess.CalledProcessError:
            return None  # user cancelled with ESC or Ctrl-C

        chosen_id = int(out.split()[0])
        return chosen_id

    def edit_competitor(self, cid: int):
        comp = self.db.get(Competitor, cid)
        if not comp:
            print(f"No competitor with ID {cid}")
            return
        comp_dict = self.competitor_to_dict(comp)
        edited, changed = Editor().edit_yaml(comp_dict)
        if changed:
            self.update_competitor_from_dict(edited)
            self.db.commit()
            print(f"Competitor {cid} updated.")
        else:
            print("No changes made. Aborted.")

    def add_competitor(self):
        skeleton = {
            "id": None,
            "reg": "",
            "group": "",
            "sid": None,
            "name": "",
            "representative": "",
            "notes": "",
            "money": None,
            "declared_days": [],
            "runs": [],
        }
        edited, changed = Editor().edit_yaml(skeleton)
        if changed:
            self.update_competitor_from_dict(edited)
            self.db.commit()
            print("Added new competitor.")
        else:
            print("No changes made. Aborted.")
