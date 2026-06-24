from database import SessionLocal
from models import AuditLog



def log_event(
    event,
    entity,
    entity_id
):

    db = SessionLocal()


    log = AuditLog(
        event=event,
        entity=entity,
        entity_id=entity_id
    )


    db.add(log)
    db.commit()

    db.close()