"""Create a reviewable Kruger boundary-fence reference layer.

The official SANParks park boundary is segmented and classified using published
boundary descriptions. This is an interpretive reference, not surveyed fence
geometry. No resistance surface is created or modified.
"""

from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError
import csv, json, os, ssl

import arcpy

SERVICE="https://dpmegis.dpme.gov.za/arcgis/rest/services/Environmental1/MapServer/1"
QUERY=SERVICE+"/query?"+urlencode({"where":"CUR_NME = 'Kruger National Park'","outFields":"*","returnGeometry":"true","outSR":"4326","f":"geojson"})
SANPARKS_PLAN="https://www.sanparks.org/wp-content/uploads/2021/03/knp-elephant-management-plan.pdf"
DFFE_PLAN="https://www.dffe.gov.za/sites/default/files/docs/krugernationalparkmanagement_approvedplan.pdf"
RAW=Path(r"C:\cheetah\raw\fences\kruger_sanparks_boundary.geojson")
GDB=r"C:\cheetah\gdb\cheetah_working.gdb"
MASK=r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
ALL_SEGMENTS=os.path.join(GDB,"kruger_boundary_fence_status_reference")
FENCED=os.path.join(GDB,"kruger_fence_documented_reference")
BACKUPS=Path(r"C:\cheetah\backups"); REPORTS=Path(r"C:\cheetah\reports")
PARENT="Cheetah project"; GROUP="11 Veterinary fences · reference"


def classify(lon,lat):
    # Approximate geographic interpretation of published named boundary sections.
    if lat <= -25.25:
        return "DOCUMENTED_FENCED","southern electrified boundary","HIGH"
    if lon <= 31.20:
        if lat <= -24.85:
            return "DOCUMENTED_FENCED","southwestern game-fence section toward Skukuza","MODERATE"
        if -23.75 <= lat <= -22.45:
            return "DOCUMENTED_FENCED","northwestern cabled veterinary-fence section","MODERATE"
        if -24.85 < lat < -23.75:
            return "DOCUMENTED_OPEN","western private-reserve interface described as unfenced","MODERATE"
    if lon >= 31.45:
        if lat <= -24.00:
            return "DOCUMENTED_FENCED","eastern boundary south of Olifants Gorge","MODERATE"
        return "DOCUMENTED_OPEN","northern/eastern transfrontier section with fence removed","MODERATE"
    if lat >= -22.50:
        return "DOCUMENTED_OPEN","northern boundary described as unfenced","HIGH"
    return "UNCERTAIN","boundary section not safely resolved from narrative description","LOW"


def rings(geometry):
    kind=geometry.get("type"); coords=geometry.get("coordinates",[])
    if kind=="Polygon":
        for ring in coords: yield ring
    elif kind=="MultiPolygon":
        for polygon in coords:
            for ring in polygon: yield ring


def remove_refs(m,dataset):
    target=os.path.normcase(os.path.normpath(dataset))
    for layer in list(m.listLayers()):
        try:
            if layer.supports("DATASOURCE") and os.path.normcase(os.path.normpath(layer.dataSource))==target: m.removeLayer(layer)
        except Exception: pass


