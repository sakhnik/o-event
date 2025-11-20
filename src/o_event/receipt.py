from o_event.analysis import Analysis
from o_event.printer import Printer
from o_event.models import Card, Competitor, Config, Course, CourseControl
from datetime import date
from typing import List


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
        for i, (code, time) in enumerate(self.result.visited):
            leg = time - last
            last = time

            loss = 0
            # if self.splits:
            #     prev_leg = self.splits[-1][2]
            #     loss = leg - prev_leg if leg > prev_leg else 0

            control = self.controls[i + 1]   # skip start
            pace_sec = None
            if control.leg_length:
                pace_sec = round(leg * 1000.0 / control.leg_length)

            self.splits.append((code, time, leg, loss, pace_sec))

        self.standing = "—"
        self.current_gap = "—"

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
        p.text(f"{self.name:<35}{self.club}\n")
        p.bold_off()

        # Category + distance
        km = self.course.length / 1000.0
        p.underline2_on()
        p.text(f"{self.category:<35}{km:.3f}km {self.course.climb}m\n")
        p.underline_off()

        start_str = self._fmt(self.card.start_time)
        finish_str = self._fmt(self.card.finish_time)
        check_str = self._fmt(self.card.check_time)

        p.text(f"Check: {check_str:<20}Finish: {finish_str}\n")
        p.text(f"Start: {start_str:<20}SI:{self.card.card_number}\n")

        p.text("=" * 48 + "\n")

        # Splits
        for i, (code, cum, leg, loss, pace_sec) in enumerate(self.splits, 1):
            cum_s = self._fmt(cum)
            leg_s = self._fmt(leg)
            loss_s = f"+{self._fmt(loss)}" if loss > 0 else ""
            if i == len(self.splits):
                p.underline2_on()
            pace_s = ('~' + self._fmt_min(pace_sec)) if pace_sec else ''
            p.text(f"{i:>2}. {code:>3}{cum_s:>10}{leg_s:>10}{loss_s:>10}{pace_s:>10}\n")
            if i == len(self.splits):
                p.underline_off()

        # Total
        p.underline2_on()
        p.bold_on()
        status = "OK" if self.result.all_visited and self.result.order_correct else "MP"

        total = self.card.finish_time - self.card.start_time
        total_str = self._fmt(total)

        # Pace
        km = self.course.length / 1000.0
        pace = self._fmt_min(int(total / km)) if km > 0 else ""
        if self.result.visited:
            finish_leg = self._fmt(total - self.result.visited[-1][1])
        else:
            finish_leg = ''

        p.text(f"     {status}{total_str:>10}{finish_leg:>10}\n")
        p.bold_off()
        p.underline_off()

        p.text("=" * 48 + "\n")

        # Footer
        p.text(f"поточне відставання: {self.current_gap}\n")
        p.text(f"турнірна таблиця: {self.standing:<10}{pace}min/km\n")

        p.feed(3)
        p.cut()
