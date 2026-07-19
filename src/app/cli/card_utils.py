from sqlalchemy import asc, or_
import requests
import subprocess

from o_event.card_processor import CardProcessor
from o_event.models import Run, Status, Config, Card
from o_event.printer import PrinterMux
from app.cli.time_utils import TimeUtils
from app.cli.editor import Editor


class CardUtils:
    def __init__(self, db):
        self.db = db

    def pick_card(self):
        cards = (
            self.db.query(Card)
            .order_by(Card.readout_datetime.asc())
            .all()
        )

        time_utils = TimeUtils()

        # Prepare the input for fzf
        lines = []
        for c in reversed(cards):
            readout_time = c.readout_datetime.strftime('%H:%M:%S')
            start = time_utils.format_time(c.start_time)
            finish = time_utils.format_time(c.finish_time)
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

    def pick_run(self):
        current_day = Config.get_current_day(self.db)

        runs = (
            self.db.query(Run)
            .filter(Run.day == current_day)
            .order_by(asc(or_(Run.result == None, Run.status != Status.OK)))    # noqa: E711
            .all()
        )

        time_utils = TimeUtils()

        # Prepare the input for fzf
        lines = []
        for r in reversed(runs):
            name = r.competitor.name
            start_slot = r.start_slot or ''
            line = f"{r.id:3} | start={start_slot:5} | {r.competitor.group:4} | {r.competitor.sid:4} | {name:20} | {r.status:3} | {time_utils.format_time(r.result):5}"
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

    def assign_card(self):
        card_id = self.pick_card()
        if card_id is None:
            return
        run_id = self.pick_run()
        if run_id is None:
            return

        card = self.db.get(Card, card_id)
        run = self.db.get(Run, run_id)
        with PrinterMux() as p:
            status = CardProcessor().handle_card(self.db, card, run, p)
            print('\n'.join(p.get_output()))
            print(status)

    def modify_card(self):
        card_id = self.pick_card()
        if card_id is None:
            return
        card = self.db.get(Card, card_id)
        if card is None:
            print("No such card")
            return

        # TODO: a better way when the card service isn't running?
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
