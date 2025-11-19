#!/usr/bin/env python3

from receipt import Receipt
from printer import Printer
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import (
    Card,
    Competitor,
    Config,
    Course,
    CourseControl,
    Punch,
    Run,
    Stage,
    Status,
)

# -----------------------------------------------------------------------------------
# DB Setup
# -----------------------------------------------------------------------------------

engine = create_engine("sqlite:///race.db", echo=False)
Session = sessionmaker(bind=engine)

app = FastAPI(title="Card Listener")

# -----------------------------------------------------------------------------------
# Request models
# -----------------------------------------------------------------------------------


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

# -----------------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------------


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


def determine_status(required_codes, actual_codes):
    """Return OK if required course codes match in order, MP otherwise."""
    ptr = 0
    for c in actual_codes:
        if ptr < len(required_codes) and c == required_codes[ptr]:
            ptr += 1
    return Status.OK if ptr == len(required_codes) else Status.MP


# -----------------------------------------------------------------------------------
# Main Endpoint
# -----------------------------------------------------------------------------------

@app.post("/card")
def receive_card(readout: PunchReadout):
    db = Session()

    try:
        # build storage object
        card = Card(
            run_id=None,
            card_number=readout.cardNumber,
            readout_datetime=datetime.now(),
            start_time=readout.startTime,
            finish_time=readout.finishTime,
            check_time=readout.checkTime,
            raw_json=readout.dict(),
        )
        db.add(card)
        db.flush()  # create card.id for details

        # store the nested punches
        actual_codes = []
        for item in readout.punches:
            actual_codes.append(item.code)
            pd = Punch(
                card_id=card.id,
                code=item.code,
                punch_time=item.time,
            )
            db.add(pd)

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

        card.status = determine_status(required_codes, actual_codes)

        db.commit()

        with Printer() as p:
            Receipt(db, card.id).print(p)

        return {"status": card.status}

    except Exception as ex:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(ex))

    finally:
        db.close()


if __name__ == "__main__":
    print("Listening for card data on port 12345...")
    uvicorn.run("card_service:app", host="0.0.0.0", port=12345, reload=False)
