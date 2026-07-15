#!/usr/bin/env python3

from dataclasses import dataclass
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from tabulate import tabulate
from typing import List
import subprocess

from o_event.db import SessionLocal
from o_event.models import Competitor, Config
from o_event.printer import Printer
from o_event.ranking import Ranking
from app.cli.editor import Editor
from app.cli.competitor_utils import CompetitorUtils
from app.cli.registration import Registration
from app.cli.time_utils import TimeUtils
from app.cli.card_utils import CardUtils


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
                TimeUtils().format_time(result.total_time),
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
                Registration(db).register(query)
            elif cmd == 'summary':
                max_place = 99
                try:
                    max_place = int(args[0])
                except (ValueError, IndexError):
                    ...
                summary(max_place)
            elif cmd == 'assign':
                CardUtils(db).assign_card()
            elif cmd == 'modify':
                CardUtils(db).modify_card()
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
