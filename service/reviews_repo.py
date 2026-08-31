from typing import Optional

from psycopg.types.json import Jsonb

from service.db import get_connection


def record_review(
    repo_full_name: str,
    pr_number: int,
    head_sha: str,
    base_sha: str,
    issues: list[dict],
    verified_patch_count: int,
    fix_pr_url: Optional[str],
    summary: Optional[str],
    cost_usd: float = 0.0,
    trace_url: Optional[str] = None,
    latency_seconds: Optional[float] = None,
    iteration_count: Optional[int] = None,
    hit_max_iterations: bool = False,
    node_latencies: Optional[dict] = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO reviews
                    (repo_full_name, pr_number, head_sha, base_sha, issue_count,
                     verified_patch_count, fix_pr_url, summary, cost_usd, trace_url,
                     latency_seconds, iteration_count, hit_max_iterations, node_latencies)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    repo_full_name,
                    pr_number,
                    head_sha,
                    base_sha,
                    len(issues),
                    verified_patch_count,
                    fix_pr_url,
                    summary,
                    cost_usd,
                    trace_url,
                    latency_seconds,
                    iteration_count,
                    hit_max_iterations,
                    Jsonb(node_latencies) if node_latencies else None,
                ),
            )
            review_id = cur.fetchone()["id"]

            for issue in issues:
                cur.execute(
                    """
                    INSERT INTO review_issues
                        (review_id, fingerprint, file, category, severity, title, confidence, fixable)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        review_id,
                        issue["fingerprint"],
                        issue["file"],
                        issue["category"],
                        issue["severity"],
                        issue["title"],
                        issue["confidence"],
                        issue["fixable"],
                    ),
                )
        conn.commit()

    return review_id


def get_known_repos() -> list[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT repo_full_name FROM reviews ORDER BY repo_full_name")
            return [row["repo_full_name"] for row in cur.fetchall()]


def get_review_history(repo_full_name: str, limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, repo_full_name, pr_number, head_sha, base_sha, issue_count,
                       verified_patch_count, fix_pr_url, summary, cost_usd, trace_url,
                       latency_seconds, iteration_count, hit_max_iterations, node_latencies,
                       created_at
                FROM reviews
                WHERE repo_full_name = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (repo_full_name, limit),
            )
            reviews = cur.fetchall()

            if not reviews:
                return []

            review_ids = [r["id"] for r in reviews]
            cur.execute(
                """
                SELECT review_id, severity, COUNT(*) AS count
                FROM review_issues
                WHERE review_id = ANY(%s)
                GROUP BY review_id, severity
                """,
                (review_ids,),
            )
            severity_rows = cur.fetchall()

    severity_by_review: dict[int, dict[str, int]] = {}
    for row in severity_rows:
        severity_by_review.setdefault(row["review_id"], {})[row["severity"]] = row["count"]

    for review in reviews:
        review["severity_breakdown"] = severity_by_review.get(review["id"], {})

    return reviews


def get_false_positive_rate(repo_full_name: str) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE dismissed) AS dismissed
                FROM review_issues ri
                JOIN reviews r ON r.id = ri.review_id
                WHERE r.repo_full_name = %s
                """,
                (repo_full_name,),
            )
            row = cur.fetchone()

    total = row["total"] or 0
    dismissed = row["dismissed"] or 0
    rate = dismissed / total if total else 0.0

    return {"total": total, "dismissed": dismissed, "false_positive_rate": rate}


def record_eval_sample(review_id: int, issues_judged: int, issues_valid: int, details: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO eval_samples (review_id, issues_judged, issues_valid, details)
            VALUES (%s, %s, %s, %s)
            """,
            (review_id, issues_judged, issues_valid, Jsonb(details)),
        )
        conn.commit()


def get_eval_quality_summary(repo_full_name: str) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS sample_count,
                       COALESCE(SUM(es.issues_judged), 0) AS total_judged,
                       COALESCE(SUM(es.issues_valid), 0) AS total_valid
                FROM eval_samples es
                JOIN reviews r ON r.id = es.review_id
                WHERE r.repo_full_name = %s
                """,
                (repo_full_name,),
            )
            row = cur.fetchone()

    sample_count = row["sample_count"] or 0
    total_judged = row["total_judged"] or 0
    total_valid = row["total_valid"] or 0
    valid_rate = total_valid / total_judged if total_judged else None

    return {"sample_count": sample_count, "total_judged": total_judged, "valid_rate": valid_rate}


def get_latency_summary(repo_full_name: str) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS review_count,
                       AVG(latency_seconds) AS avg_latency_seconds,
                       MAX(latency_seconds) AS max_latency_seconds,
                       AVG(iteration_count) AS avg_iteration_count,
                       MAX(iteration_count) AS max_iteration_count,
                       COUNT(*) FILTER (WHERE hit_max_iterations) AS hit_max_iterations_count
                FROM reviews
                WHERE repo_full_name = %s
                """,
                (repo_full_name,),
            )
            row = cur.fetchone()

    review_count = row["review_count"] or 0
    hit_max_count = row["hit_max_iterations_count"] or 0

    return {
        "review_count": review_count,
        "avg_latency_seconds": float(row["avg_latency_seconds"]) if row["avg_latency_seconds"] is not None else None,
        "max_latency_seconds": float(row["max_latency_seconds"]) if row["max_latency_seconds"] is not None else None,
        "avg_iteration_count": float(row["avg_iteration_count"]) if row["avg_iteration_count"] is not None else None,
        "max_iteration_count": row["max_iteration_count"],
        "hit_max_iterations_count": hit_max_count,
        "hit_max_iterations_rate": (hit_max_count / review_count) if review_count else None,
    }


def get_cost_summary(repo_full_name: str) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS review_count, COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
                       COALESCE(AVG(cost_usd), 0) AS avg_cost_usd
                FROM reviews
                WHERE repo_full_name = %s
                """,
                (repo_full_name,),
            )
            row = cur.fetchone()

    return {
        "review_count": row["review_count"] or 0,
        "total_cost_usd": float(row["total_cost_usd"]),
        "avg_cost_per_pr_usd": float(row["avg_cost_usd"]),
    }
