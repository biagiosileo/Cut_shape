# Esegue il codice originale fino all'accumulo (righe 1-221, senza modifiche) per una porzione,
# poi stampa accumulo e reticolo (acc > soglia) in una finestra attorno ai ponti della porzione.
import sys
src = open('/home/user/PONTI/ricalcolo_212/pysheds_bridges_5m.py').read().splitlines()
exec(compile('\n'.join(src[:221]), 'pysheds_bridges_5m.py', 'exec'))
from pyproj import Transformer
tr = Transformer.from_crs(BRIDGE_CSV_CRS, DEM_CRS, always_xy=True)
a = np.asarray(acc); f = np.asarray(fdir); af = acc.affine
for _, r in _ponti.iterrows():
    x, y = tr.transform(r.X, r.Y)
    c, rr = (~af) * (x, y)
    ci, ri = int(np.floor(c)), int(np.floor(rr))
    xs, ys = grid.snap_to_mask(acc > ACC_THRESHOLD, (x, y))
    cs, rs = grid.nearest_cell(xs, ys)
    print(f'\nPONTE {int(r.id)}: punto in cella (col {ci}, riga {ri}) offset {c-ci:.3f},{rr-ri:.3f}; '
          f'agganciato a cella (col {cs}, riga {rs}), dist {np.hypot(xs-x, ys-y):.2f} m')
    k = 6
    print('accumulo (celle), righe', ri-k, '..', ri+k, 'colonne', ci-k, '..', ci+k, '; * = reticolo, [] = cella del punto, <> = cella agganciata')
    for i in range(ri-k, ri+k+1):
        s = ''
        for j in range(ci-k, ci+k+1):
            v = int(a[i, j]); m = '*' if v > ACC_THRESHOLD else ' '
            t = f'{v}{m}'
            if (i, j) == (ri, ci): t = '[' + t + ']'
            elif (i, j) == (rs, cs): t = '<' + t + '>'
            s += f'{t:>10}'
        print(s)
    # cella del reticolo piu' vicina misurando dai centri delle celle (confronto)
    yi, xi = np.where(a > ACC_THRESHOLD)
    d = np.hypot(xi + 0.5 - c, yi + 0.5 - rr) * 5
    o = np.argsort(d)[:4]
    print('celle di reticolo piu vicine misurando dai centri:', [(int(xi[q]), int(yi[q]), round(float(d[q]), 2), int(a[yi[q], xi[q]])) for q in o])
