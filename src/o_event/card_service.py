#!/usr/bin/env python3

from o_event.card_processor import PunchReadout, CardProcessor
from o_event.printer import Printer

import uvicorn
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# -----------------------------------------------------------------------------------
# DB Setup
# -----------------------------------------------------------------------------------

engine = create_engine("sqlite:///race.db", echo=False)
Session = sessionmaker(bind=engine)

app = FastAPI(title="Card Listener")


@app.post("/card")
def receive_card(readout: PunchReadout):
    db = Session()

    try:
        with Printer() as printer:
            return CardProcessor().handle_card(db, readout, printer)

    except Exception as ex:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(ex))

    finally:
        db.close()


if __name__ == "__main__":
    print("Listening for card data on port 12345...")
    uvicorn.run("card_service:app", host="0.0.0.0", port=12345, reload=False)
