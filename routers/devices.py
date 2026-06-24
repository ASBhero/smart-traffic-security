from fastapi import APIRouter
from database import SessionLocal
from models import Device

from services.audit_service import log_event
from services.blockchain_service import create_record
from blockchain import add_block


router = APIRouter(
    prefix="/devices",
    tags=["Devices"]
)


@router.post("/register")
def register_device(data: dict):

    db = SessionLocal()


    device = Device(
        id=data["device_id"],
        public_key=data["public_key"],
        status="active"
    )


    db.add(device)
    db.commit()
    db.refresh(device)



    # Audit log
    log_event(
        "DEVICE_REGISTERED",
        "DEVICE",
        device.id
    )


    # Blockchain log
    block = create_record({

        "event":"DEVICE_REGISTERED",

        "device_id":device.id,

        "public_key":device.public_key

    })


    add_block(block)



    return {

        "message":"Device registered",

        "device_id":device.id,

        "status":device.status

    }



@router.post("/revoke/{device_id}")
def revoke_device(device_id:str):

    db = SessionLocal()


    device = db.query(Device).filter(
        Device.id == device_id
    ).first()


    if not device:
        return {
            "error":"device not found"
        }


    device.status="revoked"

    db.commit()


    log_event(
        "DEVICE_REVOKED",
        "DEVICE",
        device_id
    )


    block = create_record({

        "event":"DEVICE_REVOKED",

        "device_id":device_id,

        "status":"revoked"

    })


    add_block(block)



    return {

        "device":device_id,

        "status":"revoked"

    }


   

