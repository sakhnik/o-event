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


class PunchItem(BaseModel):
    cardNumber: int
    code: int
    time: int


class PunchReadout(BaseModel):
    stationNumber: int
    cardNumber: int
    startTime: int
    finishTime: int
    checkTime: int
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

    def handle_card(self, db, card: Card, run: Run, printer: Printer, readout: PunchReadout = None):
        if readout is None:
            readout = PunchReadout.model_validate(card.raw_json)

        competitor = run.competitor
        day = run.day

        # Assign competitor & run
        card.run_id = run.id

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

        result = Analysis().analyse_order(required_codes, actual_punches)

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
