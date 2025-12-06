#!/usr/bin/env python3

from o_event.card_processor import PunchReadout, CardProcessor
from o_event.printer import PrinterMux
from o_event.db import SessionLocal

import uvicorn
from fastapi import FastAPI, HTTPException, Request
import traceback
from pydantic import ValidationError

# -----------------------------------------------------------------------------------
# DB Setup
# -----------------------------------------------------------------------------------

app = FastAPI(title="Card Listener")


@app.post("/card")
async def receive_card(request: Request):
    raw = await request.body()
    print(raw)

    db = SessionLocal()
    try:
        data = PunchReadout.model_validate_json(raw)
        with PrinterMux() as printer:
            result = CardProcessor().handle_readout(db, data, printer)
            print('\n'.join(printer.get_output()))
            print(result)
            return result

        return {"status": "ok", "parsed": data}
    except ValidationError as e:
        print("VALIDATION ERROR:", e)
        return {"error": "validation failed", "details": e.errors()}
    except Exception as ex:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(ex))

    finally:
        db.close()


if __name__ == "__main__":
    print("Listening for card data on port 12345...")
    uvicorn.run("card_service:app", host="0.0.0.0", port=12345, reload=False)
