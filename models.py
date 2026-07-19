<<<<<<< HEAD
from sqlalchemy import Column, String, DateTime
from database import Base
from datetime import datetime



class Device(Base):

    __tablename__ = "devices"


    id = Column(
        String,
        primary_key=True
    )


    public_key = Column(String)

    certificate = Column(String)


    status = Column(
        String,
        default="pending"
    )


    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )




class Firmware(Base):

    __tablename__ = "firmware"


    version = Column(
        String,
        primary_key=True
    )


    hash = Column(String)

    signature = Column(String)


    status = Column(
        String,
        default="unsigned"
    )




class Certificate(Base):

    __tablename__ = "certificates"


    serial = Column(
        String,
        primary_key=True
    )


    device_id = Column(String)


    certificate_data = Column(String)


    status = Column(
        String,
        default="active"
    )    
from sqlalchemy import Integer


class AuditLog(Base):

    __tablename__ = "audit_logs"


    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )


    event = Column(String)

    entity = Column(String)

    entity_id = Column(String)

    timestamp = Column(
        DateTime,
        default=datetime.utcnow
=======
from sqlalchemy import Column, String, DateTime
from database import Base
from datetime import datetime



class Device(Base):

    __tablename__ = "devices"


    id = Column(
        String,
        primary_key=True
    )


    public_key = Column(String)

    certificate = Column(String)


    status = Column(
        String,
        default="pending"
    )


    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )




class Firmware(Base):

    __tablename__ = "firmware"


    version = Column(
        String,
        primary_key=True
    )


    hash = Column(String)

    signature = Column(String)


    status = Column(
        String,
        default="unsigned"
    )




class Certificate(Base):

    __tablename__ = "certificates"


    serial = Column(
        String,
        primary_key=True
    )


    device_id = Column(String)


    certificate_data = Column(String)


    status = Column(
        String,
        default="active"
    )    
from sqlalchemy import Integer


class AuditLog(Base):

    __tablename__ = "audit_logs"


    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )


    event = Column(String)

    entity = Column(String)

    entity_id = Column(String)

    timestamp = Column(
        DateTime,
        default=datetime.utcnow
>>>>>>> origin/cms
    )