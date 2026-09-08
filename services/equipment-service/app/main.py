from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, init_db
from app.models.equipment_info import EquipmentInfo
from app.models.equipment_unit import EquipmentUnit
from app.routers.equipment import router as equipment_router

app = FastAPI(title="equipment-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    db: Session = SessionLocal()
    try:
        if db.query(EquipmentInfo).count() == 0:
            db.add(EquipmentInfo(equipmentId="eq1", name="Projector PX-200", category="display", notes="Includes HDMI + VGA adapters"))
            db.add(EquipmentInfo(equipmentId="eq2", name="Wireless mic set", category="audio", notes="Fully booked Thursday"))
            db.add(EquipmentInfo(equipmentId="eq3", name="LED wall panel", category="display", notes="Flagged unavailable"))
            db.add(EquipmentUnit(unitId="u-eq1", equipmentId="eq1", status="available"))
            db.add(EquipmentUnit(unitId="u-eq2", equipmentId="eq2", status="reserved"))
            db.add(EquipmentUnit(unitId="u-eq3", equipmentId="eq3", status="maintenance"))
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"service": "equipment-service", "status": "ok"}


app.include_router(equipment_router)
