"""Network visualization: UMAP 2D projection of vault embeddings.

Produces a scatter plot colored by HDBSCAN cluster assignment,
with source type as marker shape and note preview on hover (saved as HTML).
Also saves a static PNG.

Usage:
    cd /mnt/passport/shared/phosphene
    ~/phosphene-venv/bin/python3 tools/visualize_network.py
"""
import sys, os
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src",
          "c:/Users/myeluashvili/claude-code-workspace/projects/toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

import numpy as np
from pathlib import Path

# --- Load vault ---
from phosphene.memory_store import MemoryStore, MemoryStoreConfig
from phosphene.memory_store.types import NoteQuery

vault_path = "vault"
if not Path(vault_path).exists():
    print("No vault directory. Run --seed-direct or --seed-chronological first.")
    sys.exit(1)

ms = MemoryStore(MemoryStoreConfig(vault_path=vault_path, embedding_path=f"{vault_path}/.embeddings"))
notes = ms.query_notes(NoteQuery(tier=1, limit=20000))

# Also load T2 and T3 if they exist
t2_notes = ms.query_notes(NoteQuery(tier=2, limit=5000))
t3_notes = ms.query_notes(NoteQuery(tier=3, limit=500))
all_notes = list(notes) + list(t2_notes) + list(t3_notes)

embeddings = []
metadata = []  # (tier, source, preview, note_id)
for note in all_notes:
    if note.embedding is not None:
        embeddings.append(note.embedding)
        preview = note.content[:100].replace("\n", " ").replace('"', "'")
        metadata.append({
            "tier": note.tier,
            "source": (note.source or "unknown").split("/")[0].replace("corpus_", ""),
            "preview": preview,
            "note_id": note.note_id,
            "importance": note.importance,
        })

if len(embeddings) < 10:
    print(f"Only {len(embeddings)} notes with embeddings. Need at least 10.")
    sys.exit(1)

emb = np.array(embeddings)
print(f"Loaded {len(emb)} notes ({len(notes)} T1, {len(t2_notes)} T2, {len(t3_notes)} T3)")

# --- UMAP 2D projection ---
import umap
print("Running UMAP 2D projection...")
reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=15, min_dist=0.1)
coords = reducer.fit_transform(emb)
print(f"  Projected to 2D: {coords.shape}")

# --- HDBSCAN clustering ---
import hdbscan
print("Clustering with HDBSCAN...")
# Use UMAP-reduced 15D for clustering (same as distillation)
reducer_cluster = umap.UMAP(n_components=15, random_state=42)
coords_15d = reducer_cluster.fit_transform(emb)
clusterer = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=2, metric="euclidean")
labels = clusterer.fit_predict(coords_15d)

n_clusters = len(set(labels) - {-1})
n_noise = int(np.sum(labels == -1))
print(f"  {n_clusters} clusters, {n_noise} noise ({n_noise*100//len(labels)}%)")

# --- Static PNG ---
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(1, 1, figsize=(16, 12))

# Color by cluster
unique_labels = sorted(set(labels))
colors = plt.cm.tab20(np.linspace(0, 1, max(20, n_clusters + 1)))

for label in unique_labels:
    mask = labels == label
    if label == -1:
        ax.scatter(coords[mask, 0], coords[mask, 1], c="lightgray", s=5, alpha=0.3, label="noise")
    else:
        color = colors[label % len(colors)]
        ax.scatter(coords[mask, 0], coords[mask, 1], c=[color], s=15, alpha=0.6)

# Highlight T2 and T3 notes
tier_markers = {"T2": "^", "T3": "s"}
for i, meta in enumerate(metadata):
    if meta["tier"] == 2:
        ax.scatter(coords[i, 0], coords[i, 1], c="red", s=50, marker="^", edgecolors="black", zorder=5)
    elif meta["tier"] == 3:
        ax.scatter(coords[i, 0], coords[i, 1], c="gold", s=80, marker="s", edgecolors="black", zorder=6)

# Source distribution legend
from collections import Counter
src_counts = Counter(m["source"] for m in metadata)
src_legend = ", ".join(f"{s}:{n}" for s, n in src_counts.most_common(6))

ax.set_title(f"Phosphene Memory Network — {len(emb)} notes, {n_clusters} clusters\n{src_legend}", fontsize=14)
ax.set_xlabel("UMAP-1")
ax.set_ylabel("UMAP-2")

# Detect language for annotation
ru_count = sum(1 for m in metadata if any("\u0400" <= c <= "\u04FF" for c in m["preview"]))
en_count = len(metadata) - ru_count
ax.annotate(f"RU:{ru_count} EN:{en_count}", xy=(0.02, 0.98), xycoords="axes fraction",
            fontsize=10, va="top", ha="left", bbox=dict(boxstyle="round", fc="white", alpha=0.8))

out_png = Path("notebooks/network_map.png")
out_png.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out_png, dpi=150, bbox_inches="tight")
print(f"Saved: {out_png}")
plt.close()

# --- Interactive HTML (plotly if available) ---
try:
    import plotly.express as px
    import pandas as pd

    df = pd.DataFrame({
        "x": coords[:, 0],
        "y": coords[:, 1],
        "cluster": [str(l) if l >= 0 else "noise" for l in labels],
        "tier": [f"T{m['tier']}" for m in metadata],
        "source": [m["source"] for m in metadata],
        "preview": [m["preview"][:80] for m in metadata],
    })

    fig = px.scatter(df, x="x", y="y", color="cluster", symbol="source",
                     hover_data=["preview", "tier", "source"],
                     title=f"Phosphene Network — {len(emb)} notes, {n_clusters} clusters",
                     width=1200, height=900)
    fig.update_traces(marker=dict(size=5, opacity=0.6))
    fig.update_layout(showlegend=False)  # too many clusters for legend

    out_html = Path("notebooks/network_map.html")
    fig.write_html(str(out_html))
    print(f"Saved interactive: {out_html}")
except ImportError:
    print("Plotly not installed — skipping interactive HTML. Install with: pip install plotly")

print("\nDone.")
