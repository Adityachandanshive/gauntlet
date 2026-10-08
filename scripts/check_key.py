import os
from dotenv import load_dotenv
load_dotenv()
k = os.getenv("NEBIUS_API_KEY") or ""
print("length:", len(k))
print("starts/ends:", repr(k[:4]), repr(k[-4:]))
print("has whitespace:", any(c.isspace() for c in k))
print("has quotes:", '"' in k or "'" in k)
print("has < or >:", "<" in k or ">" in k)