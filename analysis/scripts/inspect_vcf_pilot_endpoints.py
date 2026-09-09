"""Inspect saved pilot geometries and produce a diagnostic figure/report only."""
import json
import math
from pathlib import Path
import arcpy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as PlotPath
from matplotlib.patches import PathPatch

FOLDER = Path(r'C:\cheetah\diagnostics\vcf_v2_pair17_24_2016_20260903_155703_741091')
GDB = FOLDER / 'test.gdb'


def one(name):
    with arcpy.da.SearchCursor(str(GDB / name),['SHAPE@']) as rows:
        items = list(rows)
    if len(items)!=1 or items[0][0] is None:
        raise ValueError('Expected one geometry: '+name)
    return items[0][0]


def rings(geom):
    for part in geom:
        points=[]
        for p in part:
            if p is None:
                if points: yield points
                points=[]
            else:
                points.append((p.X/1000,p.Y/1000))
        if points: yield points


def main():
    old,new = one('saved_old_route'),one('candidate_route17_24')
    cores={17:one('source_core17'),24:one('destination_core24')}
    sr=old.spatialReference
    endpoints={}
    for label,line in [('old',old),('candidate',new)]:
        points=[arcpy.PointGeometry(line.firstPoint,sr),arcpy.PointGeometry(line.lastPoint,sr)]
        scores=[points[0].distanceTo(cores[17])+points[1].distanceTo(cores[24]),
                points[1].distanceTo(cores[17])+points[0].distanceTo(cores[24])]
        ordered=points if scores[0]<=scores[1] else list(reversed(points))
        endpoints[label]={}
        for cid,p in zip((17,24),ordered):
            if p.distanceTo(cores[cid])>.001:
                raise ValueError('Route endpoint is not inside assigned core')
            q=p.projectAs(arcpy.SpatialReference(4326)).firstPoint
            endpoints[label][str(cid)]={'x':p.firstPoint.X,'y':p.firstPoint.Y,'longitude':q.X,'latitude':q.Y}
    shifts={str(cid):math.hypot(endpoints['old'][str(cid)]['x']-endpoints['candidate'][str(cid)]['x'],
                               endpoints['old'][str(cid)]['y']-endpoints['candidate'][str(cid)]['y'])/1000 for cid in (17,24)}
    comparison=json.loads((FOLDER/'comparison.json').read_text())
    report={'endpoints':endpoints,'endpoint_displacement_km':shifts,
            'interpretation':'Both endpoint choices changed within the same fixed cores. The destination moved about 9.1 km; the source moved 1 km. This contributes to, but does not quantitatively partition, the observed route displacement.',
            'limits':['This is a core-to-core optimum, not a path between fixed points.',
                      'One diagnostic cannot establish robustness of other links or conservation rankings.',
                      'No additional path calculation or production change was performed.']}
    figure=FOLDER/'route_endpoint_comparison.png'
    outfile=FOLDER/'endpoint_comparison.json'
    if figure.exists() or outfile.exists():
        raise FileExistsError('Preserving existing endpoint outputs')
    fig,ax=plt.subplots(figsize=(10,8))
    fig.subplots_adjust(left=.12,right=.76,bottom=.14,top=.84)
    for cid,geom in cores.items():
        verts=[];codes=[]
        for ring in rings(geom):
            verts.extend(ring+[ring[0]])
            codes.extend([PlotPath.MOVETO]+[PlotPath.LINETO]*(len(ring)-1)+[PlotPath.CLOSEPOLY])
        ax.add_patch(PathPatch(PlotPath(verts,codes),facecolor='#e6e8eb',edgecolor='#70757a',lw=1,zorder=1))
    for label,geom,color,style in [('Old route',old,'#d55e00','--'),('Candidate route',new,'#0072b2','-')]:
        for i,ring in enumerate(rings(geom)):
            ax.plot([p[0] for p in ring],[p[1] for p in ring],color=color,ls=style,lw=2.5,
                    label=label if i==0 else None,zorder=3)
        tag='old' if label=='Old route' else 'candidate'
        for cid,marker in [('17','o'),('24','s')]:
            p=endpoints[tag][cid]
            ax.scatter(p['x']/1000,p['y']/1000,marker=marker,s=65,color=color,edgecolor='white',zorder=4)
    xmin=min(old.extent.XMin,new.extent.XMin)/1000-5
    xmax=max(old.extent.XMax,new.extent.XMax)/1000+5
    ymin=min(old.extent.YMin,new.extent.YMin)/1000-5
    ymax=max(old.extent.YMax,new.extent.YMax)/1000+5
    ax.set(xlim=(xmin,xmax),ylim=(ymin,ymax),xlabel='Easting (km)',ylabel='Northing (km)')
    ax.set_aspect('equal',adjustable='box')
    ax.grid(alpha=.15,zorder=0)
    ax.text(xmin+.7,ymax-1.7,'CORE 17',fontsize=11,weight='bold',color='#555555')
    ax.text(xmin+.7,ymin+1.1,'CORE 24',fontsize=11,weight='bold',color='#555555')
    ax.legend(loc='upper left',bbox_to_anchor=(1.02,1),frameon=False)
    ax.text(1.04,.73,f'Endpoint shifts\n\nCore 17: {shifts["17"]:.1f} km\nCore 24: {shifts["24"]:.1f} km',transform=ax.transAxes,fontsize=11,va='top')
    ax.text(1.04,.43,f'Route length\n32.1 → 33.1 km\n\nOptimized cost\n+{comparison["optimized_cost_change_percent"]:.2f}%\n\nCircle: core 17\nSquare: core 24',transform=ax.transAxes,fontsize=11,va='top')
    fig.suptitle('The route changed its departure and arrival locations',fontsize=15,weight='bold',y=.96)
    fig.text(.12,.90,'Core 17 → 24 · balanced 2016 · old versus candidate vegetation inputs',fontsize=11)
    fig.text(.12,.055,'Africa Albers, metres shown as km. Gray = portions of the fixed cores.\nControlled diagnostic; not a final corridor or conservation-priority map.',fontsize=10,color='#555555')
    fig.savefig(figure,dpi=170,facecolor='white')
    plt.close(fig)
    with outfile.open('x',encoding='utf-8') as f: json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))
    print('Figure:',figure)


if __name__=='__main__':
    main()
