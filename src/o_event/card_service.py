#!/usr/bin/env python3

from o_event.card_processor import PunchReadout, CardProcessor
from o_event.printer import Printer
from o_event.db import SessionLocal

import uvicorn
from fastapi import FastAPI, HTTPException

# -----------------------------------------------------------------------------------
# DB Setup
# -----------------------------------------------------------------------------------

app = FastAPI(title="Card Listener")


class PrinterMux:
    def __init__(self):
        self.parts = []

    def __enter__(self):
        self.parts.clear()
        try:
            self.p = Printer().__enter__()
        except Exception as e:
            print(e)
            self.p = None
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.p:
            self.p.__exit__(exc_type, exc, tb)
        self.p = None

    def __getattr__(self, name):
        def mocked_method(*args, **kwargs):
            if self.p:
                return self.p.__getattr__(name)(*args, **kwargs)
        return mocked_method

    def text(self, t):
        self.parts.append(t)
        if self.p:
            self.p.text(t)

    def get_output(self):
        return ''.join(self.parts).split('\n')


@app.post("/card")
def receive_card(readout: PunchReadout):
    db = SessionLocal()

    try:
        with PrinterMux() as printer:
            result = CardProcessor().handle_card(db, readout, printer)
            print('\n'.join(printer.get_output()))
            return result

    except Exception as ex:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(ex))

    finally:
        db.close()


if __name__ == "__main__":
    print("Listening for card data on port 12345...")
    uvicorn.run("card_service:app", host="0.0.0.0", port=12345, reload=False)
