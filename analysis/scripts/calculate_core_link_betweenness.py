"""Calculate edge betweenness for the 23-core candidate graph.

This is a network-position measure, not a movement-probability estimate. It is
joined to robust_conservation_link_screen.csv so model-sensitive links remain
visible but cannot enter the primary priority set.
"""

from collections import defaultdict, deque
from pathlib import Path
import csv

EDGES = Path(r"C:\cheetah\reports\cheetah_core_neighbor_links.csv")
SCREEN = Path(r"C:\cheetah\reports\robust_conservation_link_screen.csv")
OUTPUT = Path(r"C:\cheetah\reports\conservation_link_importance_betweenness.csv")


def edge(a, b):
    return tuple(sorted((int(a), int(b))))


def betweenness(graph):
    score = defaultdict(float)
    nodes = sorted(graph)
    for source in nodes:
        stack = []
        pred = defaultdict(list)
        sigma = defaultdict(float)
        distance = {source: 0}
        sigma[source] = 1.0
        queue = deque([source])
        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in graph[v]:
                if w not in distance:
                    distance[w] = distance[v] + 1
                    queue.append(w)
                if distance[w] == distance[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        dependency = defaultdict(float)
        while stack:
            w = stack.pop()
            for v in pred[w]:
                contribution = (sigma[v] / sigma[w]) * (1.0 + dependency[w])
                score[edge(v, w)] += contribution
                dependency[v] += contribution
    # Brandes counts each undirected pair twice.
    for e in list(score):
        score[e] /= 2.0
    denominator = ((len(nodes) - 1) * (len(nodes) - 2)) / 2.0
    return {e: (value / denominator if denominator else 0.0) for e, value in score.items()}


def main():
    graph = defaultdict(set)
    edge_rows = {}
    with EDGES.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            e = edge(row["from_core"], row["to_core"])
            graph[e[0]].add(e[1])
            graph[e[1]].add(e[0])
            edge_rows[e] = row

    screen = {}
    with SCREEN.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            screen[edge(row["from_core"], row["to_core"])] = row

    scores = betweenness(graph)
    rows = []
    for e in sorted(edge_rows):
        base = edge_rows[e]
        scr = screen.get(e, {})
        rows.append({
            "from_core": e[0],
            "to_core": e[1],
            "link_type": base.get("link_type", ""),
            "straight_line_distance_km": base.get("straight_line_distance_km", ""),
            "edge_betweenness_normalized": scores.get(e, 0.0),
            "weight_robust": scr.get("weight_robust", ""),
            "fence_robust": scr.get("fence_robust", ""),
            "primary_priority_eligible": scr.get("primary_priority_eligible", "no"),
            "priority_use": (
                "rank for primary conservation priority"
                if scr.get("primary_priority_eligible") == "yes"
                else "retain as uncertainty/data-collection link"
            ),
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    top = sorted(rows, key=lambda r: float(r["edge_betweenness_normalized"]), reverse=True)[:10]
    print(f"links scored: {len(rows)}")
    print("top 10 by normalized edge betweenness:")
    for row in top:
        print(f"  {row['from_core']}–{row['to_core']}: {float(row['edge_betweenness_normalized']):.4f} ({row['priority_use']})")
    print(f"report: {OUTPUT}")
    print("No rasters, paths, or map layers were changed.")


if __name__ == "__main__":
    main()
