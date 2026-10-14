"""
Scelta della soglia del reticolo a 5 m e confronto tra regole di aggancio.

Per ogni regola (punto di aggancio) e soglia: numero di ponti compatibili
(±15%). La soglia della regola principale (intersezione tracciato-reticolo) si
sceglie con validazione incrociata: scelta su meta' dei ponti, verifica
sull'altra meta', 500 ripetizioni.

Uso: python scelta_soglia_5m.py <aggancio.csv> <out_dir>
"""
import os
import sys

import numpy as np
import pandas as pd

TOL = 0.15
agg, out = sys.argv[1:3]
d = pd.read_csv(agg)
d = d[d.A_db_km2.notna() & (d.A_db_km2 > 0)]
regole = ['A_intersezione', 'A_input', 'A_inizio', 'A_fine', 'A_kml']
tab = []
for s, g in d.groupby('Soglia_km2'):
    o = {'Soglia_km2': s, 'N': len(g)}
    for r in regole:
        o[r] = int(((g[r] / g.A_db_km2 - 1).abs() <= TOL).sum())
    tab.append(o)
tab = pd.DataFrame(tab)
print(tab.to_string(index=False))

rng = np.random.default_rng(0)
ids = d.ID.unique()
ok = {(r, s): g.set_index('ID').pipe(lambda x: (x[r] / x.A_db_km2 - 1).abs() <= TOL)
      for s, g in d.groupby('Soglia_km2') for r in regole}
cv = []
for r in regole:
    sc, scelte = [], []
    for _ in range(500):
        p = rng.permutation(ids)
        a, b = p[:len(p) // 2], p[len(p) // 2:]
        best = max(sorted(d.Soglia_km2.unique()), key=lambda s: ok[(r, s)].reindex(a).sum())
        scelte.append(best)
        sc.append(ok[(r, best)].reindex(b).mean())
    cv.append({'Regola': r, 'CV_media_compatibili': np.mean(sc), 'CV_dev_std': np.std(sc),
               'Soglia_scelta_piu_frequente': pd.Series(scelte).mode()[0]})
cv = pd.DataFrame(cv)
print(cv.to_string(index=False))
tab.to_csv(os.path.join(out, 'soglie_regole_5m.csv'), index=False)
cv.to_csv(os.path.join(out, 'validazione_incrociata_5m.csv'), index=False)
