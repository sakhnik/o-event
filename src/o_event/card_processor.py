from o_event.receipt import Receipt
from o_event.printer import Printer
from o_event.analysis import Analysis
from o_event.models import (
    Card,
    Competitor,
    Config,
    Course,
    CourseControl,
    Punch,
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
    def handle_card(self, db, readout: PunchReadout, printer: Printer) -> Card:
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

        actual_punches = []
        for item in readout.punches:
            actual_punches.append((item.code, item.time - readout.startTime))

        # competitor lookup
        competitor = (
            db.query(Competitor)
            .filter(Competitor.sid == readout.cardNumber)
            .first()
        )

        # CASE 1: Unknown card → leave unassigned
        if competitor is None:
            db.commit()
            return {"status": "UNK", "reason": "unknown card"}

        day = Config.get(db, Config.KEY_CURRENT_DAY)
        run = get_current_run(db, day, competitor)

        # Check for duplicate for this competitor on this stage
        existing = (
            db.query(Card)
            .filter(Card.run_id == run.id)
            .first()
        )

        if existing:
            # card.run_id = run.id
            db.commit()
            return {"status": "DUP"}

        # Assign competitor & run
        card.run_id = run.id

        # calculate OK/MP
        course = get_course_for_card(db, day, competitor)

        # fetch required controls
        controls = (
            db.query(CourseControl)
            .filter(CourseControl.course_id == course.id)
            .order_by(CourseControl.seq)
            .all()
        )
        required_codes = [int(c.control_code) for c in controls if c.control_code.isdigit()]

        result = Analysis().analyse_order(required_codes, actual_punches)
        if result.all_visited and result.order_correct:
            card.status = Status.OK
        else:
            card.status = Status.MP
        run.result = card.finish_time - card.start_time

        for (code, time) in result.visited:
            pd = Punch(
                card_id=card.id,
                code=code,
                punch_time=time,
            )
            db.add(pd)

        self.store_run_splits(db, run, card, course, result)

        db.commit()

        Receipt(db, result, card, course, controls).print(printer)

        return {"status": card.status.value}

    def store_run_splits(self, db, run, card, course, result):
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
            leg_time = None if last_time is None else card.finish_time - last_time
            split = RunSplit(
                run_id=run.id,
                course_id=course.id,
                seq=len(result.visited),
                control_code='F',
                leg_time=leg_time,
                cum_time=card.finish_time,
            )
            db.add(split)
