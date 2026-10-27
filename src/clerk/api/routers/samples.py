from fastapi import APIRouter

from clerk.services.demo_samples import SAMPLE_MESSAGES

router = APIRouter(prefix="/api", tags=["samples"])


@router.get("/samples")
async def list_samples() -> dict[str, dict[str, str]]:
    return {
        sample_id: {"text": text}
        for sample_id, text in SAMPLE_MESSAGES.items()
    }
