"""List available Anthropic models."""
import os, json, urllib.request

env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

req = urllib.request.Request(
    "https://api.anthropic.com/v1/models",
    headers={
        "anthropic-version": "2023-06-01",
        "X-Api-Key": env["ANTHROPIC_API_KEY"],
    },
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read())

for model in sorted(data.get("data", []), key=lambda m: m.get("id", "")):
    mid = model.get("id", "?")
    print(mid)
