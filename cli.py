#!/usr/bin/env python3

from dataclasses import dataclass
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from sqlalchemy import asc, or_
from tabulate import tabulate
from typing import List
import subprocess
import requests

from o_event.db import SessionLocal
from o_event.models import Competitor, Run, Status, Config, Card
from o_event.printer import Printer, PrinterMux
from o_event.ranking import Ranking
from o_event.card_processor import CardProcessor
from app.cli.editor import Editor
from app.cli.competitor_utils import CompetitorUtils


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


def pick_competitor(query: str = None) -> Competitor | None:
    """
    Show competitors in fzf and return the chosen Competitor.
    """
    items = CompetitorUtils(db).filter_competitors(query)

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


# ---------- Commands ----------
def ls_competitors(query: str = None):
    for score, c in CompetitorUtils(db).filter_competitors(query):
        name = c.name or ""
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
        "name": "",
        "representative": "",
        "notes": "",
        "money": None,
        "declared_days": [],
        "runs": [],
    }
    edited, changed = Editor().edit_yaml(skeleton)
    if changed:
        CompetitorUtils(db).update_competitor_from_dict(edited)
        db.commit()
        print("Added new competitor.")
    else:
        print("No changes made. Aborted.")


def edit_competitor(cid: int):
    comp = db.get(Competitor, cid)
    if not comp:
        print(f"No competitor with ID {cid}")
        return
    comp_dict = CompetitorUtils(db).competitor_to_dict(comp)
    edited, changed = Editor().edit_yaml(comp_dict)
    if changed:
        CompetitorUtils(db).update_competitor_from_dict(edited)
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
    subset = CompetitorUtils(db).filter_competitors(query)
    updated_money = {}
    while True:
        selection = []
        for _, c in subset:
            name = c.name or ""
            group = c.group or ""
            declared = c.declared_days or []
            notes = c.notes or ''
            representative = c.representative or ''
            money = updated_money.get(c.id, c.money)
            info = f"{c.id:3} | {money:5} | {c.reg or '':6} | {c.sid:3} | {name:20} | {group:6} | {declared} | r={representative} | {notes}"
            selection.append(info)
        edited, changed = Editor().edit_yaml(selection)
        subset = []
        for s in edited:
            parts = [p.strip() for p in s.split("|")]
            id_ = int(parts[0])
            comp = db.get(Competitor, id_)
            if comp is None:
                raise ValueError(f"Competitor id {id_} not found")
            if comp.money_paid is not None:
                print(f'{comp.sid} {comp.group} {comp.name} вже заплатив {comp.money_paid}!')
            money = int(parts[1])
            updated_money[id_] = money
            subset.append((money, comp))
        report = [[comp.sid, comp.group, comp.name, money] for money, comp in subset]
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
                        name = comp.name
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
                c.name or "",
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
        name = r.competitor.name
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

    edited, changed = Editor().edit_yaml(card.raw_json)
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
