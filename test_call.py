import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    base_url=os.getenv("NEBIUS_BASE_URL"),
    api_key=os.getenv("NEBIUS_API_KEY"),
)

# 1. Confirm which model IDs actually exist
ids = [m.id for m in client.models.list().data]
for key in ["MODEL_JUDGE", "MODEL_SOLVER", "MODEL_CHEAP"]:
    mid = os.getenv(key)
    print(f"{key}: {mid} -> {'FOUND' if mid in ids else 'NOT FOUND'}")

# 2. One real call per model
for key in ["MODEL_CHEAP", "MODEL_SOLVER", "MODEL_JUDGE"]:
    mid = os.getenv(key)
    try:
        r = client.chat.completions.create(
            model=mid,
            messages=[{"role": "user", "content": "Reply with exactly: ready"}],
            max_tokens=50,
        )
        print(key, "->", r.choices[0].message.content, "| tokens:", r.usage.total_tokens)
    except Exception as e:
        print(key, "FAILED:", e)