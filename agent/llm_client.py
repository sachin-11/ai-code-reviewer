import os

from langsmith.wrappers import wrap_openai
from openai import AsyncOpenAI, OpenAI


def tracing_enabled() -> bool:
    return (
        os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"
        and bool(os.environ.get("LANGCHAIN_API_KEY"))
    )


def get_openai_client() -> OpenAI:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return wrap_openai(client) if tracing_enabled() else client


def get_async_openai_client() -> AsyncOpenAI:
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return wrap_openai(client) if tracing_enabled() else client
