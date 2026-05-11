"""Bootstrap entry point for the Phosphene MVP loop."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# Add source paths for phosphene and toolkit
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "src"))
_TOOLKIT_PATH = os.environ.get("TOOLKIT_SRC")
if not _TOOLKIT_PATH:
    # Try common locations
    for candidate in [
        _HERE.parent / "toolkit" / "src",  # sibling directory
        Path("/mnt/passport/shared/toolkit/src"),  # Pi shared drive
        Path(r"c:\Users\myeluashvili\claude-code-workspace\projects\toolkit\src"),  # Windows
    ]:
        if candidate.is_dir():
            _TOOLKIT_PATH = str(candidate)
            break
if _TOOLKIT_PATH:
    sys.path.insert(0, _TOOLKIT_PATH)

from phosphene.attention_filter import AttentionFilter, AttentionFilterConfig
from phosphene.distillation import DistillationConfig, DistillationEngine
from phosphene.gateway import Gateway, GatewayConfig, PlatformConfig
from phosphene.generator import GenerationPrompt, Generator, GeneratorConfig, RouterConfig
from phosphene.memory_store import MemoryStore, MemoryStoreConfig
from phosphene.orchestrator import (
    MVPOrchestrator,
    MVPOrchestratorConfig,
    ModuleRefs,
    ScheduleEntry,
)
from phosphene.source_ingestion import AdapterConfig, IngestionConfig, SourceIngestion


DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_VAULT_PATH = Path("./vault")
DEFAULT_LOG_PATH = Path("./logs/mvp_orchestrator.jsonl")
DEFAULT_MARKER_PATH = DEFAULT_VAULT_PATH / ".source_markers.json"


def main() -> int:
    args = _parse_args()
    env = _load_env(Path(args.env_file))

    if args.seed_direct:
        return _seed_direct(env)

    if args.seed_chronological:
        return _seed_chronological(env)

    orchestrator = build_orchestrator(env)

    if args.seed_only:
        return _print_result(orchestrator.trigger("ingestion"))

    if args.once:
        exit_code = 0
        for task_type in ("ingestion", "distillation", "generation", "decay"):
            result = orchestrator.trigger(task_type)
            _print_result(result)
            if not result.success:
                exit_code = 1
        return exit_code

    orchestrator.start()
    return 0


def _seed_direct(env: dict[str, str]) -> int:
    """Bulk-import corpus into Memory Store, bypassing the attention filter.

    Polls all configured corpus adapters, embeds each content item locally,
    and writes T1 notes directly. No LLM calls — embedding is the only compute.
    """
    from toolkit.embedding import embed, EmbeddingConfig

    vault_path = Path(env.get("PHOSPHENE_VAULT_PATH", str(DEFAULT_VAULT_PATH)))
    memory_store = MemoryStore(
        MemoryStoreConfig(
            vault_path=str(vault_path),
            embedding_path=str(vault_path / ".embeddings"),
        )
    )
    embedding_config = _make_embedding_config(env)
    ingestion_config = _make_ingestion_config(env, vault_path)
    source_ingestion = SourceIngestion(ingestion_config)

    # Poll all adapters
    print("Polling corpus adapters...")
    ingestion_results = source_ingestion.poll()
    items = []
    total_errors = 0
    for result in ingestion_results:
        items.extend(result.items)
        total_errors += len(result.errors)
        if result.items:
            print(f"  {result.adapter_label}: {len(result.items)} items")
        if result.errors:
            print(f"  {result.adapter_label}: {len(result.errors)} errors")
    print(f"  Total: {len(items)} items, {total_errors} errors")

    if not items:
        print("No items to import.")
        return 0

    # Filter out very short items
    MIN_WORDS = 10
    items = [item for item in items if len(item.content.split()) >= MIN_WORDS]
    print(f"  After filtering (<{MIN_WORDS} words): {len(items)} items")

    # Clean content: strip numbered track listing lines and share links
    import re
    _TRACK_LINE_RE = re.compile(r"^\s*\d+[\.\)]\s+.{3,80}$", re.MULTILINE)
    _SHARE_LINE_RE = re.compile(
        r"^.*(?:depositfiles|mediafire|megaupload|sharebee|rapidshare|hotfile)\S*.*$",
        re.MULTILINE | re.IGNORECASE,
    )
    _BITRATE_LINE_RE = re.compile(
        r"^.*\d+\s*(?:kbps|mb|kbit).*$", re.MULTILINE | re.IGNORECASE,
    )

    def _clean_content(text: str) -> str:
        text = _TRACK_LINE_RE.sub("", text)
        text = _SHARE_LINE_RE.sub("", text)
        text = _BITRATE_LINE_RE.sub("", text)
        # Collapse leftover blank lines
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        return text.strip()

    for item in items:
        item.content = _clean_content(item.content)

    # Re-filter after cleaning (some items may now be too short)
    before = len(items)
    items = [item for item in items if len(item.content.split()) >= MIN_WORDS]
    if len(items) < before:
        print(f"  Cleaned and re-filtered: {before - len(items)} items removed, {len(items)} remain")

    # Embed in batches
    print(f"Embedding {len(items)} items with {embedding_config.model}...")
    texts = [item.content for item in items]
    result = embed(texts, embedding_config)
    print(f"  Embedded into {result.dimension}-dim vectors")

    # Store as T1 notes
    print("Writing T1 notes to vault...")
    from phosphene.memory_store.types import NoteInput
    stored = 0
    for i, item in enumerate(items):
        title = item.title or item.content[:60].replace("\n", " ")
        note = NoteInput(
            tier=1,
            content=item.content,
            title=title,
            importance=0.5,
            source=item.source,
            embedding=result.vectors[i],
            tags=[],
        )
        try:
            memory_store.store_note(note)
            stored += 1
        except Exception as exc:
            print(f"  Error storing note {i}: {exc}")

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(items)} stored...")

    print(f"\nDone. {stored} T1 notes written to {vault_path}")
    return 0


def _seed_chronological(env: dict[str, str]) -> int:
    """Chronological seed: sort by date, feed in yearly batches, distill between.

    Items without timestamps come in last. Each batch is embedded and stored
    as T1, then distillation runs (T1→T2) before the next batch. This lets
    early writing shape the initial personality and later writing build on it.
    """
    from collections import defaultdict
    from toolkit.embedding import embed, EmbeddingConfig

    vault_path = Path(env.get("PHOSPHENE_VAULT_PATH", str(DEFAULT_VAULT_PATH)))
    memory_store = MemoryStore(
        MemoryStoreConfig(
            vault_path=str(vault_path),
            embedding_path=str(vault_path / ".embeddings"),
        )
    )
    embedding_config = _make_embedding_config(env)
    ingestion_config = _make_ingestion_config(env, vault_path)
    source_ingestion = SourceIngestion(ingestion_config)

    # Poll all adapters
    print("Polling corpus adapters...")
    ingestion_results = source_ingestion.poll()
    items = []
    for result in ingestion_results:
        items.extend(result.items)
        if result.items:
            print(f"  {result.adapter_label}: {len(result.items)} items")
    print(f"  Total: {len(items)} items")

    if not items:
        print("No items to import.")
        return 0

    # Filter and clean (same as _seed_direct)
    import re
    MIN_WORDS = 10
    items = [item for item in items if len(item.content.split()) >= MIN_WORDS]

    _TRACK_LINE_RE = re.compile(r"^\s*\d+[\.\)]\s+.{3,80}$", re.MULTILINE)
    _SHARE_LINE_RE = re.compile(
        r"^.*(?:depositfiles|mediafire|megaupload|sharebee|rapidshare|hotfile)\S*.*$",
        re.MULTILINE | re.IGNORECASE,
    )
    _BITRATE_LINE_RE = re.compile(
        r"^.*\d+\s*(?:kbps|mb|kbit).*$", re.MULTILINE | re.IGNORECASE,
    )

    def _clean(text):
        text = _TRACK_LINE_RE.sub("", text)
        text = _SHARE_LINE_RE.sub("", text)
        text = _BITRATE_LINE_RE.sub("", text)
        return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()

    for item in items:
        item.content = _clean(item.content)
    items = [item for item in items if len(item.content.split()) >= MIN_WORDS]
    print(f"  After filtering/cleaning: {len(items)} items")

    # Group by year (items without real timestamps go to year 9999)
    from datetime import datetime, timezone
    batches = defaultdict(list)
    for item in items:
        ts = item.timestamp
        # Treat "today" timestamps as no-timestamp (seed-time artifacts)
        if ts and ts.year < 2026:
            batches[ts.year].append(item)
        else:
            batches[9999].append(item)

    years = sorted(batches.keys())
    print(f"\nChronological batches: {len(years)}")
    for year in years:
        label = "no-timestamp" if year == 9999 else str(year)
        print(f"  {label}: {len(batches[year])} items")

    # Process each batch: embed → store → distill
    from phosphene.memory_store.types import NoteInput

    # Set up distillation engine for between-batch cycles
    llm_config = _make_llm_config(env)
    distillation_engine = None
    try:
        from phosphene.distillation import DistillationEngine, DistillationConfig
        distillation_engine = DistillationEngine(memory_store)
    except Exception as exc:
        print(f"  Warning: distillation unavailable ({exc}) — will seed without distillation")

    total_stored = 0
    for batch_idx, year in enumerate(years):
        batch_items = batches[year]
        label = "no-timestamp" if year == 9999 else str(year)
        print(f"\n{'='*60}")
        print(f"Batch {batch_idx + 1}/{len(years)}: {label} ({len(batch_items)} items)")
        print(f"{'='*60}")

        # Embed
        texts = [item.content for item in batch_items]
        emb = embed(texts, embedding_config)

        # Store
        stored = 0
        for i, item in enumerate(batch_items):
            title = item.title or item.content[:60].replace("\n", " ")
            note = NoteInput(
                tier=1,
                content=item.content,
                title=title,
                importance=0.5,
                source=item.source,
                embedding=emb.vectors[i],
                tags=[],
            )
            try:
                memory_store.store_note(note)
                stored += 1
            except Exception as exc:
                print(f"  Error storing note {i}: {exc}")
        total_stored += stored
        print(f"  Stored {stored} T1 notes (total: {total_stored})")

        # Run distillation between batches (skip after last batch — let --once handle it)
        if distillation_engine and batch_idx < len(years) - 1:
            print("  Running distillation...")
            try:
                distill_config = DistillationConfig(
                    llm_config=llm_config,
                    embedding_config=embedding_config,
                )
                gates = distillation_engine.check_gates(distill_config)
                if gates.t1_to_t2_ready:
                    result = distillation_engine.distill_t1_to_t2(distill_config)
                    print(f"  T1→T2: {len(result.clusters_created)} clusters created")
                else:
                    print(f"  T1→T2 gates not met yet")
            except Exception as exc:
                print(f"  Distillation error: {exc}")

    print(f"\n{'='*60}")
    print(f"Chronological seed complete. {total_stored} T1 notes across {len(years)} batches.")
    print(f"Run 'python run.py --once' for final distillation + first generation.")
    return 0


def build_orchestrator(env: dict[str, str]) -> MVPOrchestrator:
    """Construct the real MVP module graph from environment-backed config."""

    _require_env(env, "TELEGRAM_BOT_TOKEN")
    _require_env(env, "TELEGRAM_CHAT_ID")
    _require_env(env, "ANTHROPIC_API_KEY")

    vault_path = Path(env.get("PHOSPHENE_VAULT_PATH", DEFAULT_VAULT_PATH))
    memory_store = MemoryStore(
        MemoryStoreConfig(
            vault_path=str(vault_path),
            embedding_path=str(vault_path / ".embeddings"),
        )
    )
    llm_config = _make_llm_config(env)
    embedding_config = _make_embedding_config(env)

    attention_filter = AttentionFilter(memory_store)
    source_ingestion = SourceIngestion(_make_ingestion_config(env, vault_path))
    distillation_engine = DistillationEngine(memory_store)
    generator = Generator(memory_store)
    gateway = Gateway(
        _make_gateway_config(env),
        on_message=lambda _message: None,
        on_feedback=lambda _signal: None,
    )

    attention_filter_config = AttentionFilterConfig(
        llm_config=llm_config,
        embedding_config=embedding_config,
    )
    distillation_config = DistillationConfig(
        llm_config=llm_config,
        embedding_config=embedding_config,
        min_time_between_runs=timedelta(hours=24),
        min_tier1_volume=int(env.get("PHOSPHENE_MIN_TIER1_VOLUME", "20")),
    )
    generator_config = GeneratorConfig(llm_config=llm_config)
    router_config = RouterConfig(
        intent_routing={
            "internal_note": "log",
            "log_surfacing": "telegram",
            "subscription_proposal": "telegram",
            "response": "telegram",
        }
    )

    modules = ModuleRefs(
        memory_store=memory_store,
        attention_filter=attention_filter,
        source_ingestion=source_ingestion,
        distillation_engine=distillation_engine,
        generator=generator,
        gateway=gateway,
    )
    config = MVPOrchestratorConfig(
        schedule=[
            ScheduleEntry("ingestion", "0 */6 * * *"),
            ScheduleEntry("distillation", "0 3 * * *"),
            ScheduleEntry("generation", "0 */12 * * *"),
            ScheduleEntry("decay", "30 3 * * *"),
        ],
        generation_prompt=GenerationPrompt(
            topic=env.get("PHOSPHENE_GENERATION_TOPIC") or None
        ),
        attention_filter_config=attention_filter_config,
        distillation_config=distillation_config,
        generator_config=generator_config,
        router_config=router_config,
        log_path=Path(env.get("PHOSPHENE_LOG_PATH", DEFAULT_LOG_PATH)),
    )
    return MVPOrchestrator(modules, config)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Phosphene MVP orchestrator.")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the dotenv file containing secrets and runtime overrides.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--seed-direct",
        action="store_true",
        help="Bulk-import corpus directly into Memory Store. No LLM calls, no attention filter. Uses embeddings only (local, free).",
    )
    mode.add_argument(
        "--seed-chronological",
        action="store_true",
        help="Chronological seed: sort corpus by date, feed in yearly batches with distillation between each. No-timestamp items come last. Costs ~$5-10 API for distillation rounds.",
    )
    mode.add_argument(
        "--seed-only",
        action="store_true",
        help="Run one ingestion activation via the full pipeline (attention filter + LLM). WARNING: expensive for large corpora.",
    )
    mode.add_argument(
        "--once",
        action="store_true",
        help="Run one ingestion, distillation, generation, and decay cycle.",
    )
    return parser.parse_args()


def _load_env(path: Path) -> dict[str, str]:
    env = dict(os.environ)
    if not path.exists():
        return env

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env.setdefault(key.strip(), _strip_env_quotes(value.strip()))
    return env


def _strip_env_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _require_env(env: dict[str, str], key: str) -> str:
    value = env.get(key)
    if not value:
        raise SystemExit(f"Missing required environment variable: {key}")
    return value


def _make_llm_config(env: dict[str, str]) -> object:
    api_key = _require_env(env, "ANTHROPIC_API_KEY")
    model = env.get("PHOSPHENE_ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    try:
        from toolkit.llm_client import LLMConfig
    except ImportError:
        return SimpleNamespace(
            provider="anthropic",
            api_key=api_key,
            models={
                "default": model,
                "quality": model,
                "commodity": model,
            },
        )

    return LLMConfig(
        provider="anthropic",
        api_key=api_key,
        models={
            "default": model,
            "quality": model,
            "commodity": model,
        },
    )


def _make_embedding_config(env: dict[str, str]) -> object:
    model = env.get("PHOSPHENE_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    try:
        from toolkit.embedding import EmbeddingConfig
    except ImportError:
        return SimpleNamespace(model=model)

    return EmbeddingConfig(model=model)


def _make_ingestion_config(env: dict[str, str], vault_path: Path) -> IngestionConfig:
    marker_path = Path(env.get("PHOSPHENE_MARKER_PATH", DEFAULT_MARKER_PATH))
    params_common = {"marker_store_path": str(marker_path)}

    adapters = [
        AdapterConfig(
            adapter_type="corpus_livejournal",
            source_label="corpus_livejournal",
            params={
                **params_common,
                "archive_path": env.get("PHOSPHENE_LJ_ARCHIVE_PATH", "seed/LJ Backup/ljsm/lestp"),
                "format": "ljsm",
            },
        ),
        AdapterConfig(
            adapter_type="corpus_blogspot",
            source_label="corpus_blogspot_brassmonkeyonmyback",
            params={
                **params_common,
                "archive_path": env.get(
                    "PHOSPHENE_BLOGSPOT_BRASSMONKEY_PATH",
                    "seed/brassmonkeyonmyback_feed.atom",
                ),
            },
        ),
        AdapterConfig(
            adapter_type="corpus_blogspot",
            source_label="corpus_blogspot_whatsinmyipod",
            params={
                **params_common,
                "archive_path": env.get(
                    "PHOSPHENE_BLOGSPOT_WHATSINMYIPOD_PATH",
                    "seed/whatsinmyipod_feed.atom",
                ),
            },
        ),
        AdapterConfig(
            adapter_type="corpus_text",
            source_label="corpus_text",
            params={
                **params_common,
                "archive_path": env.get("PHOSPHENE_TEXT_ARCHIVE_PATH", "seed"),
            },
        ),
        AdapterConfig(
            adapter_type="corpus_facebook",
            source_label="corpus_facebook",
            params={
                **params_common,
                "archive_path": env.get(
                    "PHOSPHENE_FACEBOOK_ARCHIVE_PATH",
                    "seed/your_posts__check_ins__photos_and_videos_1.html",
                ),
            },
        ),
    ]
    vault_path.mkdir(parents=True, exist_ok=True)
    return IngestionConfig(adapters=adapters)


def _make_gateway_config(env: dict[str, str]) -> GatewayConfig:
    return GatewayConfig(
        platforms=[
            PlatformConfig(
                name="telegram",
                adapter_type="telegram",
                credentials={"bot_token": _require_env(env, "TELEGRAM_BOT_TOKEN")},
                params={"chat_id": _require_env(env, "TELEGRAM_CHAT_ID")},
                output_formats=["text", "markdown", "telegraph"],
            ),
            PlatformConfig(
                name="log",
                adapter_type="log",
                credentials={},
                params={"log_path": env.get("PHOSPHENE_OUTPUT_LOG", "logs/outputs.jsonl")},
            ),
        ],
        default_platform="telegram",
        listen=True,
    )


def _print_result(result: object) -> int:
    print(json.dumps(_to_jsonable(result), sort_keys=True))
    return 0 if getattr(result, "success", False) else 1


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_to_jsonable(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
