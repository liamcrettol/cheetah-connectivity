"""Read existing routes; draw four selected diagnostic examples, no solver."""
import csv
from pathlib import Path
import arcpy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from inspect_vcf_pilot_endpoints import rings

def main():
    root=Path(r'C:\cheetah\diagnostics\vcf_v2_balanced_overnight_v1')
    gdb=Path(r'C:\cheetah\gdb\cheetah_working.gdb')
    with (root/'comparisons.csv').open(newline='',encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
    selected=[]
    for pair in [(17,24),(24,28),(27,41),(38,40)]:
        subset=[r for r in rows if (int(r['from_core']),int(r['to_core']))==pair]
        selected.append(min(subset,key=lambda r:min(float(r['new_within_1000m_of_old_pct']),float(r['old_within_1000m_of_new_pct']))))
    cores={int(c):g for c,g in arcpy.da.SearchCursor(str(gdb/'cheetah_core_primary_density051_min500'),['CORE_ID','SHAPE@'])}
    fig,axes=plt.subplots(2,2,figsize=(12,11))
    fig.subplots_adjust(left=.10,right=.96,bottom=.12,top=.89,hspace=.36,wspace=.23)
    for ax,r in zip(axes.flat,selected):
        a,b,year=int(r['from_core']),int(r['to_core']),int(r['year'])
        with arcpy.da.SearchCursor(str(gdb/f'least_cost_paths_temporal_veg_balanced_{year}'),['SHAPE@'],f'FROM_ID = {a} AND TO_ID = {b}') as cur: old=list(cur)[0][0]
        with arcpy.da.SearchCursor(r['candidate_path'],['SHAPE@']) as cur: new=list(cur)[0][0]
        for c in (a,b):
            for ring in rings(cores[c]):
                x,y=zip(*ring);ax.plot(x,y,color='#aaaaaa',linewidth=1)
        for geom,color,style,label in [(old,'#D55E00','--','Old'),(new,'#0072B2','-','Candidate')]:
            for line in rings(geom):
                x,y=zip(*line);ax.plot(x,y,color=color,linestyle=style,linewidth=2,label=label)
            ax.scatter([geom.firstPoint.X/1000,geom.lastPoint.X/1000],[geom.firstPoint.Y/1000,geom.lastPoint.Y/1000],color=color,s=16)
        xmin=min(old.extent.XMin,new.extent.XMin)/1000; xmax=max(old.extent.XMax,new.extent.XMax)/1000
        ymin=min(old.extent.YMin,new.extent.YMin)/1000; ymax=max(old.extent.YMax,new.extent.YMax)/1000
        pad=max(3,.08*max(xmax-xmin,ymax-ymin))
        ax.set_xlim(xmin-pad,xmax+pad);ax.set_ylim(ymin-pad,ymax+pad);ax.set_aspect('equal')
        overlap=min(float(r['new_within_1000m_of_old_pct']),float(r['old_within_1000m_of_new_pct']))
        ax.set_title(f'{a}-{b}, {year}: {overlap:.1f}% min. 1 km overlap\nCost change {float(r["optimized_cost_change_pct"]):+.2f}%',fontsize=11)
        ax.set_xlabel('Easting (km)');ax.set_ylabel('Northing (km)')
        ax.tick_params(labelsize=9)
    fig.suptitle('Small cost changes can conceal route displacement',fontsize=17)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles[:2],labels[:2],loc='lower center',bbox_to_anchor=(.5,.055),ncol=2,frameon=False)
    fig.text(.10,.025,'Selected examples, not a representative sample. Fixed core boundaries gray; panel scales differ. Africa Albers.',fontsize=10)
    fig.text(.10,.005,'Controlled balanced-weight diagnostic only. No final barrier treatment or conservation-priority map.',fontsize=10)
    out=Path(r'C:\cheetah\reports\vcf_review_examples_20260904.png')
    if out.exists():raise FileExistsError(out)
    fig.savefig(out,dpi=160);plt.close(fig);print(out)

if __name__=='__main__':main()
