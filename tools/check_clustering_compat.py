"""Full interface check: verify _RaptorClusterConfig works with toolkit clustering."""
import sys, os
sys.path.insert(0, "src")
sys.path.insert(0, os.environ.get("TOOLKIT_SRC", "/mnt/passport/shared/toolkit/src"))

import numpy as np
from toolkit.clustering import ClusterConfig, ClusterStrategy, cluster
from phosphene.distillation.engine import _RaptorClusterConfig, _StrategyStr

# 1. ClusterConfig fields
print("ClusterConfig fields:")
for f, field in ClusterConfig.__dataclass_fields__.items():
    print(f"  {f}: default={field.default!r}")

# 2. Strategy enum
print("\nClusterStrategy values:")
for s in ClusterStrategy:
    print(f"  {s.name} = {s.value!r}")

# 3. _StrategyStr compat
strat = _StrategyStr("raptor")
print(f"\n_StrategyStr('raptor'):")
print(f"  .value = {strat.value!r}")
print(f"  == ClusterStrategy.RAPTOR: {strat == ClusterStrategy.RAPTOR}")

# 4. Build config
cfg = _RaptorClusterConfig(
    strategy=_StrategyStr("raptor"),
    raptor_summarizer=lambda texts: "summary of " + str(len(texts)) + " items",
    raptor_embedder=lambda texts: np.random.randn(len(texts), 10).astype(np.float32),
)
print(f"\nConfig: strategy={cfg.strategy.value}, metric={cfg.metric}, "
      f"min_cluster_size={cfg.min_cluster_size}, min_samples={cfg.min_samples}")

# 5. Dry-run cluster with fake data
embs = np.random.randn(30, 10).astype(np.float32)
texts = [f"text {i}" for i in range(30)]
try:
    result = cluster(embs, cfg, texts=texts)
    print(f"\nDry-run OK: {result.n_clusters} clusters, {result.n_noise} noise")
    if result.tree:
        print(f"  Tree: {len(result.tree)} layers")
        for layer in result.tree:
            print(f"    depth={layer.depth}: {len(layer.cluster_ids)} clusters, "
                  f"summaries={'yes' if layer.summaries else 'no'}")
except Exception as e:
    print(f"\nDry-run FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
