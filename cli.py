#!/usr/bin/env python3

from dataclasses import dataclass
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from rapidfuzz import fuzz
from sqlalchemy import asc, or_
from sqlalchemy.inspection import inspect
from tabulate import tabulate
from typing import List, Tuple
import os
import subprocess
import tempfile
import yaml
import requests

from o_event.db import SessionLocal
from o_event.models import Competitor, Run, Status, Config, Card
from o_event.printer import Printer, PrinterMux
from o_event.ranking import Ranking
from o_event.card_processor import CardProcessor


@dataclass
class Command:
    command: str
    synopsis: str
    description: str


commands_def: List[Command] = [
    Command('help', 'help', 'List commands'),
    Command('day', 'day <day>', 'Set current stage day'),
    Command('ls', 'ls <query>', 'List competitors matching query'),
    Command('edit', 'edit <competitor_id|query>', 'Edit competitor with ID <competitor_id>'),
    Command('add', 'add', 'Add new competitor'),
    Command('assign', 'assign', 'Assign a card for the run'),
    Command('modify', 'modify', 'Modify a card'),
    Command('register', 'register <query>', 'Register competitors for start'),
    Command('summary', 'summary <max place>', 'Print summary result'),
    Command('quit', 'quit', 'Quit the CLI')
]
commands = [c.command for c in commands_def]
cmd_completer = WordCompleter(commands, ignore_case=True)

db = SessionLocal()


def resolve_command(cmd):
    """
    Resolve a possibly abbreviated command to full command.
    If multiple matches exist, return None (ambiguous).
    """
    matches = [c for c in commands if c.startswith(cmd)]
    if len(matches) == 1:
        return matches[0]
    elif cmd in commands:
        return cmd  # exact match
    else:
        return None  # ambiguous or unknown


def get_columns(model):
    return [c.key for c in inspect(model).mapper.column_attrs]


# ---------- Utilities ----------
def competitor_to_dict(c: Competitor):
    comp_dict = {col: getattr(c, col) for col in get_columns(Competitor)}
    comp_dict["runs"] = [
        {col: getattr(r, col) if col != "status" else (r.status.value if r.status else None)
         for col in get_columns(Run)}
        for r in c.runs
    ]
    return comp_dict


def update_competitor_from_dict(d: dict):
    comp_columns = get_columns(Competitor)
    run_columns = get_columns(Run)

    # Create or fetch competitor
    if "id" not in d or d["id"] is None:
        comp = Competitor()
        db.add(comp)
        db.flush()
    else:
        comp = db.get(Competitor, d["id"])
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
            db.add(r)

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
            db.delete(r)

    db.flush()
    return comp


def edit_yaml_in_editor(comp_dict: dict) -> Tuple[dict, bool]:
    editor = os.environ.get("EDITOR", "vi")
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".yaml", delete=False) as tf:
        path = tf.name
        yaml.safe_dump(comp_dict, tf, sort_keys=False, allow_unicode=True, width=float('inf'))
        tf.flush()
    try:
        # Save original text
        original_text = yaml.safe_dump(comp_dict, sort_keys=False, allow_unicode=True, width=float('inf'))

        # Launch editor
        subprocess.call([editor, path])

        # Read edited text
        with open(path, "r", encoding="utf-8") as f:
            edited_text = f.read()

        if edited_text.strip() == original_text.strip():
            return comp_dict, False

        # Otherwise parse YAML and return
        edited = yaml.safe_load(edited_text)
        return edited, True

    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def get_competitors(query: str = None) -> List[Tuple[int, Competitor]]:
    comps = db.query(Competitor).all()
    results = []

    for c in comps:
        name = f"{c.last_name or ''} {c.first_name or ''}"
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


def pick_competitor(query: str = None) -> Competitor | None:
    """
    Show competitors in fzf and return the chosen Competitor.
    """
    items = get_competitors(query)

    # Prepare the input for fzf
    lines = []
    for score, c in reversed(items):
        name = f"{c.last_name or ''} {c.first_name or ''}"
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


# ---------- Commands ----------
def ls_competitors(query: str = None):
    for score, c in get_competitors(query):
        name = f"{c.last_name or ''} {c.first_name or ''}"
        group = c.group or ""
        declared = c.declared_days or []
        notes = c.notes or ''
        print(f"{c.sid:3} | {c.reg or '':6} | {name:20} | {group:6} | {declared} | {notes}")


