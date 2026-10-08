from dotenv import load_dotenv
load_dotenv()

from contree_sdk import ContreeSync

client = ContreeSync()
sandbox = client.images.use("python:3.12-slim")

# 1. Basic run
r = sandbox.run("python", args=["-c", "print('sum:', sum([3, 5, 8, 13]))"]).wait()
print("STDOUT:", r.stdout)

# 2. Is there a shell, and does the image have git?
r = sandbox.run("sh", args=["-c", "which git; python --version; pip --version"]).wait()
print("TOOLS:", r.stdout, r.stderr)

# 3. Is network access available (needed for git clone / pip install)?
r = sandbox.run("sh", args=["-c", "pip download --no-deps -d /tmp/x six 2>&1 | tail -2"]).wait()
print("NETWORK:", r.stdout, r.stderr)