"""Create the selected core-pair network for connectivity modeling.

Edges are the union of an undirected 3-nearest-neighbor graph and the minimum
spanning tree. Straight lines select pairs only; they are not corridors.
"""

from datetime import datetime
from pathlib import Path
import csv
import os

import arcpy
import numpy as np
from scipy.spatial.distance import cdist
from scipy.sparse.csgraph import minimum_spanning_tree

GDB=r"C:\cheetah\gdb\cheetah_working.gdb"
CORES=os.path.join(GDB,"cheetah_core_primary_density051_min500")
OUTPUT=os.path.join(GDB,"cheetah_core_neighbor_links")
K_NEIGHBORS=3
BACKUPS=Path(r"C:\cheetah\backups")
REPORTS=Path(r"C:\cheetah\reports")
PARENT="Cheetah project"
GROUP="15 Connectivity links · selected"


def remove_refs(m,dataset):
    target=os.path.normcase(os.path.normpath(dataset))
    for layer in list(m.listLayers()):
        try:
            if layer.supports("DATASOURCE") and os.path.normcase(os.path.normpath(layer.dataSource))==target:
                m.removeLayer(layer)
        except Exception: pass


def main():
    if not arcpy.Exists(CORES): raise FileNotFoundError(CORES)
    aprx=arcpy.mp.ArcGISProject("CURRENT"); maps=aprx.listMaps("Map"); m=maps[0] if maps else aprx.activeMap
    parents=[x for x in m.listLayers() if x.isGroupLayer and x.longName==PARENT]
    if len(parents)!=1: raise RuntimeError(f"Expected one {PARENT!r} group; found {len(parents)}")
    wanted=PARENT+"\\"+GROUP; groups=[x for x in m.listLayers() if x.isGroupLayer and x.longName==wanted]
    target=groups[0] if groups else m.createGroupLayer(GROUP,parents[0])

    BACKUPS.mkdir(parents=True,exist_ok=True); REPORTS.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S"); backup=BACKUPS/f"{Path(aprx.filePath).stem}_before_core_links_{stamp}.aprx"
    aprx.saveACopy(str(backup)); print(f"backup: {backup}")

    records=[]
    with arcpy.da.SearchCursor(CORES,["CORE_ID","SHAPE@TRUECENTROID"]) as cursor:
        for core_id,xy in cursor: records.append((int(core_id),float(xy[0]),float(xy[1])))
    records.sort(); n=len(records)
    if n<2: raise RuntimeError(f"At least two cores are required; found {n}")
    coordinates=np.array([[x,y] for _,x,y in records],dtype=float)
    distances=cdist(coordinates,coordinates)
    np.fill_diagonal(distances,np.inf)

    knn=set()
    for i in range(n):
        for j in np.argsort(distances[i])[:min(K_NEIGHBORS,n-1)]: knn.add(tuple(sorted((i,int(j)))))
    mst_matrix=minimum_spanning_tree(np.where(np.isfinite(distances),distances,0)).tocoo()
    mst={tuple(sorted((int(i),int(j)))) for i,j in zip(mst_matrix.row,mst_matrix.col)}
    edges=sorted(knn|mst)

    remove_refs(m,OUTPUT)
    if arcpy.Exists(OUTPUT): arcpy.management.Delete(OUTPUT)
    sr=arcpy.Describe(CORES).spatialReference
    arcpy.management.CreateFeatureclass(GDB,Path(OUTPUT).name,"POLYLINE",spatial_reference=sr)
    for name,field_type,length in (("FROM_ID","LONG",None),("TO_ID","LONG",None),("DIST_KM","DOUBLE",None),("LINK_TYPE","TEXT",20)):
        if length is None: arcpy.management.AddField(OUTPUT,name,field_type)
        else: arcpy.management.AddField(OUTPUT,name,field_type,field_length=length)
    rows=[]
    with arcpy.da.InsertCursor(OUTPUT,["SHAPE@","FROM_ID","TO_ID","DIST_KM","LINK_TYPE"]) as cursor:
        for i,j in edges:
            from_id,x1,y1=records[i]; to_id,x2,y2=records[j]
            distance_km=float(np.linalg.norm(coordinates[i]-coordinates[j])/1000.0)
            link_type="KNN+MST" if (i,j) in knn and (i,j) in mst else "KNN" if (i,j) in knn else "MST_BRIDGE"
            geometry=arcpy.Polyline(arcpy.Array([arcpy.Point(x1,y1),arcpy.Point(x2,y2)]),sr)
            cursor.insertRow([geometry,from_id,to_id,distance_km,link_type])
            rows.append([from_id,to_id,distance_km,link_type])

    loose=m.addDataFromPath(OUTPUT); added=m.addLayerToGroup(target,loose,"BOTTOM"); m.removeLayer(loose)
    if not added: raise RuntimeError("Could not add neighbor links to selected group")
    added[0].visible=True; target.visible=True
    report=REPORTS/"cheetah_core_neighbor_links.csv"
    with report.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["from_core","to_core","straight_line_distance_km","link_type"]); w.writerows(rows)
    aprx.save()
    print(f"cores: {n}"); print(f"three-nearest-neighbor links: {len(knn)}")
    print(f"minimum-spanning-tree links: {len(mst)}"); print(f"additional MST bridge links: {len(mst-knn)}")
    print(f"selected unique pairs: {len(edges)}"); print(f"links: {OUTPUT}"); print(f"report: {report}")
    print("Complete. Lines identify selected core pairs only; no least-cost path or corridor was calculated.")

if __name__=="__main__": main()