def main():
    RAW.parent.mkdir(parents=True,exist_ok=True); REPORTS.mkdir(parents=True,exist_ok=True); BACKUPS.mkdir(parents=True,exist_ok=True)
    request=Request(QUERY,headers={"User-Agent":"ArcGIS-Pro-Cheetah-Connectivity/1.0"})
    try:
        with urlopen(request,timeout=120) as response: data=response.read()
    except URLError as exc:
        # ArcGIS Pro's bundled CA store may not recognize the DFFE/DP-ME server's
        # certificate chain. Limit the compatibility fallback to this known URL.
        if not isinstance(exc.reason, ssl.SSLCertVerificationError):
            raise
        print("WARNING: ArcGIS Pro could not verify the DFFE service certificate; retrying this official endpoint with certificate verification disabled")
        context=ssl.create_default_context()
        context.check_hostname=False
        context.verify_mode=ssl.CERT_NONE
        with urlopen(request,timeout=120,context=context) as response: data=response.read()
    RAW.write_bytes(data); geojson=json.loads(data.decode("utf-8-sig"))
    if not geojson.get("features"): raise RuntimeError("DFFE query returned no Kruger boundary feature")

    aprx=arcpy.mp.ArcGISProject("CURRENT"); maps=aprx.listMaps("Map"); m=maps[0] if maps else aprx.activeMap
    parents=[x for x in m.listLayers() if x.isGroupLayer and x.longName==PARENT]
    if len(parents)!=1: raise RuntimeError(f"Expected one {PARENT!r} group; found {len(parents)}")
    wanted=PARENT+"\\"+GROUP; groups=[x for x in m.listLayers() if x.isGroupLayer and x.longName==wanted]
    target=groups[0] if groups else m.createGroupLayer(GROUP,parents[0])
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S"); backup=BACKUPS/f"{Path(aprx.filePath).stem}_before_kruger_fence_reference_{stamp}.aprx"
    aprx.saveACopy(str(backup)); print(f"backup: {backup}")

    source_fc=os.path.join(GDB,"tmp_kruger_boundary_segments_wgs84")
    projected=os.path.join(GDB,"tmp_kruger_boundary_segments_projected")
    for dataset in (source_fc,projected,ALL_SEGMENTS,FENCED):
        remove_refs(m,dataset)
        if arcpy.Exists(dataset): arcpy.management.Delete(dataset)
    arcpy.management.CreateFeatureclass(GDB,Path(source_fc).name,"POLYLINE",spatial_reference=arcpy.SpatialReference(4326))
    for name,length in (("STATUS",24),("SECTION",120),("CONFIDENCE",12),("METHOD",80)):
        arcpy.management.AddField(source_fc,name,"TEXT",field_length=length)
    count=0
    with arcpy.da.InsertCursor(source_fc,["SHAPE@","STATUS","SECTION","CONFIDENCE","METHOD"]) as cursor:
        for feature in geojson["features"]:
            for ring in rings(feature.get("geometry",{})):
                for first,second in zip(ring[:-1],ring[1:]):
                    lon1,lat1=float(first[0]),float(first[1]); lon2,lat2=float(second[0]),float(second[1])
                    lon=(lon1+lon2)/2; lat=(lat1+lat2)/2; status,section,confidence=classify(lon,lat)
                    line=arcpy.Polyline(arcpy.Array([arcpy.Point(lon1,lat1),arcpy.Point(lon2,lat2)]),arcpy.SpatialReference(4326))
                    cursor.insertRow([line,status,section,confidence,"interpreted from SANParks boundary narrative"]); count+=1
    target_sr=arcpy.Describe(MASK).spatialReference
    arcpy.management.Project(source_fc,projected,target_sr)
    arcpy.analysis.Clip(projected,MASK,ALL_SEGMENTS)
    arcpy.analysis.Select(ALL_SEGMENTS,FENCED,"STATUS = 'DOCUMENTED_FENCED'")
    for dataset in (source_fc,projected):
        if arcpy.Exists(dataset): arcpy.management.Delete(dataset)

    status_counts={}
    with arcpy.da.SearchCursor(ALL_SEGMENTS,["STATUS","SHAPE@LENGTH"]) as cursor:
        for status,length in cursor:
            entry=status_counts.setdefault(status,[0,0.0]); entry[0]+=1; entry[1]+=float(length)/1000
    report=REPORTS/"kruger_boundary_fence_reference_inventory.csv"
    with report.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["status","segments","length_km","geometry_source","classification_source","warning"])
        for status,(segments,length) in sorted(status_counts.items()):
            w.writerow([status,segments,length,SERVICE,SANPARKS_PLAN,"interpretive boundary classification; not surveyed fence geometry"])
    for dataset,visible in ((ALL_SEGMENTS,False),(FENCED,True)):
        loose=m.addDataFromPath(dataset); added=m.addLayerToGroup(target,loose,"BOTTOM"); m.removeLayer(loose)
        if not added: raise RuntimeError(f"Could not group {dataset}")
        added[0].visible=visible
    target.visible=True; aprx.save()
    print(f"official boundary segments processed: {count}")
    for status,(segments,length) in sorted(status_counts.items()): print(f"{status}: {segments} segments; {length:.2f} km")
    print(f"all classified segments: {ALL_SEGMENTS}"); print(f"documented-fenced reference: {FENCED}"); print(f"report: {report}")
    print("Complete. This is a review layer only; no fence resistance raster or final model was changed.")

if __name__=="__main__": main()
