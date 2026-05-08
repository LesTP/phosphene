"""MVP Orchestrator lifecycle shell."""

from __future__ import annotations

from phosphene.orchestrator.types import ModuleRefs, MVPOrchestratorConfig


class MVPOrchestrator:
    """Minimal constructor shell for the MVP Orchestrator."""

    def __init__(
        self,
        modules: ModuleRefs,
        config: MVPOrchestratorConfig,
    ) -> None:
        self.modules = modules
        self.config = config
