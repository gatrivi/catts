from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, HttpUrl

from api.deps import require_api_key

router = APIRouter(tags=["meta"])


class ExternalLink(BaseModel):
    label: str
    url: HttpUrl
    note: str | None = None


class LinksResponse(BaseModel):
    links: List[ExternalLink]


@router.get("/links", response_model=LinksResponse)
async def get_links(_: None = Depends(require_api_key)) -> LinksResponse:
    # Kept static (hardcoded) for now; endpoint exists mainly so UI can render it consistently.
    return LinksResponse(
        links=[
            ExternalLink(
                label="LiteUI-Studio",
                url="https://github.com/FJWRnoArina/LiteUI-Studio",
                note="Standalone local AI audio-visual creation workstation (ComfyUI wrapper).",
            ),
            ExternalLink(
                label="LiteUI-Studio (short link)",
                url="https://t.co/tisnj26TZ9",
                note="Original short URL you provided.",
            ),
        ]
    )

