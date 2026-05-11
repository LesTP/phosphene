"""Measure link density on seeded vault."""
import sys
sys.path.insert(0, "src")

# Try toolkit from env or common locations
import os
toolkit_src = os.environ.get("TOOLKIT_SRC")
if toolkit_src:
    sys.path.insert(0, toolkit_src)
for candidate in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(candidate):
        sys.path.insert(0, candidate)
        break

from phosphene.memory_store import MemoryStore, MemoryStoreConfig

ms = MemoryStore(MemoryStoreConfig(
    vault_path="vault",
    embedding_path="vault/.embeddings",
))
metrics = ms.get_density_metrics()

print(f"note_count:        {metrics.note_count}")
print(f"mean_link_degree:  {metrics.mean_link_degree:.2f}")
print(f"cluster_count:     {metrics.cluster_count}")
print(f"unresolved_count:  {metrics.unresolved_count}")
print(f"max_unresolvedness: {metrics.max_unresolvedness:.2f}")

# Phase 2 activation check
crossover = 3.0
ramp_start = crossover * 0.5
ramp_end = crossover * 2.0
print(f"\nPhase 2 check (crossover={crossover}):")
print(f"  note_count >= 50:           {metrics.note_count >= 50}")
print(f"  cluster_count >= 3:         {metrics.cluster_count >= 3}")
print(f"  mean_link_degree >= {ramp_start}: {metrics.mean_link_degree >= ramp_start}")
if metrics.mean_link_degree >= ramp_start:
    progress = min(1.0, (metrics.mean_link_degree - ramp_start) / (ramp_end - ramp_start))
    weight = progress * 0.7
    print(f"  Phase 2 ramp progress:      {progress:.2f}")
    print(f"  Structure weight:           {weight:.2f} (prompt weight: {1-weight:.2f})")
else:
    print(f"  Phase 2: NOT ACTIVE")
