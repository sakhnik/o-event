#!/usr/bin/env python3

import argparse
from sqlalchemy.orm import Session
from html import escape
from datetime import timedelta

from o_event.models import Run, RunSplit, Competitor, Stage, Course, CourseControl, Status
from o_event.ranking import Ranking
from o_event.db import SessionLocal


# ----------------------------
#  Helpers
# ----------------------------

def fmt(t):
    """Format seconds as H:MM:SS. Return empty for None."""
    if t is None:
        return ""
    if t < 3600:
        return f'{t // 60}:{t % 60:02}'
    return str(timedelta(seconds=t))


def diff(base, t):
    """Return time difference as +M:SS."""
    if base is None or t is None:
        return ""
    d = t - base
    if d <= 0:
        return ""
    return "+" + fmt(d)


def html_header(title):
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<style>
body {{ font-family: sans-serif; max-width: 1100px; margin: auto; }}

h1, h2 {{ margin-top: 40px; }}

table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 30px;
}}

th, td {{
    border: 1px solid #ccc;
    padding: 4px 6px;
    text-align: right;
}}

th.name {{
    text-align: left;
}}

th {{
    background: #eee;
}}

td.name {{
    text-align: left;
}}

tr:nth-child(even) {{ background: #fafafa; }}

.best1 {{ background-color: #c7f7c7; font-weight: bold; }}   /* green */
.best2 {{ background-color: #fff7c7; }}                     /* yellow */
.best3 {{ background-color: #f7d0c7; }}                     /* red   */

a.group-link {{
    margin-right: 12px;
    font-weight: bold;
}}
</style>
</head>
<body>
"""


def html_footer():
    return "</body></html>"


# ----------------------------
#  Main export logic
# ----------------------------

def export_results(db: Session, day: int, include_splits: bool):
    # Load all groups for today
    q = (db.query(Run)
         .join(Run.competitor)
         .filter(Run.day == day, Run.status != Status.DNS)
         .order_by(Competitor.group, Run.result.asc().nullslast()))

    runs = q.all()

    # Group runs by competitor group
    groups = {}
    for run in runs:
        g = run.competitor.group
        groups.setdefault(g, []).append(run)

    # Prepare HTML
    html = []
    html.append(html_header(f"Results Day {day}"))

    # Top links to groups
    html.append("<h1>Results</h1>")
    for g in sorted(groups):
        html.append(f'<a class="group-link" href="#grp-{escape(g)}">{escape(g)}</a>')
    html.append("<hr>")

    # ----------------------------
    #  Per-group results
    # ----------------------------
    for g in sorted(groups):
        html.append(f'<h2 id="grp-{escape(g)}">{escape(g)}</h2>')

        html.append("<table>")
        html.append('<tr><th>Місце</th><th class="name">Ім’я</th><th>Результат</th><th>Відставання</th></tr>')

        runs_g = groups[g]
        ranked_runs = Ranking().rank(runs_g)

        for pos, behind, r in ranked_runs:
            name = escape(f"{r.competitor.last_name} {r.competitor.first_name}")
            res = fmt(r.result)
            behind_s = f'+{fmt(behind)}' if behind is not None else ''

            html.append(
                f"<tr>"
                f"<td>{pos if pos is not None else ''}</td>"
                f"<td class='name'>{name}</td>"
                f"<td>{res}</td>"
                f"<td>{behind_s if behind is not None else r.status.value}</td>"
                f"</tr>"
            )

        html.append("</table>")

        # ----------------------------
        # Splits (optional)
        # ----------------------------
        if include_splits:
            # Collect splits per-leg for top3 highlighting
            # leg_index -> list of (run_id, leg_time)
            all_splits = (
                db.query(RunSplit)
                .filter(RunSplit.run_id.in_([r.id for r in runs_g]))
                .order_by(RunSplit.seq)
                .all()
            )

            # Organize by run
            splits_by_run = {}
            for sp in all_splits:
                splits_by_run.setdefault(sp.run_id, []).append(sp)

            # Determine best 3 per leg
            best_per_leg = {}
            for run_id, spl_list in splits_by_run.items():
                for sp in spl_list:
                    if sp.leg_time is None:
                        continue
                    best_per_leg.setdefault(sp.seq, set()).add(sp.leg_time)

            for seq in best_per_leg:
                best_per_leg[seq] = sorted(best_per_leg[seq])[:3]  # keep top3

            # First gather max seq count
            max_seq = max((len(splits_by_run.get(r.id, [])) for r in runs_g), default=0)

            try:
                # fetch required controls
                stage = db.query(Stage).filter_by(day=day).first()
                course = db.query(Course).filter_by(stage_id=stage.id, name=g).first()
                controls = (
                    db.query(CourseControl)
                    .filter(CourseControl.course_id == course.id)
                    .order_by(CourseControl.seq)
                    .all()
                )
                required_codes = [int(c.control_code) for c in controls if c.control_code.isdigit()]
            except Exception:
                print('No course information for', g)
                required_codes = ['-'] * max_seq

            # Render table
            html.append(f"<h3>Проміжки – {escape(g)}</h3>")
            # header row with control codes

            # header
            html.append("<table>")
            html.append("<tr><th>Ім’я</th>")
            for seq in range(1, max_seq):
                html.append(f"<th>{seq}<br/>{required_codes[seq - 1]}</th>")
            html.append(f"<th>{max_seq}<br/>F</th>")
            html.append("</tr>")

            for pos, behind, r in ranked_runs:
                name = escape(f"{r.competitor.last_name} {r.competitor.first_name}")
                html.append(f"<tr><td class='name'>{name}</td>")

                sp_dict = {sp.seq: sp for sp in splits_by_run.get(r.id, [])}

                for seq in range(1, max_seq + 1):
                    sp = sp_dict.get(seq - 1)
                    if not sp or sp.leg_time is None:
                        html.append("<td></td>")
                        continue

                    lt = sp.leg_time
                    classes = ""

                    best3 = best_per_leg.get(seq - 1, [])
                    if lt in best3:
                        idx = best3.index(lt)
                        if idx == 0:
                            classes = "best1"
                        elif idx == 1:
                            classes = "best2"
                        elif idx == 2:
                            classes = "best3"

                    html.append(f"<td class='{classes}'>{fmt(lt)}</td>")

                html.append("</tr>")

            html.append("</table>")

    html.append(html_footer())
    return "".join(html)


# ----------------------------
#  CLI
# ----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--splits", action="store_true",
                    help="Include detailed split tables")
    args = ap.parse_args()

    with SessionLocal() as db:
        html = export_results(db, args.day, args.splits)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Exported to {args.out}")


if __name__ == "__main__":
    main()
