#!/usr/bin/env python3

from dataclasses import dataclass
from typing import Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from tabulate import tabulate

from o_event.db import SessionLocal
from o_event.models import Config

from app.cli.card_utils import CardUtils
from app.cli.competitor_utils import CompetitorUtils
from app.cli.registration import Registration
from app.cli.summary import Summary


@dataclass(frozen=True)
class Command:
    command: str
    synopsis: str
    description: str
    handler: Callable[[list[str]], None]


class Cli:
    def __init__(self):
        self.db = SessionLocal()

        self.session = PromptSession()
        self.running = True

        self.competitors = CompetitorUtils(self.db)
        self.cards = CardUtils(self.db)
        self.registration = Registration(self.db)
        self.summary_util = Summary(self.db)

        self.commands = [
            Command("help", "help", "List commands", self.help),
            Command("day", "day <day>", "Set current stage day", self.day),
            Command("ls", "ls <query>", "List competitors matching query", self.ls),
            Command("edit", "edit <competitor_id|query>", "Edit competitor", self.edit),
            Command("add", "add", "Add new competitor", self.add),
            Command("assign", "assign", "Assign a card for the run", self.assign),
            Command("modify", "modify", "Modify a card", self.modify),
            Command("register", "register <query>", "Register competitors for start", self.register),
            Command("summary", "summary <max place>", "Print summary result", self.summary),
            Command("quit", "quit", "Quit the CLI", self.quit),
        ]

        self.handlers = {
            command.command: command.handler
            for command in self.commands
        }

        self.completer = WordCompleter(
            self.handlers.keys(),
            ignore_case=True,
        )

    def resolve_command(self, prefix: str) -> str | None:
        matches = [name for name in self.handlers if name.startswith(prefix)]

        if len(matches) == 1:
            return matches[0]

        if prefix in self.handlers:
            return prefix

        return None

    def current_day(self):
        return Config.get_current_day(self.db)

    def set_current_day(self, day: str):
        try:
            Config.set(self.db, Config.KEY_CURRENT_DAY, int(day))
        except (TypeError, ValueError):
            pass

    def run(self):
        print("Orienteering CLI (type 'help' for commands)")

        while self.running:
            try:
                self.prompt_once()
            except KeyboardInterrupt:
                print("Use 'quit' to exit")
            except EOFError:
                break

        self.db.close()

    def prompt_once(self):
        text = self.session.prompt(
            HTML(f"<ansiblue>E{self.current_day()}> </ansiblue>"),
            completer=self.completer,
        )

        if not text.strip():
            return

        parts = text.split()
        command = self.resolve_command(parts[0].lower())
        args = parts[1:]

        if command is None:
            print("Unknown command, type 'help'")
            return

        self.handlers[command](args)

    #
    # Commands
    #

    def help(self, args: list[str]):
        print("Commands:")
        print(tabulate([[c.synopsis, c.description] for c in self.commands]))

    def quit(self, args: list[str]):
        self.running = False

    def day(self, args: list[str]):
        if not args:
            print(f"Current day: {self.current_day()}")
            return

        self.set_current_day(args[0])

    def ls(self, args: list[str]):
        self.competitors.ls_competitors(" ".join(args) or None)

    def add(self, args: list[str]):
        self.competitors.add_competitor()

    def edit(self, args: list[str]):
        if args and args[0].isdigit():
            competitor_id = int(args[0])
        else:
            competitor_id = self.competitors.pick_competitor(" ".join(args))

        if competitor_id is not None:
            self.competitors.edit_competitor(competitor_id)

    def assign(self, args: list[str]):
        self.cards.assign_card()

    def modify(self, args: list[str]):
        self.cards.modify_card()

    def register(self, args: list[str]):
        self.registration.register(" ".join(args) or None)

    def summary(self, args: list[str]):
        try:
            max_place = int(args[0])
        except (IndexError, ValueError):
            max_place = 99

        self.summary_util.summary(max_place)


if __name__ == "__main__":
    Cli().run()
