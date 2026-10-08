from dotenv import load_dotenv
import os

load_dotenv()
for k in ["NEBIUS_BASE_URL", "MODEL_JUDGE", "MODEL_SOLVER", "MODEL_CHEAP"]:
    print(k, "=", os.getenv(k))
print("API key set:", bool(os.getenv("NEBIUS_API_KEY")))