from o_event.analysis import Analysis
from o_event.printer import Printer
from o_event.models import Card, Competitor, Config, Course, CourseControl, Run, RunSplit
from datetime import date
from typing import List
from sqlalchemy import func


class Receipt:
    WIDTH = 48

    def __init__(self, db, result: Analysis.Result, card: Card, course: Course, controls: List[CourseControl]):
        self.db = db
        self.result = result
        self.card = card
        self.course = course
        self.controls = controls

        self._load_all()

    # ------------------------------------------------------------
    # Load everything from DB
    # ------------------------------------------------------------
    def _load_all(self):
        card = self.card

        competitor = (
            self.db.query(Competitor)
            .filter_by(sid=card.card_number)
            .first()
        )
        if not competitor:
            raise ValueError("No competitor with this SID")

        self.competitor = competitor
        self.name = f"{competitor.last_name} {competitor.first_name}"
        self.club = competitor.group
        self.category = competitor.group

        day = card.raw_json.get("day") or Config.get(self.db, Config.KEY_CURRENT_DAY)
        if not day:
            raise ValueError("Day not provided in card or config")

        self.day = day

        self.race_name = Config.get(self.db, Config.KEY_NAME, "")
        self.place = Config.get(self.db, Config.KEY_PLACE, "")
        self.race_date = Config.get(self.db, Config.KEY_DATE, date.today())

        self._compute_times()

    # ------------------------------------------------------------
    # Time calculations
    # ------------------------------------------------------------
    def _fmt_min(self, seconds):
        if seconds is None:
            return ""
        m, s = divmod(seconds, 60)
        return f"{m:d}:{s:02d}"

    def _fmt(self, seconds):
        if seconds is None:
            return ""
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"

    def _compute_times(self):
        # Splits
        self.splits = []
        last = 0
        self.cum_loss = 0

        def calc_leg_loss_pace(seq, time):
            if time is None:
                return None, None, None
            leg = time - last if last is not None else None

            best = (
                self.db.query(func.min(RunSplit.leg_time))
                .filter_by(course_id=self.course.id, seq=seq)
                .scalar()
            )

            loss = 0 if leg is None or best is None or best >= leg else leg - best
            self.cum_loss += loss

            control = self.controls[seq + 1]   # skip start
            pace_sec = None
            if control.leg_length and leg is not None:
                pace_sec = round(leg * 1000.0 / control.leg_length)
            else:
                pace_sec = None
            return leg, loss, pace_sec

        for seq, (code, time) in enumerate(self.result.visited):
            leg, loss, pace_sec = calc_leg_loss_pace(seq, time)
            self.splits.append((code, time, leg, loss, pace_sec))
            last = time

        self.run_time = self.card.finish_time - self.card.start_time
        leg, loss, pace_sec = calc_leg_loss_pace(len(self.result.visited), self.run_time)
        self.finish_leg = leg
        self.finish_loss = loss

    def get_standing(self, total):
        # All results in this group for this day
        q = (
            self.db.query(Run.result)
            .join(Competitor)
            .filter(
                Competitor.group == self.competitor.group,
                Run.day == self.day,
                Run.result != None,    # noqa: E711
            )
        )

        all_count = q.count()

        # Count how many have STRICTLY better results
        better_count = q.filter(Run.result < total).count()

        return better_count + 1, all_count

    # ------------------------------------------------------------
    # Printer output
    # ------------------------------------------------------------
    def print(self, p: Printer):
        p.bold_on()
        p.text(f"{'=' * 48}\n")
        p.text(f"E{self.day} - {self.race_name}\n")
        p.bold_off()

        p.text(f"{self.race_date} {self.place}\n")
        p.text(f"{'-' * 48}\n")

        # Name + club
        p.bold_on()
        p.text(f"{self.name:<35}{self.club:>13}\n")
        p.bold_off()

        # Category + distance
        km = self.course.length / 1000.0
        p.underline2_on()
        dist_s = f"{km}km {self.course.climb}m"
        p.text(f"{self.category:<35}{dist_s:>13}\n")
        p.underline_off()

        check_str = f"Check: {self._fmt(self.card.check_time)}"
        start_str = f"Start: {self._fmt(self.card.start_time)}"
        finish_str = f"Finish: {self._fmt(self.card.finish_time)}"
        si_str = f"SI:{self.card.card_number}"

        p.text(f"{check_str:<20}{finish_str:>28}\n")
        p.text(f"{start_str:<20}{si_str:>28}\n")

        p.text("=" * 48 + "\n")

        # Splits
        for i, (code, cum, leg, loss, pace_sec) in enumerate(self.splits, 1):
            cum_s = '-----' if cum is None else self._fmt(cum)
            leg_s = '-----' if leg is None else self._fmt(leg)

            loss_s = '' if loss is None or loss <= 0 else f"+{self._fmt(loss)}"
            pace_s = '' if not pace_sec else '~' + self._fmt_min(pace_sec)

            if i == len(self.splits):
                p.underline2_on()
            p.text(f"{i:>2}. {code:>3}{cum_s:>10}{leg_s:>10}{loss_s:>10}{pace_s:>10}\n")
            if i == len(self.splits):
                p.underline_off()

        # Total
        p.underline2_on()
        p.bold_on()
        status = "OK" if self.result.all_visited and self.result.order_correct else "DSQ"

        total_str = self._fmt(self.run_time)

        # Pace
        km = self.course.length / 1000.0
        pace = self._fmt_min(int(self.run_time / km)) if km > 0 else ""
        finish_leg_s = '' if self.finish_leg is None else self._fmt(self.finish_leg)
        finish_loss_s = '' if self.finish_loss is None or self.finish_loss <= 0 else f'+{self._fmt(self.finish_loss)}'

        p.text(f"   {status:>4}{total_str:>10}{finish_leg_s:>10}{finish_loss_s:>10}{'':>10}\n")
        p.bold_off()
        p.underline_off()

        p.text("=" * 48 + "\n")

        # Footer
        cum_loss_s = f"+{self._fmt(self.cum_loss)}"
        p.text(f"поточне відставання: {cum_loss_s:>16}{'min/km':>10}\n")
        place, all_count = self.get_standing(self.run_time)
        standing_s = f"турнірна таблиця: {place}/{all_count}" if status == 'OK' else ''
        p.text(f"{standing_s:<28}{pace:>19}\n")

        p.feed(3)
        p.cut()
