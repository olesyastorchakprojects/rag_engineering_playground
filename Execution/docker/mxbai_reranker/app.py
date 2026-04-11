import os
from contextlib import asynccontextmanager
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from mxbai_rerank import MxbaiRerankV2


MODEL_ID = os.environ.get("MODEL_ID", "mixedbread-ai/mxbai-rerank-base-v2")
_model_lock = Lock()


class RerankRequest(BaseModel):
    query: str
    texts: list[str] = Field(min_length=1)
    top_n: int | None = Field(default=None, ge=1)
    instruction: str | None = None


def _to_public_result(item: Any, texts: list[str], fallback_index: int) -> dict[str, Any]:
    if isinstance(item, dict):
        index = item.get("index", fallback_index)
        text = item.get("text")
        if text is None and isinstance(index, int) and 0 <= index < len(texts):
            text = texts[index]
        return {
            "index": index,
            "score": item.get("score"),
            "text": text,
        }

    index = getattr(item, "index", fallback_index)
    text = getattr(item, "text", None)
    if text is None and isinstance(index, int) and 0 <= index < len(texts):
        text = texts[index]
    return {
        "index": index,
        "score": getattr(item, "score", None),
        "text": text,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = None
    yield


app = FastAPI(title="mxbai-reranker", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    status = "ready" if app.state.model is not None else "warming"
    return {"status": status, "model_id": MODEL_ID}


def _get_model() -> MxbaiRerankV2:
    model = app.state.model
    if model is not None:
        return model

    with _model_lock:
        model = app.state.model
        if model is None:
            model = MxbaiRerankV2(MODEL_ID)
            app.state.model = model
    return model


@app.post("/rerank")
def rerank(payload: RerankRequest) -> dict[str, Any]:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query must not be empty")

    texts = [text for text in payload.texts if text.strip()]
    if not texts:
        raise HTTPException(status_code=400, detail="texts must contain at least one non-empty item")

    kwargs: dict[str, Any] = {"query": query, "documents": texts}
    if payload.instruction is not None:
        kwargs["instruction"] = payload.instruction

    raw_results = _get_model().rank(**kwargs)
    results = [_to_public_result(item, texts, idx) for idx, item in enumerate(raw_results)]
    results.sort(key=lambda item: (item["score"] is not None, item["score"]), reverse=True)

    if payload.top_n is not None:
        results = results[: payload.top_n]

    for rank, item in enumerate(results, start=1):
        item["rank"] = rank

    return {"model_id": MODEL_ID, "results": results}
