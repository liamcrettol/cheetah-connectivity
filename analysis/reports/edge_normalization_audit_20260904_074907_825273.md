# Edge-betweenness normalization audit

All 45 scores independently checked with NetworkX 3.6.

The previous script used the node-betweenness denominator 231. Standard undirected edge normalization divides raw scores by 253 (23 choose 2). Corrected scores equal previous scores times 21/23. All rankings and ties are unchanged.

This graph is unweighted: road/vegetation costs do not enter its centrality calculation. With fixed nodes and edges, unchanged rankings are structural, not evidence of biological or route robustness.

Original tables, GIS layers and paper files were not edited. The versioned CSV supplies corrected values for later production propagation. No connectivity rerun is required for this arithmetic correction.

Source: https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.centrality.edge_betweenness_centrality.html
