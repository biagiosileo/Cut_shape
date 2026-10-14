# Prova esplorativa (percorsi relativi alla cartella di lavoro della sessione).
import numpy as np, pandas as pd, rasterio, time
np.in1d=np.isin
from rasterio.windows import Window
from rasterio.warp import reproject, Resampling
from rasterio.transform import Affine
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
src=rasterio.open('lavoro/dem30_mosaico.tif'); acc30=np.load('lavoro/acc30.npy')
d=pd.read_csv('risultati_v2/aree_dem30_v2.csv'); d=d[d.A_db_km2.notna()&(d.A_db_km2<10)].reset_index(drop=True)
HALF=3000.0; F=6
out=[]; t0=time.time()
for _,p in d.iterrows():
    x,y=p.X_UTM33N,p.Y_UTM33N
    c,r=~src.transform*(x,y); n=int(HALF/30)
    win=Window(int(c)-n,int(r)-n,2*n+1,2*n+1)
    z=src.read(1,window=win,boundless=True,fill_value=-9999); tw=src.window_transform(win)
    t5=Affine(tw.a/F,0,tw.c,0,tw.e/F,tw.f); z5=np.full((z.shape[0]*F,z.shape[1]*F),-9999,np.float32)
    reproject(z,z5,src_transform=tw,dst_transform=t5,src_crs=src.crs,dst_crs=src.crs,src_nodata=-9999,dst_nodata=-9999,resampling=Resampling.bilinear)
    vf=ViewFinder(affine=t5,shape=z5.shape,crs=src.crs,nodata=np.float32(-9999))
    dem=Raster(z5,viewfinder=vf); g=Grid.from_raster(dem)
    fd=g.flowdir(g.resolve_flats(g.fill_depressions(g.fill_pits(dem)))); acc=np.asarray(g.accumulation(fd),float)*25/1e6
    R,C=np.mgrid[0:z5.shape[0],0:z5.shape[1]]; X,Y=t5*(C+.5,R+.5); dd=np.hypot(X-x,Y-y)
    o={'ID':p.ID,'A_db':p.A_db_km2,'A5orig':p.A_5m_originale_km2}
    for thr in (0.0125,0.1,0.25):
        m=acc>=thr; i=np.argmin(np.where(m,dd,1e12)); a=acc.flat[i]
        r_,c_=divmod(i,z5.shape[1]); edge=False
        o[f'A5res_{thr}']=a
    out.append(o)
o=pd.DataFrame(out); o.to_csv('lavoro/resample_test.csv',index=False)
print(len(o),'ponti DB<10 km2, %.0fs'%(time.time()-t0))
for c in o.columns[2:]: print(c, (np.abs(o[c]/o.A_db-1)<=.15).sum())
