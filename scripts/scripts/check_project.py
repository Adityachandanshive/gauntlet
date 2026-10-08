from dotenv import load_dotenv; import os
load_dotenv()
p = os.getenv("NEBIUS_PROJECT_ID")
print("project id set:", bool(p), "| prefix:", (p or "")[:8], "| length:", len(p or ""))