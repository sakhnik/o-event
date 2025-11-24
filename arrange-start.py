#!/usr/bin/env python3

import argparse
import random
import csv
from collections import defaultdict
from tabulate import tabulate

from o_event.models import Run, Competitor, Course  # adjust import
from o_event.db import SessionLocal


# -----------------------------
# Assign start slots using course length
# -----------------------------
def assign_start_slots_with_course(session, day, parallel_starts=1, seed=None):
    """
    Assign start slots for competitors on a given day, considering course length and pace.
    """
    if seed is not None:
        random.seed(seed)

    # Load all runs and join competitors
    runs = session.query(Run).filter(Run.day == day).join(Competitor).all()

    # Map group -> course length
    group_course_lengths = {}
    courses = session.query(Course).all()
    for course in courses:
        group_course_lengths[course.name] = course.length

    # Heuristic pace per group (minutes per km)
    pace_per_group = {
        "Ч10": 10.0, "Ж10": 10.0,
        "Ч12": 9.0, "Ж12": 9.0,
        "Ч14": 8.0, "Ж14": 8.0,
        "Ч16": 7.0, "Ж16": 7.0,
        "Ч18": 6.0, "Ж18": 7.0,
        "Ч21E": 5.5, "Ж21E": 5.5,
    }

    # Compute expected time per group
    expected_time = {}
    for group, length in group_course_lengths.items():
        pace = pace_per_group.get(group, 10.0)  # default pace if missing
        expected_time[group] = length * pace

    # Group runs by competitor group
    group_runs = defaultdict(list)
    for run in runs:
        group_runs[run.competitor.group].append(run)

    # Sort groups by expected time descending (longer courses start earlier)
    sorted_groups = sorted(group_runs.items(), key=lambda x: expected_time.get(x[0], 30), reverse=True)

    group_slots = defaultdict(set)
    slot_counts = defaultdict(int)
    last_slot_time = defaultdict(int)

    for group_name, run_list in sorted_groups:
        random.shuffle(run_list)  # randomize within group
        for run in run_list:
            slot = max(last_slot_time.get(group_name, 0), 0)
            while True:
                if group_name not in group_slots[slot] and slot_counts[slot] < parallel_starts:
                    break
                slot += 1
            run.start_slot = slot
            group_slots[slot].add(group_name)
            slot_counts[slot] += 1
            last_slot_time[group_name] = slot

    session.commit()
    print(f"Assigned start slots for {len(runs)} competitors on day {day}")


# -----------------------------
# Generic start protocol printer
# -----------------------------
def start_protocol(session, day, export_csv=None, by_group=False):
    runs = session.query(Run).filter(Run.day == day).join(Competitor).all()

    # Sort runs
    if by_group:
        runs.sort(key=lambda r: (r.competitor.group, r.start_slot))
    else:
        runs.sort(key=lambda r: r.start_slot)

    # Group runs by slot
    slots = defaultdict(list)
    for run in runs:
        slots[run.start_slot].append(run)

    # Display
    for slot in sorted(slots):
        print(f"Хвилина {slot}:")
        table = [[f"{r.competitor.last_name} {r.competitor.first_name}", r.competitor.group] for r in slots[slot]]
        print(tabulate(table, headers=["Ім’я", "Група"], tablefmt="plain"))
        print()  # blank line

    # Export CSV if requested
    if export_csv:
        with open(export_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["StartSlot", "Name", "Group"])
            for slot in sorted(slots):
                for run in slots[slot]:
                    name = f"{run.competitor.last_name} {run.competitor.first_name}"
                    writer.writerow([slot, name, run.competitor.group])
        print(f"Exported CSV to {export_csv}")


def start_protocol_participants(session, day, export_csv=None):
    """
    Print participant start protocol partitioned by groups.
    """
    runs = session.query(Run).filter(Run.day == day).join(Competitor).all()

    # Group runs by competitor group
    group_runs = defaultdict(list)
    for run in runs:
        group_runs[run.competitor.group].append(run)

    # Sort groups alphabetically (or by expected time if you prefer)
    for group_name in sorted(group_runs):
        print(f"Група {group_name}:")
        # Sort competitors within group by start_slot
        sorted_runs = sorted(group_runs[group_name], key=lambda r: r.start_slot)
        table = [[r.start_slot, f"{r.competitor.last_name} {r.competitor.first_name}"] for r in sorted_runs]
        print(tabulate(table, headers=["Хвилина", "Ім’я"], tablefmt="plain"))
        print()  # empty line between groups

    # Export CSV if requested
    if export_csv:
        with open(export_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Group", "Slot", "Name"])
            for group_name in sorted(group_runs):
                sorted_runs = sorted(group_runs[group_name], key=lambda r: r.start_slot)
                for run in sorted_runs:
                    writer.writerow([group_name, run.start_slot, f"{run.competitor.last_name} {run.competitor.first_name}"])
        print(f"Exported CSV to {export_csv}")


# -----------------------------
# CLI
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="Orienteering start slot manager")
    parser.add_argument("day", type=int, help="Day number")
    parser.add_argument("--parallel", type=int, default=1, help="Number of parallel starts per slot")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--assign", action="store_true", help="Assign start slots")
    parser.add_argument("--referees", action="store_true", help="Print start protocol by slot")
    parser.add_argument("--participants", action="store_true", help="Print start protocol by group and slot")
    parser.add_argument("--csv", type=str, default=None, help="Export protocol to CSV")

    args = parser.parse_args()

    session = SessionLocal()

    if args.assign:
        assign_start_slots_with_course(session, args.day, args.parallel, args.seed)
    if args.referees:
        start_protocol(session, args.day, export_csv=args.csv, by_group=False)
    if args.participants:
        start_protocol_participants(session, args.day, export_csv=args.csv)


if __name__ == "__main__":
    main()
