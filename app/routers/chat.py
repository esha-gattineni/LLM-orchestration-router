import uuid
import time

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest, ChatResponse, ModelChoice
from app.services.routing_engine import get_routing_engine
from app.services.llm_client import get_llm_client
from app.services.telemetry import get_telemetry
from app.services.metrics_store import get_metrics_store, RequestRecord

router = APIRouter()


@router.post("/completions", response_model=ChatResponse, summary="Route and complete a chat request")
async def chat_completions(request: ChatRequest):
    """
    Accepts a chat completion request, runs the routing algorithm to select
    between GPT-4 and Claude, then returns the completion with full routing
    metadata and usage statistics.
    """
    request_id = str(uuid.uuid4())
    telemetry = get_telemetry()
    metrics = get_metrics_store()

    # ---- 1. Routing decision (<200ms target) ----
    t_route_start = time.perf_counter()
    engine = get_routing_engine()
    messages_raw = [m.model_dump() for m in request.messages]

    routing = engine.route(
        messages=messages_raw,
        preferred_model=request.model,
        latency_budget_ms=request.latency_budget_ms,
    )
    routing_overhead_ms = (time.perf_counter() - t_route_start) * 1000

    telemetry.track_event(
        "RoutingDecision",
        {
            "request_id": request_id,
            "model_selected": routing.model_selected.value,
            "complexity_score": str(routing.complexity_score),
            "routing_overhead_ms": str(round(routing_overhead_ms, 2)),
            "reason": routing.reason,
        },
    )

    # ---- 2. LLM call with automatic fallback ----
    client = get_llm_client()
    error_occurred = False
    try:
        content, usage, actual_model = await client.complete_with_fallback(
            messages=messages_raw,
            primary_model=routing.model_selected,
            max_tokens=request.max_tokens,
        )
    except Exception as exc:
        error_occurred = True
        telemetry.track_exception(exc)
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}")

    # ---- 3. Record metrics ----
    metrics.record(
        RequestRecord(
            model=actual_model,
            latency_ms=usage.latency_ms,
            cost_usd=usage.cost_usd,
            tokens=usage.total_tokens,
            complexity_score=routing.complexity_score,
            error=error_occurred,
        )
    )

    telemetry.track_metric("llm.latency_ms", usage.latency_ms, {"model": actual_model.value})
    telemetry.track_metric("llm.cost_usd", usage.cost_usd, {"model": actual_model.value})
    telemetry.track_metric("llm.tokens", usage.total_tokens, {"model": actual_model.value})

    # If model fell back, patch the routing decision model for response clarity
    routing.model_selected = actual_model

    return ChatResponse(
        request_id=request_id,
        content=content,
        model_used=actual_model,
        routing=routing,
        usage=usage,
    )
