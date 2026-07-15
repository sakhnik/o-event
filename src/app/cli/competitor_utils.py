from o_event.models import Competitor, Run, Status
from sqlalchemy.inspection import inspect


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
