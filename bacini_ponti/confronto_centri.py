"""
Confronto tra il ricalcolo con i punti originali (ricalcolo_212) e quello con i punti al centro della cella
(ricalcolo_centri), ponte per ponte, sui parametri del codice. Uso:
python confronto_centri.py <porzioni originali> <porzioni centri> <csv di uscita>
"""
import glob
import os
import sys

import pandas as pd

a_dir, b_dir, out = sys.argv[1:4]
rd = lambda d: pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(d, '*_parametri.csv')))]).drop_duplicates('ID').set_index('ID')
A, B = rd(a_dir), rd(b_dir)
ids = sorted(set(A.index) & set(B.index))
num = [c for c in A.columns if c not in ('Longitude', 'Latitude', 'X_UTM33N', 'Y_UTM33N') and A[c].dtype != object]
rows = []
for i in ids:
    diff = [c for c in num if not (pd.isna(A.at[i, c]) and pd.isna(B.at[i, c])) and A.at[i, c] != B.at[i, c]]
    rows.append({'ID': int(i), 'A_orig_km2': A.at[i, 'A_km2'], 'A_centri_km2': B.at[i, 'A_km2'],
                 'Diff_area_perc': round(100 * (B.at[i, 'A_km2'] / A.at[i, 'A_km2'] - 1), 2) if A.at[i, 'A_km2'] else None,
                 'Snap_orig_m': A.at[i, 'Snap_Distance_m'], 'Snap_centri_m': B.at[i, 'Snap_Distance_m'],
                 'Parametri_diversi': ', '.join(c for c in diff if c != 'Snap_Distance_m')})
T = pd.DataFrame(rows)
T.to_csv(out, index=False)
cambia = T[T.Parametri_diversi != '']
print(f'ponti confrontati {len(T)} di 212; bacino o parametri diversi: {len(cambia)}')
print('distanza di aggancio con i centri:', T.Snap_centri_m.value_counts().to_dict())
if len(cambia):
    print(cambia.to_string(index=False))
