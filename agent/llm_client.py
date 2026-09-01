import os

from langsmith.wrappers import wrap_openai
from openai import AsyncOpenAI, OpenAI

# Set to Ollama's OpenAI-compatible endpoint (e.g. http://localhost:11434/v1)
# to route every node through a local model instead of OpenAI, at zero API
# cost -- useful for testing the pipeline itself. eval/judge.py deliberately
# does not read this: the judge that scores review quality needs to stay on
# a fixed, trusted model so scores are comparable across runs regardless of
# which model produced the review being judged.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")


def using_ollama() -> bool:
    return bool(OLLAMA_BASE_URL)


def resolve_model(openai_model: str) -> str:
    return OLLAMA_MODEL if using_ollama() else openai_model


def tracing_enabled() -> bool:
    return (
        os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"
        and bool(os.environ.get("LANGCHAIN_API_KEY"))
    )


def _client_kwargs() -> dict:
    if using_ollama():
        # Ollama ignores the key but the OpenAI SDK requires a non-empty string.
        return {"base_url": OLLAMA_BASE_URL, "api_key": os.environ.get("OPENAI_API_KEY") or "ollama"}
    return {"api_key": os.environ["OPENAI_API_KEY"]}


def get_openai_client() -> OpenAI:
    client = OpenAI(**_client_kwargs())
    return wrap_openai(client) if tracing_enabled() else client


def get_async_openai_client() -> AsyncOpenAI:
    client = AsyncOpenAI(**_client_kwargs())
    return wrap_openai(client) if tracing_enabled() else client
