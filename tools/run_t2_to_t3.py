"""One-shot T2→T3 distillation runner with logging.

Usage (on Pi):
    cd /mnt/passport/shared/phosphene
    ~/phosphene-venv/bin/python3 tools/run_t2_to_t3.py
"""
import sys, os
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

from pathlib import Path

# Load .env manually (no python-dotenv dependency)
env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from phosphene.memory_store import MemoryStore, MemoryStoreConfig
from phosphene.distillation.engine import DistillationEngine, DistillationConfig

vault_path = os.environ.get("PHOSPHENE_VAULT_PATH", "vault")
model = os.environ.get("PHOSPHENE_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

print(f"=== T2→T3 Distillation ===")
print(f"Vault: {vault_path}")
print(f"Model: {model}")
print()

ms = MemoryStore(MemoryStoreConfig(
    vault_path=vault_path,
    embedding_path=f"{vault_path}/.embeddings",
))

engine = DistillationEngine(ms)

# Build config - use the model from .env
from dataclasses import fields
config_kwargs = {}

# Try to import the LLM config types
try:
    from toolkit.llm_client import LLMConfig, ModelTier
    config_kwargs["llm_config"] = LLMConfig(
        provider="anthropic",
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        models={
            "default": model,
            "quality": model,
            "commodity": model,
        },
    )
    config_kwargs["reflection_tier"] = ModelTier.QUALITY
    config_kwargs["evolution_tier"] = ModelTier.QUALITY
except ImportError:
    print("WARNING: toolkit.llm_client not available, using default config")

try:
    from toolkit.embedding import EmbeddingConfig
    config_kwargs["embedding_config"] = EmbeddingConfig(
        model=os.environ.get("PHOSPHENE_EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"),
    )
except ImportError:
    print("WARNING: toolkit.embedding not available, using default config")

config = DistillationConfig(**config_kwargs)
print(f"Batch size: {config.t2_reflection_batch_size}")
print()

# Check gates first
gates = engine.check_gates(config)
print(f"Gates: t2_to_t3_ready={gates.t2_to_t3_ready}")
print()

# Run T2→T3
try:
    result = engine.distill_t2_to_t3(config)
    print()
    print(f"=== RESULT ===")
    print(f"Insights: {len(result.insights)}")
    print(f"Superseded/created: {len(result.superseded)}")
    for s in result.superseded:
        print(f"  {s.new_note_id}: {s.change_summary[:80]}")
    print(f"Unchanged: {len(result.unchanged_ids)}")
    print(f"Compression ratio: {result.compression_ratio:.3f}")
    print(f"Criteria adjustments: {len(result.criteria_adjustments)}")
except Exception as e:
    print(f"\nFAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
