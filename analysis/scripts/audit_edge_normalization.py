"""Independent normalized-edge verification; versioned report only."""
import csv
import datetime as dt
from pathlib import Path
import networkx as nx

def main():
    root=Path(r'C:\cheetah\reports')
    with (root/'cheetah_core_neighbor_links.csv').open(newline='',encoding='utf-8-sig') as f: links=list(csv.DictReader(f))
    with (root/'conservation_link_importance_betweenness.csv').open(newline='',encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
    graph=nx.Graph()
    graph.add_edges_from((int(r['from_core']),int(r['to_core'])) for r in links)
    assert graph.number_of_nodes()==23 and graph.number_of_edges()==45
    corrected={tuple(sorted(k)):v for k,v in nx.edge_betweenness_centrality(graph,normalized=True,weight=None).items()}
    factor=(23-2)/23
    for r in rows:
        pair=tuple(sorted((int(r['from_core']),int(r['to_core']))))
        original=float(r['edge_betweenness_normalized'])
        assert abs(original*factor-corrected[pair])<1e-12
        r['edge_betweenness_normalized_previous']=r.pop('edge_betweenness_normalized')
        r['edge_betweenness_normalized_corrected']=corrected[pair]
    assert len(rows)==45
    # Positive uniform scaling preserves all ties and pairwise rankings.
    for a in rows:
        for b in rows:
            old=float(a['edge_betweenness_normalized_previous'])-float(b['edge_betweenness_normalized_previous'])
            new=a['edge_betweenness_normalized_corrected']-b['edge_betweenness_normalized_corrected']
            assert abs(old)<1e-12 and abs(new)<1e-12 or old*new>0
    stem=root/('edge_normalization_audit_'+dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    with stem.with_suffix('.csv').open('x',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    stem.with_suffix('.md').write_text('# Edge-betweenness normalization audit\n\n'
        'All 45 scores independently checked with NetworkX '+nx.__version__+'.\n\n'
        'The previous script used the node-betweenness denominator 231. Standard undirected edge normalization divides raw scores by 253 (23 choose 2). Corrected scores equal previous scores times 21/23. All rankings and ties are unchanged.\n\n'
        'This graph is unweighted: road/vegetation costs do not enter its centrality calculation. With fixed nodes and edges, unchanged rankings are structural, not evidence of biological or route robustness.\n\n'
        'Original tables, GIS layers and paper files were not edited. The versioned CSV supplies corrected values for later production propagation. No connectivity rerun is required for this arithmetic correction.\n\n'
        'Source: https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.centrality.edge_betweenness_centrality.html\n',encoding='utf-8')
    top=max(rows,key=lambda r:r['edge_betweenness_normalized_corrected'])
    print('Verified 45 normalized scores; all rankings unchanged. Top:',top['from_core'],top['to_core'],top['edge_betweenness_normalized_previous'],top['edge_betweenness_normalized_corrected'])
    print('REPORT:',stem.with_suffix('.md'))

if __name__=='__main__':main()
