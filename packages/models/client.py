import os

from dotenv import load_dotenv
from langsmith.wrappers import wrap_openai
from openai import OpenAI

load_dotenv()
_client = wrap_openai(
    OpenAI(base_url=os.getenv("NEBIUS_BASE_URL"), api_key=os.getenv("NEBIUS_API_KEY"))
)


def chat(model_env: str, messages: list, max_tokens: int = 4000, temperature: float = 0.7):
    r = _client.chat.completions.create(
        model=os.getenv(model_env), messages=messages,
        max_tokens=max_tokens, temperature=temperature,
        langsmith_extra={"metadata": {"model_env": model_env}},
    )
    return (r.choices[0].message.content or ""), r.usage