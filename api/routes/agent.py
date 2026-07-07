"""Dashboard agent routes — omp (Oh My Pi) bridge."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.deps import require_api_key
from api.schemas import AgentPromptRequest, AgentPromptResponse
from services import omp_client

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/status")
async def agent_status(_: None = Depends(require_api_key)):
    return await omp_client.omp_status()


@router.post("/prompt", response_model=AgentPromptResponse)
async def agent_prompt(body: AgentPromptRequest, _: None = Depends(require_api_key)):
    if not omp_client.resolve_omp_bin():
        raise HTTPException(503, "omp not found — set CATTS_OMP_BIN or install Oh My Pi")
    if not omp_client.token_configured():
        raise HTTPException(503, "LM Studio token missing — run scripts/setup-lmstudio.ps1")
    try:
        result = await omp_client.run_prompt(
            body.prompt,
            model=body.model,
            cwd=body.cwd,
            auto_approve=body.auto_approve,
            timeout_sec=body.timeout_sec,
        )
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    return AgentPromptResponse(**result)


@router.post("/prompt/stream")
async def agent_prompt_stream(body: AgentPromptRequest, _: None = Depends(require_api_key)):
    if not omp_client.resolve_omp_bin():
        raise HTTPException(503, "omp not found")
    if not omp_client.token_configured():
        raise HTTPException(503, "LM Studio token missing")

    async def lines():
        try:
            async for chunk in omp_client.stream_prompt(
                body.prompt,
                model=body.model,
                cwd=body.cwd,
                auto_approve=body.auto_approve,
            ):
                yield chunk if chunk.endswith("\n") else chunk + "\n"
        except Exception as exc:
            yield f'{{"type":"error","message":{exc!r}}}\n'

    return StreamingResponse(lines(), media_type="application/x-ndjson")
