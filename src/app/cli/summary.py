from o_event.models import Config, Competitor
from o_event.ranking import Ranking
from o_event.printer import Printer
from app.cli.time_utils import TimeUtils

from tabulate import tabulate


class Summary:
    def __init__(self, db):
        self.db = db

    def summary(self, max_place):
        day = Config.get_current_day(self.db)

        groups = (
            self.db.query(Competitor.group)
            .distinct()
            .order_by(Competitor.group)
            .all()
        )
        groups = [g[0] for g in groups]

        # List of tuples: (group_name, rows)
        report_groups = []

        for group in groups:
            competitors = (
                self.db.query(Competitor)
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
