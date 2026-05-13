"""Quick test: verify Anthropic API + model work."""
import sys, os
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

# Load .env
env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

from toolkit.llm_client import AnthropicProvider
import inspect

api_key = env["ANTHROPIC_API_KEY"]
model = env.get("PHOSPHENE_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

print(f"Model: {model}")
print(f"API key: {api_key[:20]}...")

provider = AnthropicProvider(api_key=api_key)
# Check available methods
methods = [m for m in dir(provider) if not m.startswith("_")]
print(f"Provider methods: {methods}")

# Use the correct method name
response = provider.call(
    messages=[{"role": "user", "content": "Say hello in exactly 5 words."}],
    model=model,
    max_tokens=50,
)
print(f"Response text: {response.text!r}")
print("API works!")