def add_competitor():
    skeleton = {
        "id": None,
        "reg": "",
        "group": "",
        "sid": None,
        "first_name": "",
        "last_name": "",
        "notes": "",
        "money": None,
        "declared_days": [],
        "runs": [],
    }
    edited, changed = edit_yaml_in_editor(skeleton)
    if changed:
        update_competitor_from_dict(edited)
        db.commit()
        print("Added new competitor.")
    else:
        print("No changes made. Aborted.")


def edit_competitor(cid: int):
    comp = db.get(Competitor, cid)
    if not comp:
        print(f"No competitor with ID {cid}")
        return
    comp_dict = competitor_to_dict(comp)
    edited, changed = edit_yaml_in_editor(comp_dict)
    if changed:
        update_competitor_from_dict(edited)
        db.commit()
        print(f"Competitor {cid} updated.")
    else:
        print("No changes made. Aborted.")


def get_current_day():
    return Config.get(db, Config.KEY_CURRENT_DAY)


def set_current_day(arg):
    try:
        Config.set(db, Config.KEY_CURRENT_DAY, int(arg))
    except Exception:
        ...


def register(query: str = None):
    subset = get_competitors(query)
    updated_money = {}
    while True:
        selection = []
        for _, c in subset:
            name = f"{c.last_name or ''} {c.first_name or ''}"
            group = c.group or ""
            declared = c.declared_days or []
            notes = c.notes or ''
            money = updated_money.get(c.id, c.money)
            info = f"{c.id:3} | {money:5} | {c.reg or '':6} | {c.sid:3} | {name:20} | {group:6} | {declared} | {notes}"
            selection.append(info)
        edited, changed = edit_yaml_in_editor(selection)
        subset = []
        for s in edited:
            parts = [p.strip() for p in s.split("|")]
            id_ = int(parts[0])
            comp = db.get(Competitor, id_)
            if comp is None:
                raise ValueError(f"Competitor id {id_} not found")
            if comp.money_paid is not None:
                print(f'{comp.sid} {comp.group} {comp.last_name} {comp.first_name} вже заплатив {comp.money_paid}!')
            money = int(parts[1])
            updated_money[id_] = money
            subset.append((money, comp))
        report = [[comp.sid, comp.group, f'{comp.last_name} {comp.first_name}', money] for money, comp in subset]
        print(tabulate(report))
        total = sum(money for money, _ in subset)
        print(f"Всього: {total}")
        ans = input('Прийняти [Y/n/q]? ').strip().lower()
        if ans in ('q', 'quit'):
            break
        if ans in ('', 'y', 'yes', 'т', 'так'):
            try:
                with Printer() as p:
                    for money, comp in subset:
                        p.bold_on()
                        p.text(f'{comp.sid:>3}')
                        p.bold_off()
                        p.text(f' {comp.group:<8}')
                        name = f'{comp.last_name} {comp.first_name}'
                        p.text(f' {name:<21}')
                        p.text(f' {money:>5}')
                        p.text('\n')
                    p.text('\n')
                    summary = f"Всього: {total}"
                    p.bold_on()
                    p.text(f"{summary:>40}")
                    p.bold_off()
                    p.feed(3)
                    p.cut()
            except Exception as ex:
                print(ex)
            for money, comp in subset:
                comp.money_paid = money
            db.commit()
            break


# Format seconds → "h:mm:ss"
def format_time(seconds: int | None) -> str:
    if seconds is None:
        return ""
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if not h:
        return f"{m}:{s:02d}"
    return f"{h}:{m:02d}:{s:02d}"


def summary(max_place):
    day = Config.get(db, Config.KEY_CURRENT_DAY)

    groups = (
        db.query(Competitor.group)
        .distinct()
        .order_by(Competitor.group)
        .all()
    )
    groups = [g[0] for g in groups]

    # List of tuples: (group_name, rows)
    report_groups = []

    for group in groups:
        competitors = (
            db.query(Competitor)
            .filter(Competitor.group == group)
            .all()
        )
        if not competitors:
            continue

        ranked = Ranking().rank_multiday(day, competitors)

        rows = []
        for place, result in ranked:
            c = result.competitor
            if place is None or place > max_place:
                break
            rows.append([
                place or "",
                f"{c.last_name} {c.first_name}",
                c.reg or "",
                result.best_count,
                format_time(result.total_time),
                result.total_score
            ])

        report_groups.append((group, rows))

        print(group)
        print(tabulate(rows))

    ans = input('Друкувати [Y/n]? ').strip().lower()
    if ans in ('', 'y', 'yes'):
        try:
            with Printer() as p:
                for group, result in report_groups:
                    p.bold_on()
                    p.underline2_on()
                    p.text(f'{group}\n')
                    p.bold_off()
                    p.underline_off()
                    for r in result:
                        p.text(f'{r[0]:>2}')
                        p.text(f' {r[1]:<23}')
                        p.text(f' {r[2]:>5}')
                        p.text(f' {r[3]:>2}')
                        p.text(f' {r[4]:>7}')
                        p.text(f' {r[5]:>4}')
                        p.text('\n')
                    p.text('\n')
                p.feed(3)
                p.cut()
        except Exception as ex:
            print(ex)


