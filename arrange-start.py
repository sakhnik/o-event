#!/usr/bin/env python3

import json
import random
import time
import math
from collections import defaultdict
from datetime import datetime, timedelta

from jinja2 import Environment, FileSystemLoader

from o_event.models import Run, Competitor, Course, Config, Stage
from o_event.db import SessionLocal


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
        "Ч10": 15.0, "Ж10": 15.0,
        "Ч12": 10.0,  "Ж12": 10.0,
        "Ч14": 8.0,   "Ж14": 8.0,
        "Ч16": 7.0,   "Ж16": 7.0,
        "Ч18": 6.0,   "Ж18": 7.0,
        "Ч21E": 5.5,  "Ж21E": 5.5,
    }

    expected_time = {
        g: course_len[g] * pace.get(g, 20.0)
        for g in course_len
    }

    # --- collect all runs into a single list and assign priority ---
    def priority(r):
        etime = expected_time.get(r.competitor.group, 30.0)
        return (0 if r.competitor.reg == "OCO" else 1, -etime)

    runs.sort(key=priority)

    # --- prepare slots ---
    num_slots = math.ceil(len(runs) / parallel_starts)
    slot_counts = defaultdict(int)          # slot_index -> number of competitors
    group_slots = defaultdict(set)          # slot_index -> groups in slot
    slot_first_controls = defaultdict(set)  # slot_index -> first controls

    slot_index = 0

    # NEW: track last reg assigned for each group (to avoid same-reg adjacency)
    last_reg_by_group = defaultdict(lambda: None)

    # We'll work with runs as a mutable list of remaining candidates
    remaining = list(runs)

    while remaining:
        picked_index = None
        # 1) first pass: try to find candidate that doesn't repeat reg for its group AND can be placed
        for i, run in enumerate(remaining):
            group_name = run.competitor.group
            reg = run.competitor.reg
            course_first = first_control.get(run.competitor.group)

            # skip if reg equals last reg for this group
            if last_reg_by_group[group_name] == reg:
                continue

            # check if there exists a valid slot for this run (searching from current slot_index)
            ok = False
            si = slot_index
            for _ in range(num_slots):
                if (group_name not in group_slots[si] and
                    (course_first is None or course_first not in slot_first_controls[si])):
                    ok = True
                    break
                si = (si + 1) % num_slots

            if ok:
                picked_index = i
                break

        # 2) fallback pass: if no candidate found, allow same-reg (to avoid deadlock)
        if picked_index is None:
            for i, run in enumerate(remaining):
                group_name = run.competitor.group
                course_first = first_control.get(run.competitor.group)

                si = slot_index
                ok = False
                for _ in range(num_slots):
                    if (group_name not in group_slots[si] and
                        (course_first is None or course_first not in slot_first_controls[si])):
                        ok = True
                        break
                    si = (si + 1) % num_slots

                if ok:
                    picked_index = i
                    break

        # If still none found (very unlikely), expand search by ignoring first_control constraint
        if picked_index is None:
            for i, run in enumerate(remaining):
                group_name = run.competitor.group
                si = slot_index
                ok = False
                for _ in range(num_slots):
                    if group_name not in group_slots[si]:
                        ok = True
                        break
                    si = (si + 1) % num_slots
                if ok:
                    picked_index = i
                    break

        # If still none (really pathological), take first
        if picked_index is None:
            run = remaining.pop(0)
        else:
            run = remaining.pop(picked_index)

        # Now find slot for this run (starting from current slot_index)
        group_name = run.competitor.group
        reg = run.competitor.reg
        course_first = first_control.get(run.competitor.group)

        for _ in range(num_slots):
            if (group_name not in group_slots[slot_index] and
                (course_first is None or course_first not in slot_first_controls[slot_index])):
                break
            slot_index = (slot_index + 1) % num_slots

        # assign
        run.start_slot = slot_index
        group_slots[slot_index].add(group_name)
        slot_counts[slot_index] += 1
        if course_first:
            slot_first_controls[slot_index].add(course_first)

        # record last reg for this group
        last_reg_by_group[group_name] = reg

        # advance slot for round-robin
        slot_index = (slot_index + 1) % num_slots

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

    for suffix in 'html', 'tex':
        tmpl = env.get_template(f"start-judge.{suffix}")
        out = tmpl.render(
            day=day,
            slots=judge_data,
            cfg=cfg,
            slot0=slot0,
            slot_to_time=slot_to_time,
        )
        with open(f"out/e{day}-start-judge.{suffix}", "w", encoding="utf-8") as f:
            f.write(out)

    for suffix in 'html', 'tex':
        tmpl = env.get_template(f"start.{suffix}")
        out = tmpl.render(
            day=day,
            groups=participant_data,
            cfg=cfg,
            slot0=slot0,
            slot_to_time=slot_to_time,
        )
        with open(f"out/e{day}-start.{suffix}", "w", encoding="utf-8") as f:
            f.write(out)


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
