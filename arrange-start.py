#!/usr/bin/env python3

import json
import random
import time
from collections import defaultdict
from datetime import datetime, timedelta

from jinja2 import Environment, FileSystemLoader

from o_event.models import Run, Competitor, Course, Config, Stage
from o_event.db import SessionLocal


# ------------------------------------------------------------
# Assign start slots using course length
# ------------------------------------------------------------
def assign_start_slots(session, day, parallel_starts=1, seed=None):
    if seed is None:
        seed = int(time.time())
    random.seed(seed)
    print(f"Using seed: {seed}")

    # --- store seed in Config ---
    start_seeds_json = Config.get(session, Config.KEY_START_SEEDS, default="{}")
    try:
        start_seeds = json.loads(start_seeds_json)
    except json.JSONDecodeError:
        start_seeds = {}

    day_key = str(day)
    if day_key not in start_seeds:
        start_seeds[day_key] = []

    if not start_seeds[day_key] or start_seeds[day_key][-1] != seed:
        start_seeds[day_key].append(seed)

    Config.set(session, Config.KEY_START_SEEDS, json.dumps(start_seeds))

    runs = (
        session.query(Run)
        .filter(Run.day == day)
        .join(Competitor)
        .all()
    )

    stage = session.query(Stage).filter(Stage.day == day).first()
    courses = stage.courses
    course_len = {c.name: c.length for c in courses}

    # course_name -> first_control_code
    first_control = {}
    for c in session.query(Course).all():
        first_control[c.name] = c.controls[1].control_code if c.controls else None

    pace = {
        "Ч10": 10.0, "Ж10": 10.0,
        "Ч12": 9.0,  "Ж12": 9.0,
        "Ч14": 7.0,  "Ж14": 8.0,
        "Ч16": 7.0,  "Ж16": 7.0,
        "Ч18": 6.0,  "Ж18": 7.0,
        "Ч21E": 5.5, "Ж21E": 5.5,
    }

    expected_time = {
        g: course_len[g] * pace.get(g, 10.0)
        for g in course_len
    }

    grouped = defaultdict(list)
    for r in runs:
        grouped[r.competitor.group].append(r)

    sorted_groups = sorted(
        grouped.items(),
        key=lambda kv: (
            0 if any(r.competitor.reg == "OCO" for r in kv[1]) else 1,  # OCO first
            -expected_time.get(kv[0], 30.0)
        )
    )

    group_slots = defaultdict(set)
    slot_counts = defaultdict(int)
    last_slot = defaultdict(int)
    slot_first_controls = defaultdict(set)  # slot_index -> set of first control codes

    for group_name, lst in sorted_groups:
        random.shuffle(lst)
        for run in lst:
            course_first = first_control.get(run.competitor.group)
            slot = last_slot[group_name]
            while True:
                # check group clash, parallel limit, and first control clash
                if (group_name not in group_slots[slot] and
                    slot_counts[slot] < parallel_starts and
                   (course_first is None or course_first not in slot_first_controls[slot])):
                    break
                slot += 1

            run.start_slot = slot
            group_slots[slot].add(group_name)
            slot_counts[slot] += 1
            last_slot[group_name] = slot
            if course_first:
                slot_first_controls[slot].add(course_first)

    session.commit()


# ------------------------------------------------------------
# Convert slot index → HH:MM time
# ------------------------------------------------------------
def slot_to_time(slot0_str, slot):
    t0 = datetime.strptime(slot0_str, "%H:%M")
    return (t0 + timedelta(minutes=slot)).strftime("%H:%M")


# ------------------------------------------------------------
# Load config
# ------------------------------------------------------------
def load_config(session):
    cfg_rows = session.query(Config).all()
    return {row.key: row.value for row in cfg_rows}


# ------------------------------------------------------------
# Load protocol view-models
# ------------------------------------------------------------
def load_protocol_data(session, day):
    runs = (
        session.query(Run)
        .filter(Run.day == day)
        .join(Competitor)
        .all()
    )

    # Judge: group by slot
    by_slot = defaultdict(list)
    for r in runs:
        by_slot[r.start_slot].append(r)

    judge_list = [
        (slot, sorted(lst, key=lambda x: (x.competitor.last_name, x.competitor.first_name)))
        for slot, lst in sorted(by_slot.items())
    ]

    # Competitors: group by group
    by_group = defaultdict(list)
    for r in runs:
        by_group[r.competitor.group].append(r)

    participant_list = [
        (group, sorted(lst, key=lambda r: r.start_slot))
        for group, lst in sorted(by_group.items())
    ]

    return judge_list, participant_list


# ------------------------------------------------------------
# Render Jinja2 templates
# ------------------------------------------------------------
def render_html(day, judge_data, participant_data, cfg, slot0):
    env = Environment(loader=FileSystemLoader("templates"))

    tmpl_judge = env.get_template("start-judge.html")
    tmpl_part  = env.get_template("start.html")

    html_judge = tmpl_judge.render(
        day=day,
        slots=judge_data,
        cfg=cfg,
        slot0=slot0,
        slot_to_time=slot_to_time,
    )

    html_part = tmpl_part.render(
        day=day,
        groups=participant_data,
        cfg=cfg,
        slot0=slot0,
        slot_to_time=slot_to_time,
    )

    with open(f"e{day}-start-judge.html", "w", encoding="utf-8") as f:
        f.write(html_judge)

    with open(f"e{day}-start.html", "w", encoding="utf-8") as f:
        f.write(html_part)


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate start protocols")
    parser.add_argument("day", type=int)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--assign", action="store_true")
    parser.add_argument("--slot0", default="11:00",
                        help="Start time for slot 0, HH:MM (default 11:00)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed to reproduce arrangement")
    args = parser.parse_args()

    session = SessionLocal()

    cfg = load_config(session)

    if args.assign:
        assign_start_slots(session, args.day, args.parallel, args.seed)

    judge_data, participant_data = load_protocol_data(session, args.day)

    render_html(args.day, judge_data, participant_data, cfg, args.slot0)


if __name__ == "__main__":
    main()
