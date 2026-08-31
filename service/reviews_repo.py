from typing import Optional

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
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO reviews
                    (repo_full_name, pr_number, head_sha, base_sha, issue_count,
                     verified_patch_count, fix_pr_url, summary, cost_usd, trace_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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


def get_review_history(repo_full_name: str, limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, repo_full_name, pr_number, head_sha, base_sha, issue_count,
                       verified_patch_count, fix_pr_url, summary, cost_usd, trace_url, created_at
                FROM reviews
                WHERE repo_full_name = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (repo_full_name, limit),
            )
            return cur.fetchall()


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
