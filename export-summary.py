#!/usr/bin/env python3

from sqlalchemy.orm import Session
from jinja2 import Template
from datetime import timedelta

from o_event.models import Competitor
from o_event.ranking import Ranking
from o_event.db import SessionLocal


# Format seconds → "h:mm:ss"
def format_time(seconds: int | None) -> str:
    if seconds is None:
        return ""
    td = timedelta(seconds=int(seconds))
    # drop days
    h, remainder = divmod(td.seconds, 3600)
    m, s = divmod(remainder, 60)
    return f"{h}:{m:02d}:{s:02d}"


# -------------------------------
# HTML TEMPLATE
# -------------------------------
HTML_TEMPLATE = Template("""
<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<title>Багатоденні результати</title>
<style>
body {
    font-family: sans-serif;
    margin: 20px;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 40px;
}
th, td {
    border: 1px solid #aaa;
    padding: 6px 10px;
    text-align: left;
}
th {
    background: #eee;
}
h1 {
    margin-bottom: 10px;
}
h2 {
    margin-top: 40px;
    margin-bottom: 10px;
    border-bottom: 2px solid #333;
    padding-bottom: 5px;
}
</style>
</head>
<body>

<h1>Багатоденні результати</h1>

{% for group_name, rows in groups %}
<h2>Група {{ group_name }}</h2>

<table>
<thead>
    <tr>
        {% for h in headers %}
        <th>{{ h }}</th>
        {% endfor %}
    </tr>
</thead>
<tbody>
{% for row in rows %}
    <tr>
        {% for col in row %}
        <td>{{ col }}</td>
        {% endfor %}
    </tr>
{% endfor %}
</tbody>
</table>
{% endfor %}

</body>
</html>
""")


# --------------------------------------------
# MAIN GENERATOR
# --------------------------------------------
def generate_reports(session: Session, days_to_calculate: int):
    headers = ["Місце", "Ім’я", "Клуб", "К-ть Е", "Час всього", "Бали"]

    # 1. Fetch all groups
    groups = (
        session.query(Competitor.group)
        .distinct()
        .order_by(Competitor.group)
        .all()
    )
    groups = [g[0] for g in groups]

    # List of tuples: (group_name, rows)
    report_groups = []

    for group in groups:
        competitors = (
            session.query(Competitor)
            .filter(Competitor.group == group)
            .all()
        )
        if not competitors:
            continue

        ranked = Ranking().rank_multiday(days_to_calculate, competitors)

        rows = []
        for place, result in ranked:
            c = result.competitor
            rows.append([
                place or "",
                f"{c.last_name} {c.first_name}",
                c.club_name or "",
                result.best_count,
                format_time(result.total_time),
                result.total_score
            ])

        report_groups.append((group, rows))

    # Render the whole page
    html = HTML_TEMPLATE.render(
        headers=headers,
        groups=report_groups
    )

    # Output
    fname = "report_all.html"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✔ Created {fname}")


with SessionLocal() as db:
    generate_reports(db, days_to_calculate=2)
