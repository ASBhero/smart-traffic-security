from fastapi import APIRouter, UploadFile, File

from services.firmware_service import calculate_hash
from services.hsm_client import HSMClient


router = APIRouter(
    prefix="/firmware",
    tags=["Firmware"]
)


hsm = HSMClient()


@router.post("/upload")
async def upload_firmware(
    file: UploadFile = File(...)
):

    path = f"uploads/{file.filename}"


    with open(path,"wb") as f:
        f.write(await file.read())


    firmware_hash = calculate_hash(path)


    signature = hsm.sign_data(
        firmware_hash
    )


    return {

        "firmware": file.filename,
        "hash": firmware_hash,
        "signature": signature

    }
