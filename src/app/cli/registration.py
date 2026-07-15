from tabulate import tabulate

from app.cli.competitor_utils import CompetitorUtils
from app.cli.editor import Editor
from o_event.models import Competitor
from o_event.printer import Printer


class Registration:
    def __init__(self, db):
        self.db = db

    def register(self, query: str = None):
        subset = CompetitorUtils(self.db).filter_competitors(query)
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
                comp = self.db.get(Competitor, id_)
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
                self.db.commit()
                break
