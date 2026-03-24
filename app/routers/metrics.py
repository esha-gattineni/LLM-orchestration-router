from fastapi import APIRouter
from app.models.schemas import MetricsSummary
from app.services.metrics_store import get_metrics_store

router = APIRouter()


@router.get("/summary", response_model=MetricsSummary, summary="Routing and cost metrics summary")
async def metrics_summary():
    """Returns aggregated routing stats: model split, latency percentiles, cost savings."""
    store = get_metrics_store()
    return store.summary()
