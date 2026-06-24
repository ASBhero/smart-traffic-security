from fastapi import APIRouter
from services.certificate_manager import issue_certificate


router = APIRouter(
    prefix="/certificates",
    tags=["Certificates"]
)



@router.post("/issue")
def issue(data:dict):

    result = issue_certificate(
        data["device_id"]
    )


    return result