"""Test the exact call path that distillation uses."""
import sys, os, json
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

# Build LLMConfig exactly as run.py does
from toolkit.llm_client import LLMConfig, Message, complete

api_key = env["ANTHROPIC_API_KEY"]
model = env.get("PHOSPHENE_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

config = LLMConfig(
    provider="anthropic",
    api_key=api_key,
    models={"default": model, "quality": model, "commodity": model},
)

# Build the exact messages that _build_cluster_summary_request builds
test_observations = [
    "Мы съездили в Yosemite, полазить по горам.",
    "I think a common thread for items here is art criticism.",
    "[context: user1] Something someone said [reply] My thoughtful response.",
]

payload = json.dumps({
    "task": "distill_tier1_cluster_summary",
    "instructions": "Synthesize these observations into one coherent pattern description. Return plain text.",
    "observations": test_observations,
    "note": "Showing 3 of 3 cluster members.",
}, sort_keys=True)

messages = [
    Message(role="system", content=(
        "You are a research assistant synthesizing personal journal entries. "
        "The content may be multilingual and include informal language. "
        "Always produce a synthesis — never return empty."
    )),
    Message(role="user", content=payload),
]

print(f"Model: {model}")
print(f"Messages: {len(messages)} ({messages[0].role}, {messages[1].role})")
print(f"User prompt length: {len(payload)} chars")

try:
    response = complete(messages=messages, config=config)
    print(f"\nSUCCESS via complete():")
    print(f"  content: {response.content[:300]}...")
    print(f"  tokens: input={response.token_usage.input_tokens}, output={response.token_usage.output_tokens}")
except Exception as e:
    print(f"\nFAILED via complete(): {type(e).__name__}: {e}")
