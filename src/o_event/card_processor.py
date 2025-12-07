from o_event.receipt import Receipt
from o_event.printer import Printer
from o_event.analysis import Analysis
from o_event.models import (
    Card,
    Competitor,
    Config,
    Course,
    CourseControl,
    Run,
    RunSplit,
    Stage,
    Status,
)

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
import json


class PunchItem(BaseModel):
    cardNumber: int
    code: int
    time: int


class PunchReadout(BaseModel):
    stationNumber: int
    cardNumber: int
    startTime: int
    finishTime: int
    checkTime: Optional[int] = None
    punches: list[PunchItem]


def get_current_run(db, day, competitor):
    run = (
        db.query(Run)
        .filter(Run.day == day)
        .filter(Run.competitor_id == competitor.id)
        .first()
    )
    if not run:
        raise RuntimeError("No run configured for current race day")

    return run


def get_course_for_card(db, day, competitor):
    """
    Given a card number (competitor.sid) and day (1-based),
    return the Course that the competitor is running today.
    """

    if day not in competitor.declared_days:
        return None  # card exists but not for today

    # 3. Find stage for this day
    stage = db.query(Stage).filter_by(day=day).first()
    if not stage:
        return None

    # 4. Find course matching competitor group
    course = db.query(Course).filter_by(stage_id=stage.id, name=competitor.group).first()
    return course


class CardProcessor:
    def handle_readout(self, db, readout: PunchReadout, printer: Printer):
        # build storage object
        card = Card(
            run_id=None,
            card_number=readout.cardNumber,
            readout_datetime=datetime.now(),
            start_time=readout.startTime,
            finish_time=readout.finishTime,
            check_time=readout.checkTime,
            raw_json=readout.model_dump(),
        )
        db.add(card)
        db.flush()  # create card.id for details

        # competitor lookup
        competitor = (
            db.query(Competitor)
            .filter(Competitor.sid == readout.cardNumber)
            .first()
        )

        # CASE 1: Unknown card → leave unassigned
        if competitor is None:
            db.commit()
            return {"status": "UNK", "sid": card.card_number}

        day = Config.get(db, Config.KEY_CURRENT_DAY)
        run = get_current_run(db, day, competitor)

        # Check for duplicate for this competitor on this stage
        existing = (
            db.query(Card)
            .filter(Card.run_id == run.id, Card.raw_json != card.raw_json)
            .first()
        )

        if existing:
            # card.run_id = run.id
            db.commit()
            return {"status": "DUP", "sid": card.card_number}

        return self.handle_card(db, card, run, printer, readout)

    def retime_local_anchors(self, punches: List[PunchItem], max_leg: int = 1800) -> List[PunchItem]:
        n = len(punches)
        if n == 0:
            return punches

        reliable_idx = [0]  # first punch is always reliable

        # Step 1: mark reliable punches
        for i in range(1, n):
            delta = punches[i].time - punches[reliable_idx[-1]].time
            if 0 < delta <= max_leg:
                reliable_idx.append(i)
            # else: outlier

        # Step 2: ensure last punch is reliable
        if reliable_idx[-1] != n - 1:
            reliable_idx.append(n - 1)

        # Step 3: interpolate sequences of outliers between reliable punches
        for r in range(len(reliable_idx) - 1):
            start_idx = reliable_idx[r]
            end_idx = reliable_idx[r + 1]
            t_start = punches[start_idx].time
            t_end = punches[end_idx].time
            num_outliers = end_idx - start_idx - 1
            if num_outliers <= 0:
                continue
            # strictly increasing timestamps for outliers
            for i in range(1, num_outliers + 1):
                punches[start_idx + i].time = int(t_start + i * (t_end - t_start) / (num_outliers + 1))

        return punches

    def handle_card(self, db, card: Card, run: Run, printer: Printer, readout: PunchReadout | None = None):
        if readout is None:
            readout = PunchReadout.model_validate(card.raw_json)
        if readout.startTime == 0xeeee:
            print("No start time!")
            return {"status": "NO_START", "sid": card.card_number}
        if readout.finishTime == 0xeeee:
            print("No finish time!")
            return {"status": "NO_FINISH", "sid": card.card_number}

        competitor = run.competitor
        day = run.day

        # Assign competitor & run
        card.run_id = run.id

        readout.punches = self.retime_local_anchors(readout.punches)

        actual_punches = []
        for item in readout.punches:
            actual_punches.append((item.code, item.time - readout.startTime))

        # calculate OK/MP
        course = get_course_for_card(db, day, competitor)
        if not course:
            db.commit()
            return {"status": "UNK_COURSE", "sid": card.card_number}

        # fetch required controls
        controls = (
            db.query(CourseControl)
            .filter(CourseControl.course_id == course.id)
            .order_by(CourseControl.seq)
            .all()
        )
        required_codes = [int(c.control_code) for c in controls if c.control_code.isdigit()]

        ignore_controls = json.loads(Config.get(db, Config.KEY_IGNORE_CONTROLS, '[]'))

        result = Analysis().analyse_order(required_codes, actual_punches, ignore_controls)

        run.start = card.start_time
        run.finish = card.finish_time
        run.result = card.finish_time - card.start_time
        if result.all_visited and result.order_correct:
            run.status = Status.OK
            card.status = Status.OK
        else:
            run.status = Status.MP
            card.status = Status.MP

        self.store_run_splits(db, run, card, course, result)

        db.commit()

        printer.logo()
        Receipt(db, result, card, course, controls).print(printer)

        return {"status": card.status.value}

    def store_run_splits(self, db, run, card, course, result):
        # Delete previous splits for this run
        db.query(RunSplit).filter(RunSplit.run_id == run.id).delete()

        prev_time = 0

        for seq, (code, time) in enumerate(result.visited):
            if time is not None and time >= 0:
                # Normal punch
                leg_time = time - prev_time
                prev_time = time
            else:
                # Missing control
                leg_time = None

            split = RunSplit(
                run_id=run.id,
                course_id=course.id,
                seq=seq,
                control_code=code,
                leg_time=leg_time,
                cum_time=time,
            )
            db.add(split)

        if result.visited:
            last_time = result.visited[-1][1]
            run_time = card.finish_time - card.start_time
            leg_time = None if last_time is None else run_time - last_time
            split = RunSplit(
                run_id=run.id,
                course_id=course.id,
                seq=len(result.visited),
                control_code='F',
                leg_time=leg_time,
                cum_time=run_time,
            )
            db.add(split)
