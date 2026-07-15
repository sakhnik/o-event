#!/usr/bin/env python3

from dataclasses import dataclass
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from tabulate import tabulate
from typing import List

from o_event.db import SessionLocal
from o_event.models import Config
from app.cli.card_utils import CardUtils
from app.cli.competitor_utils import CompetitorUtils
from app.cli.registration import Registration
from app.cli.summary import Summary


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


def get_current_day():
    return Config.get(db, Config.KEY_CURRENT_DAY)


def set_current_day(arg):
    try:
        Config.set(db, Config.KEY_CURRENT_DAY, int(arg))
    except Exception:
        ...


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
                CompetitorUtils(db).ls_competitors(query)
            elif cmd == 'add':
                CompetitorUtils(db).add_competitor()
            elif cmd == 'edit':
                if args and len(args) > 0 and args[0].isdigit():
                    cid = int(args[0])
                else:
                    cid = CompetitorUtils(db).pick_competitor(' '.join(args))
                if cid is not None:
                    CompetitorUtils(db).edit_competitor(cid)
            elif cmd == 'register':
                query = ' '.join(args) if args else None
                Registration(db).register(query)
            elif cmd == 'summary':
                max_place = 99
                try:
                    max_place = int(args[0])
                except (ValueError, IndexError):
                    ...
                Summary(db).summary(max_place)
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
