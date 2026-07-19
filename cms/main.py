from fastapi import FastAPI

from database import engine, Base
from routers import devices
from routers import certificates
from routers import firmware

from blockchain import blockchain


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="CMS Server"
)


app.include_router(
    devices.router
)


app.include_router(
    certificates.router
)


app.include_router(
    firmware.router
)



@app.get("/")
def home():

    return {
        "message":"CMS running"
    }



@app.get("/blockchain")
def get_blockchain():

    return blockchain