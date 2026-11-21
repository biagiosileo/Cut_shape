"""
Dati (JSON) per il documento di sintesi v2, letti dai file della cartella condivisa v2.
Uso: python dati_sintesi_v2.py <cartella v2> <out.json>
"""
import json
import os
import sys

import pandas as pd
from openpyxl import load_workbook

v2, out = sys.argv[1:3]
x = os.path.join(v2, '2_spostamento_punti', 'spostamento_punti.xlsx')
R = pd.read_excel(x, sheet_name='Riepilogo_classi', skiprows=3)
S = pd.read_excel(x, sheet_name='Ponti_modificati', skiprows=4)
C = pd.read_excel(x, sheet_name='Verifica_centro_cella', skiprows=4)
COL = {'compatibile': 'DFF0D8', 'quasi compatibile': 'FCE5CC', 'non compatibile': 'F6D5D5', 'senza area relazione': 'EDEDED'}
BREVE = {'sezione sul tracciato KML': 'tracciato KML', 'sezione sul tracciato KML (fosso piccolo, soglia ridotta)': 'fosso piccolo',
         'sezione secondo la relazione di ispezione (multi-asta)': 'relazione (multi-asta)',
         'sezione sul taglio del tombino': 'tombino', 'solo porzione di calcolo allargata': 'porzione allargata'}
f = lambda v, n=3: '-' if pd.isna(v) or v == '' else (f'{v:.{n}f}' if isinstance(v, float) else str(v))
D = {'riep': [[r.Classe, int(r['Prima analisi (212 ponti)']), int(r['Finale (212 ponti)'])] for _, r in R.iterrows()]}
D['tipi'] = [[t, int((S.Tipo_modifica == t).sum()), ', '.join(str(i) for i in S.ID[S.Tipo_modifica == t])]
             for t in BREVE if (S.Tipo_modifica == t).any()]
m = S[S.Spostamento_m > 0]
D['mossi'] = [[str(r.ID), BREVE[r.Tipo_modifica], f'{r.Spostamento_m:.0f}', f(r.A_relazione_km2), f(r.A_prima_km2),
               r.Classe_prima, f(r.A_finale_km2), r.Classe_finale, COL[r.Classe_finale]] for _, r in m.iterrows()]
e = C.Esito.value_counts()
div = C[C.Esito == 'bacino diverso (altra asta)']
D['centri'] = (f"{int(e.get('identico', 0))} ponti identici, {int(e.get('stessa area, altri parametri diversi', 0))} con la stessa area "
               f"ma altri parametri diversi (cella vicina sulla stessa asta), {int(e.get('area diversa meno del 2%', 0))} con area diversa "
               f"per meno del 2% e {len(div)} con un bacino completamente diverso, su un'altra asta (" +
               ', '.join(f'{int(r.ID)}: da {r.A_punto_usato_km2:g} a {r.A_punto_al_centro_cella_km2:g} km2' for _, r in div.iterrows()) + ')')
ws = load_workbook(os.path.join(v2, '5_verifica_manuale_ID100', 'ID100_VERIFICA_MANUALE_ATTRAVERSAMENTO.xlsm'), data_only=True)['Confronto']
q = {}
for r in ws.iter_rows(min_row=2, values_only=True):
    if r[2] and r[3] is not None:
        q[r[2]] = (r[3], r[5])
v = []
for k, nome, n in (('A', 'Area (km2)', 3), ('P', 'Perimetro (km)', 2), ('AE', 'Quota media (m)', 2), ('CN', 'Curve Number medio', 0),
                   ('S', 'Pendenza media del bacino (m/m)', 4), ('CS', 'Pendenza della cella (m/m)', 4)):
    v.append([nome, f(float(q[k][0]), n), f(float(q[k][1]), n)])
for r in ws.iter_rows(min_row=2, values_only=True):
    if r[7] and r[9] is not None and r[7] != "Reach_Slope_Centered_is_fallback" and isinstance(r[9], (int, float)):
        v.append([r[7], f"{r[9]:.5g}", f"{r[10]:g}" if isinstance(r[10], (int, float)) else str(r[10])])
D['v100'] = v
json.dump(D, open(out, 'w'), ensure_ascii=False, indent=1)
print(D['centri']); print(len(D['mossi']), D['tipi']); print(v)
