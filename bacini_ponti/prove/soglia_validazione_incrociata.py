# Prova esplorativa (percorsi relativi alla cartella di lavoro della sessione).
import numpy as np, pandas as pd, rasterio
acc=np.load('lavoro/acc30.npy'); src=rasterio.open('lavoro/dem30_mosaico.tif'); T=src.transform; valid=src.read(1)!=-9999
ck=0.0009
d=pd.read_csv('risultati_v2/aree_dem30_v2.csv'); c=pd.read_csv('zip/handoff/dati/cmp.csv')[['ID','W_alveo']]
d=d.merge(c,on='ID'); d=d[d.A_db_km2.notna()].reset_index(drop=True)
# candidati entro 300 m con area >= 0.0125
cand=[]
for x,y in zip(d.X_UTM33N,d.Y_UTM33N):
    cc0,r0=~T*(x,y); r0,cc0=int(r0),int(cc0); n=11
    rr,cc=np.mgrid[r0-n:r0+n+1,cc0-n:cc0+n+1]; X,Y=T*(cc+.5,rr+.5); dd=np.hypot(X-x,Y-y)
    a=acc[rr,cc]*ck; m=(dd<=300)&(a>=0.0125)&valid[rr,cc]
    cand.append((a[m],dd[m]))
A=d.A_db_km2.values
def nearest_thr(thr):
    out=[]
    for a,dd in cand:
        m=a>=thr
        out.append(a[m][np.argmin(dd[m])] if m.any() else np.nan)
    return np.array(out)
thrs=[0.0125,0.05,0.1,0.25,0.5,1,2]
res={t:np.abs(nearest_thr(t)/A-1)<=.15 for t in thrs}
def width_snap(a_,b_,R):
    out=[]
    for (a,dd),w in zip(cand,d.W_alveo.values):
        m=dd<=R
        if not m.any() or np.isnan(w): out.append(np.nan); continue
        Ae=np.exp(a_+b_*np.log(w)); k=np.argmin(np.abs(np.log(a[m]/Ae)))
        out.append(a[m][k])
    return np.array(out)
rng=np.random.default_rng(0); s1=[];s2=[]
for rep in range(200):
    idx=rng.permutation(len(d)); tr,te=idx[:len(d)//2],idx[len(d)//2:]
    best=max(thrs,key=lambda t:res[t][tr].sum()); s1.append(res[best][te].mean())
    g=d.iloc[tr]; g=g[g.W_alveo>0]; b_,a_=np.polyfit(np.log(g.W_alveo),np.log(g.A_db_km2),1)
    s2.append((np.abs(width_snap(a_,b_,150)[te]/A[te]-1)<=.15).mean())
print('soglia fissa scelta su meta, valutata sull altra: %.1f%% (sd %.1f)'%(100*np.mean(s1),100*np.std(s1)))
print('snap guidato dalla larghezza alveo (CV): %.1f%% (sd %.1f)'%(100*np.mean(s2),100*np.std(s2)))
g=d[d.W_alveo>0]; b_,a_=np.polyfit(np.log(g.W_alveo),np.log(g.A_db_km2),1); print('A = %.3f * W^%.2f'%(np.exp(a_),b_))
for R in (60,90,150,300): print('larghezza R',R,(np.abs(width_snap(a_,b_,R)/A-1)<=.15).sum())