# Format seconds → "h:mm:ss"
def format_time(seconds: int | None) -> str:
    if seconds is None:
        return ""
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if not h:
        return f"{m}:{s:02d}"
    return f"{h}:{m:02d}:{s:02d}"


def pick_card():
    cards = (
        db.query(Card)
        .order_by(Card.readout_datetime.asc())
        .all()
    )

    # Prepare the input for fzf
    lines = []
    for c in reversed(cards):
        readout_time = c.readout_datetime.strftime('%H:%M:%S')
        start = format_time(c.start_time)
        finish = format_time(c.finish_time)
        line = f"{c.id:3} | card={c.card_number:<4} | readout={readout_time:7} | start={start:6} | finish={finish:6}"
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


def pick_run():
    current_day = Config.get(db, Config.KEY_CURRENT_DAY)

    runs = (
        db.query(Run)
        .filter(Run.day == current_day)
        .order_by(asc(or_(Run.result == None, Run.status != Status.OK)))    # noqa: E711
        .all()
    )

    # Prepare the input for fzf
    lines = []
    for r in reversed(runs):
        name = f'{r.competitor.last_name} {r.competitor.first_name}'
        start_slot = r.start_slot or ''
        line = f"{r.id:3} | start={start_slot:5} | {r.competitor.group:4} | {r.competitor.sid:4} | {name:20} | {r.status:3} | {format_time(r.result):5}"
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


def assign_card():
    card_id = pick_card()
    if card_id is None:
        return
    run_id = pick_run()
    if run_id is None:
        return

    card = db.get(Card, card_id)
    run = db.get(Run, run_id)
    with PrinterMux() as p:
        status = CardProcessor().handle_card(db, card, run, p)
        print('\n'.join(p.get_output()))
        print(status)


def modify_card():
    card_id = pick_card()
    if card_id is None:
        return
    card = db.get(Card, card_id)
    if card is None:
        print("No such card")
        return

    edited, changed = edit_yaml_in_editor(card.raw_json)
    if changed:
        url = "https://localhost:12345/card"
        response = requests.post(url, json=edited)
        if response.ok:
            print(response.json())
        else:
            print("Error:", response.status_code, response.text)
    else:
        print("No changes made. Aborted.")


def main():
    print("Orienteering CLI (type 'help' for commands)")
    session = PromptSession()
    while True:
        try:
            current_day = get_current_day()
            text = session.prompt(HTML(f'<ansiblue>E{current_day}> </ansiblue>'), completer=cmd_completer)
            if not text.strip():
                continue
            parts = text.strip().split()
            cmd_input = parts[0].lower()
            cmd = resolve_command(cmd_input)
            args = parts[1:]

            if cmd == 'quit':
                break
            elif cmd == 'day':
                set_current_day(parts[1])
            elif cmd == 'ls':
                query = " ".join(args) if args else None
                ls_competitors(query)
            elif cmd == 'add':
                add_competitor()
            elif cmd == 'edit':
                if args and len(args) > 0 and args[0].isdigit():
                    cid = int(args[0])
                else:
                    cid = pick_competitor(' '.join(args))
                if cid is not None:
                    edit_competitor(cid)
            elif cmd == 'register':
                query = ' '.join(args) if args else None
                register(query)
            elif cmd == 'summary':
                max_place = 99
                try:
                    max_place = int(args[0])
                except (ValueError, IndexError):
                    ...
                summary(max_place)
            elif cmd == 'assign':
                assign_card()
            elif cmd == 'modify':
                modify_card()
            elif cmd == 'help':
                print("Commands:")
                print(tabulate([[c.synopsis, c.description] for c in commands_def]))
            else:
                print("Unknown command, type 'help'")
        except KeyboardInterrupt:
            print("Use 'quit' to exit")
        except EOFError:
            break

    db.close()


if __name__ == "__main__":
    main()
