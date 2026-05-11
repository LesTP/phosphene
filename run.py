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
_TOOLKIT_PATH = os.environ.get(
    "TOOLKIT_SRC",
    str(Path(r"c:\Users\myeluashvili\claude-code-workspace\projects\toolkit\src")),
)
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
        "--seed-only",
        action="store_true",
        help="Run one ingestion activation and exit.",
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
                "archive_path": env.get("PHOSPHENE_LJ_ARCHIVE_PATH", "seed/livejournal"),
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
