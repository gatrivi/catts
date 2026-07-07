from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import require_api_key
from services.diagnostics import get_run, run_smoke

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.post("/smoke")
async def run_smoke_check(_: None = Depends(require_api_key)):
    diagnostic_id = await run_smoke()
    return {"diagnostic_id": diagnostic_id, "status": "running"}


@router.get("/{diagnostic_id}")
async def get_smoke_check(diagnostic_id: str, _: None = Depends(require_api_key)):
    run = get_run(diagnostic_id)
    if not run:
        raise HTTPException(404, "Diagnostic not found")
    return run

