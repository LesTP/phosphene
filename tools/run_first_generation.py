"""First generation test — minimal, bypasses full index rebuild.

Loads only T3 personality files, generates one output, saves to vault/outputs/,
sends to Telegram.

Usage (on Pi):
    cd /mnt/passport/shared/phosphene
    ~/phosphene-venv/bin/python3 -u tools/run_first_generation.py
"""
import sys, os, json
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

# Load .env
env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

vault_path = Path(os.environ.get("PHOSPHENE_VAULT_PATH", "vault"))
model = os.environ.get("PHOSPHENE_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
api_key = os.environ.get("ANTHROPIC_API_KEY", "")

print(f"=== First Generation ===")
print(f"Model: {model}")

# Step 1: Load T3 personality files directly (no full index rebuild)
t3_dir = vault_path / "tier3"
t3_files = sorted(t3_dir.glob("*.md")) if t3_dir.exists() else []
print(f"T3 personality files: {len(t3_files)}")

if not t3_files:
    print("ERROR: No T3 personality files. Run T2→T3 distillation first.")
    sys.exit(1)

# Parse T3 content
personality_context = []
for f in t3_files:
    raw = f.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    if len(parts) >= 3:
        body = parts[2].strip()
        # Extract title from frontmatter
        title = f.stem
        for line in parts[1].splitlines():
            if line.strip().startswith("title:"):
                title = line.split(":", 1)[1].strip().strip("'\"")
                break
        personality_context.append({"title": title, "content": body})
        print(f"  {title} ({len(body)} chars)")

# Step 2: Build generation prompt
personality_text = "\n\n---\n\n".join(
    f"## {p['title']}\n\n{p['content']}" for p in personality_context
)

generation_prompt = f"""You are a personality that has developed from a personal writing corpus.
Your personality files describe your core orientations, tensions, and preoccupations.
Generate an original observation, essay fragment, or question that emerges naturally
from these personality dimensions. Be specific, not generic. Write as yourself, not
about yourself. 300-600 words.

=== PERSONALITY FILES ===

{personality_text}"""

print(f"\nPrompt: {len(generation_prompt)} chars")

# Step 3: Call LLM
print(f"Generating...", end="", flush=True)
import anthropic
client = anthropic.Anthropic(api_key=api_key)
response = client.messages.create(
    model=model,
    messages=[{"role": "user", "content": generation_prompt}],
    max_tokens=2000,
    temperature=0.8,
)

if response.stop_reason != "end_turn" or not response.content:
    print(f" FAILED — stop_reason={response.stop_reason}")
    sys.exit(1)

generated = response.content[0].text
print(f" OK — {len(generated)} chars")
print()
print("=" * 60)
print(generated)
print("=" * 60)

# Step 4: Save to vault/outputs/
outputs_dir = vault_path / "outputs"
outputs_dir.mkdir(parents=True, exist_ok=True)

now = datetime.now(timezone.utc)
timestamp = now.strftime("%Y%m%dT%H%M%S")
slug = generated[:60].lower()
slug = "".join(c if c.isalnum() or c == " " else "" for c in slug).strip().replace(" ", "-")[:40]
filename = f"{slug}-{timestamp}.md"

frontmatter = {
    "output_mode": "prompted",
    "intent_tag": "first_generation",
    "model": model,
    "personality_files": [p["title"] for p in personality_context],
    "created_at": now.isoformat(),
    "delivery_success": False,
}

output_path = outputs_dir / filename
output_content = f"---\n"
for k, v in frontmatter.items():
    if isinstance(v, list):
        output_content += f"{k}:\n" + "".join(f"- {item}\n" for item in v)
    else:
        output_content += f"{k}: {v}\n"
output_content += f"---\n{generated}\n"
output_path.write_text(output_content, encoding="utf-8")
print(f"\nSaved: {output_path}")

# Step 5: Send to Telegram
tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "")

if tg_token and tg_chat:
    import urllib.request, urllib.parse
    # Truncate to 4096 chars (Telegram limit)
    tg_text = generated[:4096]
    data = urllib.parse.urlencode({"chat_id": tg_chat, "text": tg_text}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{tg_token}/sendMessage", data=data)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        if result.get("ok"):
            print(f"Telegram: delivered (message_id={result['result']['message_id']})")
            # Update delivery_success
            output_content = output_content.replace("delivery_success: False", "delivery_success: True")
            output_path.write_text(output_content, encoding="utf-8")
        else:
            print(f"Telegram: FAILED — {result}")
    except Exception as e:
        print(f"Telegram: FAILED — {type(e).__name__}: {e}")
else:
    print("Telegram: skipped (no token/chat_id)")

print("\nDone.")
