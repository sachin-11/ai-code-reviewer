from fastapi import APIRouter, Query

from agent import github_client
from service import reviews_repo

router = APIRouter(prefix="/api/reviews")


@router.get("/repos")
async def list_repos():
    # Merge two sources: Postgres review history (repos that have actually
    # been reviewed at least once) and, when GitHub App auth is configured,
    # every repo the App is currently installed on -- so a freshly-installed
    # repo with zero reviews yet still shows up to pick from.
    reviewed = reviews_repo.get_known_repos()
    installed = github_client.list_installed_repos()
    return {"repos": sorted(set(reviewed) | set(installed))}


@router.get("")
async def list_reviews(repo: str = Query(...), limit: int = Query(default=20, le=100)):
    return {"reviews": reviews_repo.get_review_history(repo, limit)}


@router.get("/stats")
async def review_stats(repo: str = Query(...)):
    return reviews_repo.get_false_positive_rate(repo)


@router.get("/cost")
async def review_cost(repo: str = Query(...)):
    return reviews_repo.get_cost_summary(repo)


@router.get("/eval")
async def review_eval(repo: str = Query(...)):
    return reviews_repo.get_eval_quality_summary(repo)


@router.get("/latency")
async def review_latency(repo: str = Query(...)):
    return reviews_repo.get_latency_summary(repo)
