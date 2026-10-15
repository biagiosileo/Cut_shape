"""
Caratteristiche del database che possono rendere difficile il calcolo del
bacino, confrontate con l'esito (compatibile / non compatibile).

Per ogni caratteristica: quota di non compatibili con e senza la
caratteristica e test esatto di Fisher. Per ogni ponte non compatibile:
elenco delle criticita' presenti.

Uso: python criticita_database.py <Database.xlsx> <Risultati (con foglio Ponti)> <out_dir>
"""
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

dbx, res, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
db = pd.read_excel(dbx).rename(columns={'Unnamed: 0': 'ID'})
db = db[pd.to_numeric(db.ID, errors='coerce').notna()]
db['ID'] = db.ID.astype(int)
db = db.set_index('ID')
P = pd.read_excel(res, sheet_name='Ponti').set_index('ID')
ok = P['Compatibile (±15%)'] == True  # noqa: E712
hasdb = P['Area database (km²)'].notna()


def txt(c):
    return db[c].astype(str).str.strip().str.lower()


def num(c):
    return pd.to_numeric(db[c], errors='coerce')


nome = txt('Nome opera')
retic = txt('TIPOLOGIA RETICOLO (principale / secondario)')
alveo = txt('Tipologia Alveo (incassato/alluvionato largo o stretto/ inciso)')
conf = txt('CONFINAMENTO ALVEO (confinato/ semiconfinato/non confinato)')
arg = txt("TIPOLOGIA CORSO D'ACQUA (arginato (si)/ non arginato (no))")
curv = txt('TRATTO CON SENSIBILE CURVATURA (si / no)')
obl = txt("ORIENTAMENTO OBLIQUO RISPETTO ALL'ASSE LONGITUDINALE (Si/No)")
pend = num('pendenza media tratto %')
luce = num('LUCE TOT (SPALLA/SPALLA - m)')
larg = num('LARGHEZZA ALVEO INCISO (m)')
adb = P['Area database (km²)']

C = pd.DataFrame(index=P.index)
C['Opera non su corso d\'acqua (ferrovia/strada/svincolo nel nome)'] = nome.str.contains(
    r'ferrovi|svincolo|su sp|su ss|sovrappasso|cavalcavia|f\.s\.|ff/ss|ff\.ss', regex=True)
C['Reticolo artificiale di scolo'] = retic.str.contains('artificial')
C['Reticolo principale'] = retic.str.contains('principale')
C['Alveo alluvionato largo'] = alveo.str.contains('alluvionato largo')
C['Alveo alluvionato (largo o stretto)'] = alveo.str.contains('alluvionat')
C['Alveo non confinato'] = conf.str.contains('non confinato')
C['Alveo intrecciato (pluricursale)'] = conf.str.contains('intrecciat')
C['Corso arginato'] = arg.str.startswith('si')
C['Tratto con sensibile curvatura'] = curv.str.startswith('si')
C['Ponte obliquo rispetto all\'alveo'] = obl.str.startswith('si')
C['Pendenza del tratto < 1%'] = pend < 1
C['Luce totale > 100 m (viadotto)'] = luce > 100
C['Bacino DB < 0,5 km²'] = adb < 0.5
C['Larghezza alveo < 5 m'] = larg < 5

righe = []
for c in C.columns:
    m = C[c].fillna(False) & hasdb
    n = (~C[c].fillna(False)) & hasdb
    a, b = int((m & ~ok).sum()), int((m & ok).sum())
    cc, d = int((n & ~ok).sum()), int((n & ok).sum())
    _, p = fisher_exact([[a, b], [cc, d]]) if (a + b) and (cc + d) else (np.nan, np.nan)
    righe.append({'Caratteristica': c, 'Ponti con la caratteristica': a + b,
                  'di cui non compatibili': a, 'Quota non compatibili (con)': a / (a + b) if a + b else np.nan,
                  'Quota non compatibili (senza)': cc / (cc + d) if cc + d else np.nan,
                  'p (Fisher)': p})
S = pd.DataFrame(righe).sort_values('p (Fisher)')
crit = {i: [c for c in C.columns if bool(C.loc[i, c]) and c != 'Reticolo principale'] for i in P.index}
nc = P.index[~ok & hasdb]
T = pd.DataFrame({
    'ID': nc,
    'Strada': P.loc[nc, 'Strada'].values,
    'Progressiva': P.loc[nc, 'Progressiva'].values,
    'Nome opera': db.loc[nc, 'Nome opera'].values,
    'Area DB (km²)': adb[nc].values,
    'Area calcolata (km²)': P.loc[nc, 'Area calcolata 5 m (km²)'].values,
    'Tipologia reticolo': db.loc[nc, 'TIPOLOGIA RETICOLO (principale / secondario)'].values,
    'Tipologia alveo': db.loc[nc, 'Tipologia Alveo (incassato/alluvionato largo o stretto/ inciso)'].values,
    'Confinamento': db.loc[nc, 'CONFINAMENTO ALVEO (confinato/ semiconfinato/non confinato)'].values,
    'Arginato': db.loc[nc, "TIPOLOGIA CORSO D'ACQUA (arginato (si)/ non arginato (no))"].values,
    'Pendenza tratto %': pend[nc].values,
    'Luce totale (m)': luce[nc].values,
    'Larghezza alveo (m)': larg[nc].values,
    'N. criticità': [len(crit[i]) for i in nc],
    'Criticità dal database': ['; '.join(crit[i]) for i in nc],
})
if 'Probabile origine errore' in P.columns:
    T['Probabile origine errore'] = P.loc[nc, 'Probabile origine errore'].values
with pd.ExcelWriter(os.path.join(out, 'Criticita_da_database.xlsx'), engine='openpyxl') as w:
    S.to_excel(w, sheet_name='Caratteristiche vs esito', index=False)
    T.to_excel(w, sheet_name='Non compatibili', index=False)
    C.assign(Compatibile=ok, Area_DB=adb).reset_index().to_excel(w, sheet_name='Tutti i ponti', index=False)
    for ws in w.book.worksheets:
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(
                max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 60)
        ws.freeze_panes = 'B2'
pd.set_option('display.width', 250)
print(S.round(3).to_string(index=False))
print(T[['ID', 'Nome opera', 'N. criticità', 'Criticità dal database']].to_string(index=False))
