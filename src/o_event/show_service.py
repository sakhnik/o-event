#!/usr/bin/env python3

from o_event.models import Competitor, Run, Config, Status
from o_event.db import SessionLocal
from o_event.ranking import Ranking
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uvicorn

app = FastAPI()

# Allow frontend to fetch JSON from the same server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
print(STATIC_DIR)

# Mount static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def compute_group_results(db: Session, day: int):
    runs = (
        db.query(Run)
        .filter(Run.day == day, Run.status != Status.DNS)
        .join(Competitor)
        .all()
    )

    groups = {}
    for r in runs:
        comp = r.competitor
        g = comp.group
        groups.setdefault(g, []).append(r)

    results = {}

    for group_name, group_runs in groups.items():
        table = []

        for position, time_behind, run in Ranking().rank(group_runs):
            comp = run.competitor
            table.append({
                "position": position,
                "name": f"{comp.last_name} {comp.first_name}",
                "club": comp.club_name,
                "result": run.result,
                "behind": time_behind,
                "status": run.status,
            })

        if table:
            results[group_name] = table

    return results


@app.get("/results")
def get_results():
    """JSON API for browser to poll."""
    db = SessionLocal()
    day = Config.get(db, Config.KEY_CURRENT_DAY)
    data = compute_group_results(db, day)
    db.close()
    return data


@app.get("/")
def index():
    """Serve the kiosk results page by default."""
    return FileResponse(STATIC_DIR / "show.html")


if __name__ == "__main__":
    print("Listening on port 8000...")
    uvicorn.run("show_service:app", host="0.0.0.0", port=8000, reload=False)
