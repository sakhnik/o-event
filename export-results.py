#!/usr/bin/env python3

import argparse
from sqlalchemy.orm import Session
from datetime import timedelta

from jinja2 import Environment, FileSystemLoader, select_autoescape

from o_event.models import Run, RunSplit, Competitor, Stage, Course, CourseControl, Status, Config
from o_event.ranking import Ranking
from o_event.db import SessionLocal


# -------------------------------------------------------
# Helpers
# -------------------------------------------------------

def fmt(t):
    if t is None:
        return ""
    if t < 3600:
        return f"{t // 60}:{t % 60:02}"
    return str(timedelta(seconds=t))


def diff(base, t):
    if base is None or t is None:
        return ""
    d = t - base
    return "+" + fmt(d) if d > 0 else ""


# -------------------------------------------------------
# Template loading
# -------------------------------------------------------

env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(["html", "xml"])
)
env.filters["fmt"] = fmt
env.filters["diff"] = diff


# -------------------------------------------------------
# Data extraction
# -------------------------------------------------------

def load_day_results(db: Session, day: int):
    q = (
        db.query(Run)
        .join(Run.competitor)
        .filter(Run.day == day, Run.status != Status.DNS)
        .order_by(Competitor.group, Run.result.asc().nullslast())
    )
    runs = q.all()

    groups = {}
    for run in runs:
        g = run.competitor.group
        groups.setdefault(g, []).append(run)

    return groups


def load_splits(db: Session, day: int, runs_g):
    run_ids = [r.id for r in runs_g]

    all_splits = (
        db.query(RunSplit)
        .filter(RunSplit.run_id.in_(run_ids))
        .order_by(RunSplit.seq)
        .all()
    )

    splits_by_run = {}
    for sp in all_splits:
        splits_by_run.setdefault(sp.run_id, []).append(sp)

    # Best per leg
    best_per_leg = {}
    for sp_list in splits_by_run.values():
        for sp in sp_list:
            if sp.leg_time is not None:
                best_per_leg.setdefault(sp.seq, set()).add(sp.leg_time)

    for seq in best_per_leg:
        best_per_leg[seq] = sorted(best_per_leg[seq])[:3]

    # Load required controls
    try:
        stage = db.query(Stage).filter_by(day=day).first()
        group_name = runs_g[0].competitor.group
        course = db.query(Course).filter_by(stage_id=stage.id, name=group_name).first()
        controls = (
            db.query(CourseControl)
            .filter(CourseControl.course_id == course.id)
            .order_by(CourseControl.seq)
            .all()
        )
        required = [c.control_code for c in controls]
    except:
        required = []

    return {
        "splits_by_run": splits_by_run,
        "best_per_leg": best_per_leg,
        "required": required,
    }


# -------------------------------------------------------
# HTML + LaTeX export
# -------------------------------------------------------

def export_results_html(db: Session, day: int, cfg, include_splits: bool):
    groups = load_day_results(db, day)
    ranking = Ranking()

    groups_data = []

    for g, runs in sorted(groups.items()):
        ranked_runs = ranking.rank(runs)
        group_info = {
            "name": g,
            "ranked": ranked_runs,
        }

        if include_splits:
            group_info["splits"] = load_splits(db, day, runs)

        groups_data.append(group_info)

    template = env.get_template("results.html.j2")
    return template.render(day=day, groups=groups_data, include_splits=include_splits, cfg=cfg)


def export_results_tex(db: Session, day: int, cfg):
    groups = load_day_results(db, day)
    ranking = Ranking()

    groups_data = []
    for g, runs in sorted(groups.items()):
        ranked_runs = ranking.rank(runs)
        groups_data.append({
            "name": g,
            "ranked": ranked_runs,
        })

    template = env.get_template("results.tex.j2")
    return template.render(day=day, groups=groups_data, cfg=cfg)


# -------------------------------------------------------
# CLI
# -------------------------------------------------------


def load_config(db):
    cfg_rows = db.query(Config).all()
    return {row.key: row.value for row in cfg_rows}


def main():
    with SessionLocal() as db:
        day = Config.get(db, Config.KEY_CURRENT_DAY)
        if day is None:
            raise RuntimeError("Config.current_day is not set")

        cfg = load_config(db)

        # HTML without splits
        html_results = export_results_html(db, day, cfg, include_splits=False)
        # HTML with splits
        html_splits = export_results_html(db, day, cfg, include_splits=True)

        # File names
        path_results = f"out/e{day}-results.html"
        path_splits  = f"out/e{day}-splits.html"

        # Write main results
        with open(path_results, "w", encoding="utf-8") as f:
            f.write(html_results)

        # Write splits
        with open(path_splits, "w", encoding="utf-8") as f:
            f.write(html_splits)

        print(f"Generated {path_results}")
        print(f"Generated {path_splits}")

        # Optional LaTeX
        tex = export_results_tex(db, day, cfg)
        path_tex = f"out/e{day}-results.tex"
        with open(path_tex, "w", encoding="utf-8") as f:
            f.write(tex)
        print(f"Generated {path_tex}")


if __name__ == "__main__":
    main()
