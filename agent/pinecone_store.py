import logging
import os
from typing import Optional

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
DEFAULT_INDEX_NAME = "ai-review-memory"
TOP_K = 5


def is_enabled() -> bool:
    return bool(os.environ.get("PINECONE_API_KEY"))


def _get_client() -> Pinecone:
    return Pinecone(api_key=os.environ["PINECONE_API_KEY"])


def _get_index_name() -> str:
    return os.environ.get("PINECONE_INDEX_NAME", DEFAULT_INDEX_NAME)


def ensure_index() -> None:
    if not is_enabled():
        return

    try:
        pc = _get_client()
        index_name = _get_index_name()
        if pc.has_index(index_name):
            return

        pc.create_index(
            name=index_name,
            dimension=EMBEDDING_DIMENSIONS,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    except Exception as exc:
        logger.error("Failed to ensure Pinecone index exists: %s", exc)


def _embed(text: str) -> Optional[list[float]]:
    try:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        return response.data[0].embedding
    except Exception as exc:
        logger.error("Failed to embed text: %s", exc)
        return None


def upsert_issue(
    fingerprint: str,
    file: str,
    category: str,
    title: str,
    description: str,
    outcome: str,
    repo_full_name: str,
) -> bool:
    if not is_enabled():
        return False

    vector = _embed(f"{title}\n{description}")
    if vector is None:
        return False

    try:
        pc = _get_client()
        index = pc.Index(_get_index_name())
        index.upsert(
            vectors=[
                {
                    "id": fingerprint,
                    "values": vector,
                    "metadata": {
                        "file": file,
                        "category": category,
                        "title": title,
                        "description": description[:500],
                        "outcome": outcome,
                        "repo_full_name": repo_full_name,
                    },
                }
            ]
        )
        return True
    except Exception as exc:
        logger.error("Failed to upsert issue %s into Pinecone: %s", fingerprint, exc)
        return False


def update_outcome(fingerprint: str, outcome: str) -> bool:
    """Best-effort: re-fetches the stored metadata and re-upserts with a new
    outcome. Silently no-ops if the vector isn't found (e.g. it predates
    this feature, or Pinecone is disabled)."""
    if not is_enabled():
        return False

    try:
        pc = _get_client()
        index = pc.Index(_get_index_name())
        fetched = index.fetch(ids=[fingerprint])
        vectors = fetched.get("vectors", {}) if hasattr(fetched, "get") else {}
        record = vectors.get(fingerprint)
        if record is None:
            return False

        metadata = dict(record.get("metadata", {}))
        metadata["outcome"] = outcome

        index.upsert(vectors=[{"id": fingerprint, "values": record["values"], "metadata": metadata}])
        return True
    except Exception as exc:
        logger.error("Failed to update outcome for %s in Pinecone: %s", fingerprint, exc)
        return False


def search_similar_issues(query: str, repo_full_name: Optional[str] = None, top_k: int = TOP_K) -> list[dict]:
    if not is_enabled():
        return []

    vector = _embed(query)
    if vector is None:
        return []

    try:
        pc = _get_client()
        index = pc.Index(_get_index_name())
        filter_ = {"repo_full_name": repo_full_name} if repo_full_name else None

        response = index.query(vector=vector, top_k=top_k, include_metadata=True, filter=filter_)

        results = []
        for match in response.get("matches", []):
            metadata = match.get("metadata", {}) or {}
            results.append(
                {
                    "score": match.get("score"),
                    "title": metadata.get("title"),
                    "file": metadata.get("file"),
                    "category": metadata.get("category"),
                    "outcome": metadata.get("outcome"),
                }
            )
        return results
    except Exception as exc:
        logger.error("Failed to search Pinecone: %s", exc)
        return []
