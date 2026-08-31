from fastapi import APIRouter, Query

from service import reviews_repo

router = APIRouter(prefix="/api/reviews")


@router.get("")
async def list_reviews(repo: str = Query(...), limit: int = Query(default=20, le=100)):
    return {"reviews": reviews_repo.get_review_history(repo, limit)}


@router.get("/stats")
async def review_stats(repo: str = Query(...)):
    return reviews_repo.get_false_positive_rate(repo)
