import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Patient
from .schemas import PatientCreate, PatientOut, PatientUpdate, normalize_phone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("carecloud")

app = FastAPI(title="CareCloud Voice AI Patient Registration", version="1.0.0")
Base.metadata.create_all(bind=engine)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

def envelope(data: Any = None, error: Any = None):
    return {"data": data, "error": error}

def patient_dict(p: Patient):
    return PatientOut.model_validate(p).model_dump(mode="json")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    details = []
    for err in exc.errors():
        details.append({"field": ".".join(str(x) for x in err.get("loc", [])[1:]), "message": err.get("msg")})
    return JSONResponse(status_code=422, content=envelope(error={"code": "validation_error", "message": "Invalid request data", "details": details}))

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content=envelope(error={"code": "http_error", "message": str(exc.detail)}))

@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception("Unhandled server error")
    return JSONResponse(status_code=500, content=envelope(error={"code": "internal_error", "message": "Internal server error"}))

@app.get("/health")
def health():
    return envelope({"status": "ok"})

@app.get("/patients")
def list_patients(last_name: str | None = None, date_of_birth: str | None = None, phone_number: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Patient).where(Patient.deleted_at.is_(None))
    if last_name:
        stmt = stmt.where(Patient.last_name.ilike(last_name.strip()))
    if date_of_birth:
        from .schemas import parse_dob
        try:
            dob = parse_dob(date_of_birth)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        stmt = stmt.where(Patient.date_of_birth == dob)
    if phone_number:
        try:
            phone = normalize_phone(phone_number)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        stmt = stmt.where(Patient.phone_number == phone)
    patients = db.scalars(stmt.order_by(Patient.created_at.desc())).all()
    return envelope([patient_dict(p) for p in patients])

@app.get("/patients/{patient_id}")
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return envelope(patient_dict(p))

@app.post("/patients", status_code=201)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    p = Patient(**payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    logger.info("PATIENT_CREATED payload=%s", json.dumps(patient_dict(p), default=str))
    return envelope(patient_dict(p))

@app.put("/patients/{patient_id}")
def update_patient(patient_id: str, payload: PatientUpdate, db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Patient not found")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(p, key, value)
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)
    logger.info("PATIENT_UPDATED patient_id=%s fields=%s", patient_id, sorted(updates.keys()))
    return envelope(patient_dict(p))

@app.delete("/patients/{patient_id}")
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if not p or p.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Patient not found")
    p.deleted_at = datetime.now(timezone.utc)
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    return envelope({"patient_id": patient_id, "deleted": True})

@app.post("/vapi/tool")
async def vapi_tool(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    message = body.get("message", {})
    tool_calls = message.get("toolCallList", [])
    results = []

    for call in tool_calls:
        tool_id = call.get("id")
        name = call.get("name")
        args = call.get("arguments") or {}
        try:
            if name == "lookup_patient_by_phone":
                phone = normalize_phone(args.get("phone_number"))
                patient = db.scalar(select(Patient).where(Patient.phone_number == phone, Patient.deleted_at.is_(None)))
                result = {"found": bool(patient), "patient": patient_dict(patient) if patient else None}
            elif name == "save_patient":
                payload = PatientCreate.model_validate(args)
                p = Patient(**payload.model_dump())
                db.add(p)
                db.commit()
                db.refresh(p)
                logger.info("VOICE_PATIENT_CREATED call_id=%s payload=%s", message.get("call", {}).get("id"), json.dumps(patient_dict(p), default=str))
                result = {"success": True, "patient_id": p.patient_id, "patient": patient_dict(p)}
            elif name == "update_patient":
                patient_id = args.pop("patient_id", None)
                p = db.get(Patient, patient_id) if patient_id else None
                if not p or p.deleted_at is not None:
                    result = {"success": False, "error": "Patient not found"}
                else:
                    payload = PatientUpdate.model_validate(args)
                    updates = payload.model_dump(exclude_unset=True)
                    for key, value in updates.items():
                        setattr(p, key, value)
                    p.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    db.refresh(p)
                    result = {"success": True, "patient": patient_dict(p)}
            else:
                result = {"success": False, "error": f"Unsupported tool: {name}"}
        except Exception as exc:
            db.rollback()
            logger.exception("Vapi tool failure: %s", name)
            result = {"success": False, "error": str(exc)}
        results.append({"toolCallId": tool_id, "result": result})
    return {"results": results}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    patients = db.scalars(select(Patient).where(Patient.deleted_at.is_(None)).order_by(Patient.created_at.desc())).all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "patients": patients})
