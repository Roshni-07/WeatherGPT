from fastapi import APIRouter

router = APIRouter()


@router.get("/active")
def active_alerts():
    # TODO: query alerts table for non-expired rows
    return {"alerts": []}
