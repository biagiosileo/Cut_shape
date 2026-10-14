# Prova esplorativa: i bacini (Whitebox riempimento + D8) sono contenuti nel mosaico a 30 m?
import numpy as np, pandas as pd, rasterio, whitebox_workflows as wb
np.in1d=np.isin
from pysheds.grid import Grid
wbe=wb.WbEnvironment(); wbe.verbose=False
dem=wbe.read_raster('lavoro/dem30_mosaico.tif')
wbe.write_raster(wbe.hydrology.fill_depressions(dem=dem),'lavoro/dem30_wbt_fill.tif')
g=Grid.from_raster('lavoro/dem30_wbt_fill.tif'); z=g.read_raster('lavoro/dem30_wbt_fill.tif')
fd=g.flowdir(z); acc=np.asarray(g.accumulation(fd),float)*0.0009
src=rasterio.open('lavoro/dem30_mosaico.tif'); T=src.transform; zz=src.read(1); valid=zz!=-9999
nr,nc=zz.shape
d=pd.read_csv('/home/user/Cut_shape/risultati_v2/aree_metodi_alternativi.csv').merge(pd.read_csv('/home/user/Cut_shape/risultati_v2/aree_dem30_soglia_0.25.csv')[['ID','X_UTM33N','Y_UTM33N']],on='ID')
out=[]
for _,p in d.iterrows():
    c0,r0=~T*(p.X_UTM33N,p.Y_UTM33N); r0,c0=int(r0),int(c0); n=4
    while True:
        rr,cc=np.mgrid[max(r0-n,0):min(r0+n+1,nr),max(c0-n,0):min(c0+n+1,nc)]; X,Y=T*(cc+.5,rr+.5); dd=np.hypot(X-p.X_UTM33N,Y-p.Y_UTM33N)
        m=acc[rr,cc]>=0.25
        if m.any(): break
        n*=2
    i=np.argmin(np.where(m,dd,np.inf)); r,c=rr.flat[i],cc.flat[i]
    b=np.asarray(g.catchment(x=c,y=r,fdir=fd,xytype='index'),bool)
    R,C=np.nonzero(b)
    # distanza minima (km) dal bordo del dato valido: celle del bacino adiacenti a nodata/bordo
    pad=np.pad(valid,1,constant_values=False); nb=np.zeros_like(b)
    for dr in (-1,0,1):
        for dc in (-1,0,1): nb|=~pad[1+dr:1+dr+nr,1+dc:1+dc+nc]
    tocca=b&nb; ztocca=zz[tocca]
    out.append(dict(ID=p.ID,A=b.sum()*0.0009,celle_bordo=int(tocca.sum()),zmax_bordo=float(ztocca.max()) if tocca.any() else np.nan,
                    troncato=bool((ztocca>max(20,zz[r,c]+20)).any()) if tocca.any() else False,
                    xmin=T.c+C.min()*30,xmax=T.c+(C.max()+1)*30,ymin=T.f-(R.max()+1)*30,ymax=T.f-R.min()*30))
o=pd.DataFrame(out); o.to_csv('lavoro/contenimento.csv',index=False)
print('troncati',o.troncato.sum(), o[o.troncato].ID.tolist())
print(o.sort_values('A',ascending=False).head(12).round(1).to_string(index=False))
