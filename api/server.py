from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .breeze import get_breeze_client
from .printer import get_printer, LabelData
from .codes import generate_code, decode_checkin_code, validate_checkin_code


MAX_BATCH_SIZE = 15  # Breeze rate limit is ~20 req/min, leave headroom


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await get_breeze_client().close()


app = FastAPI(title="Breeze Check-in API", lifespan=lifespan)

# CORS: localhost dev ports + LAN IPs
_LAN_PATTERN = re.compile(r"^https?://192\.168\.\d+\.\d+:\d+$")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:4173",
    ],
    allow_origin_regex=r"^https?://192\.168\.\d+\.\d+:\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---


class CheckinRequest(BaseModel):
    instance_id: str
    person_id: str
    print_label: bool = True


class CheckinPerson(BaseModel):
    person_id: str
    name: str
    code: str


class BatchCheckinRequest(BaseModel):
    instance_id: str
    people: List[CheckinPerson]
    extra_labels: List[LabelData] = []
    print_labels: bool = True


class PrintRequest(BaseModel):
    labels: List[LabelData]


# --- Health ---


@app.get("/health")
async def health():
    return {"status": "ok"}


# --- Printer ---


@app.get("/printer/status")
async def printer_status():
    printer = get_printer()
    connected = await printer.is_connected()
    return {"connected": connected}


@app.get("/printer/list")
async def printer_list():
    printer = get_printer()
    printers_xml = await printer.get_printers()
    return {"printers": printers_xml}


@app.post("/printer/print")
async def print_labels(request: PrintRequest):
    printer = get_printer()
    success = await printer.print_labels(request.labels)
    if not success:
        raise HTTPException(status_code=500, detail="Print failed")
    return {"success": True, "count": len(request.labels)}


# --- Events ---


@app.get("/events")
async def list_events(start: Optional[str] = None, end: Optional[str] = None):
    breeze = get_breeze_client()
    # Default to today if no start provided
    if start is None:
        start = date.today().isoformat()
    try:
        events = await breeze.get_events(start=start, end=end)
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events/{instance_id}/eligible")
async def eligible_people(instance_id: str):
    breeze = get_breeze_client()
    try:
        people = await breeze.get_eligible_people(instance_id)
        return {"people": people}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events/{instance_id}/attendance")
async def list_attendance(instance_id: str):
    breeze = get_breeze_client()
    try:
        attendance = await breeze.list_attendance(instance_id)
        return {"attendance": attendance}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Check-in ---


@app.post("/checkin")
async def checkin(request: CheckinRequest):
    """Check in a single person and optionally print a label."""
    breeze = get_breeze_client()
    try:
        success = await breeze.add_attendance(request.instance_id, request.person_id)
        if not success:
            raise HTTPException(status_code=400, detail="Check-in failed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Breeze API error: {e}")

    return {"success": True, "person_id": request.person_id}


@app.post("/checkin/batch")
async def batch_checkin(request: BatchCheckinRequest):
    """Check in multiple people and print labels in one batch."""
    if len(request.people) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size {len(request.people)} exceeds max of {MAX_BATCH_SIZE}",
        )

    breeze = get_breeze_client()
    printer = get_printer()

    async def _checkin_one(person: CheckinPerson) -> dict:
        try:
            success = await breeze.add_attendance(
                request.instance_id, person.person_id
            )
            if success:
                return {"person_id": person.person_id, "success": True}
            return {"person_id": person.person_id, "success": False, "error": "Failed"}
        except Exception as e:
            return {"person_id": person.person_id, "success": False, "error": str(e)}

    # Fire attendance calls in parallel
    results = await asyncio.gather(*[_checkin_one(p) for p in request.people])

    # Build label list from successful check-ins
    labels_to_print: list[LabelData] = []
    if request.print_labels:
        successful_ids = {r["person_id"] for r in results if r["success"]}
        for person in request.people:
            if person.person_id in successful_ids:
                labels_to_print.append(
                    LabelData(name=person.name, code=person.code)
                )
        # Append extra labels (parent tear-offs)
        labels_to_print.extend(request.extra_labels)

    print_success = False
    if labels_to_print:
        print_success = await printer.print_labels(labels_to_print)

    return {
        "results": list(results),
        "labels_printed": len(labels_to_print) if print_success else 0,
    }


@app.post("/checkout")
async def checkout(instance_id: str, person_id: str):
    """Check out a person from an event."""
    breeze = get_breeze_client()
    try:
        success = await breeze.delete_attendance(instance_id, person_id)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- People & Families ---


@app.get("/people/{person_id}")
async def get_person(person_id: str):
    """Get a person's details."""
    breeze = get_breeze_client()
    try:
        person = await breeze.get_person(person_id)
        return {"person": person}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _normalize_family(raw_family: list) -> list:
    """Flatten Breeze family records into Person-shaped dicts."""
    result = []
    for member in raw_family:
        details = member.get("details", {})
        result.append({
            "id": member.get("person_id") or details.get("id", member.get("id")),
            "first_name": details.get("first_name", ""),
            "force_first_name": details.get("force_first_name", ""),
            "last_name": details.get("last_name", ""),
            "role_name": member.get("role_name", ""),
        })
    return result


@app.get("/people/{person_id}/family")
async def get_family(person_id: str):
    """Get a person's family members."""
    breeze = get_breeze_client()
    try:
        family = await breeze.get_family(person_id)
        return {"family": _normalize_family(family)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/people/{person_id}/with-family")
async def get_person_with_family(person_id: str):
    """Get a person and their family members in one call."""
    breeze = get_breeze_client()
    try:
        person = await breeze.get_person_with_family(person_id)
        return {"person": person}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Codes ---


@app.get("/codes/generate")
async def generate_checkin_code(person_id: str, instance_id: str):
    """Generate a check-in code for a person/instance."""
    code = generate_code(person_id, instance_id)
    return {"code": code, "person_id": person_id, "instance_id": instance_id}


@app.get("/codes/decode/{code}")
async def decode_code(code: str):
    """Decode a check-in code back to its components."""
    decoded = decode_checkin_code(code)
    if decoded is None:
        raise HTTPException(status_code=400, detail="Invalid code")
    return decoded


@app.post("/codes/validate")
async def validate_code(code: str, instance_id: Optional[str] = None):
    """Validate a check-in code, optionally against expected instance."""
    decoded = validate_checkin_code(code, expected_instance_id=instance_id)
    if decoded is None:
        return {"valid": False}
    return {"valid": True, **decoded}
