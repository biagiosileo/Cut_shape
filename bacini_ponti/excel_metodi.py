"""
Excel di confronto tra metodi di estrazione (una riga per ID 1-212).

Uso: python excel_metodi.py <aree_metodi_alternativi.csv> <file_out.xlsx>
"""
import sys

import numpy as np
import pandas as pd

TOL = 0.15
src, out = sys.argv[1], sys.argv[2]
d = pd.read_csv(src).sort_values('ID').reset_index(drop=True)
db = d.A_db_km2
metodi = {
    'pysheds_fill_D8': 'pysheds: riempimento + D8 (script)',
    'WBT_fill_D8': 'Whitebox: riempimento + D8',
    'WBT_breach_D8': 'Whitebox: apertura depressioni + D8',
    'WBT_breach_Dinf': 'Whitebox: apertura depressioni + D-infinito',
}
t = d[['ID']].copy()
t['Area database (km²)'] = db
oks = []
for k, lab in metodi.items():
    a = d[f'A_{k}_km2']
    e = a / db - 1
    ok = (e.abs() <= TOL) & db.notna()
    oks.append(ok)
    t[f'{lab} (km²)'] = a
    t[f'{lab}: diff. %'] = e
    t[f'{lab}: compatibile'] = np.where(db.notna(), ok, None)
t['N. metodi compatibili'] = np.where(db.notna(), np.sum(oks, axis=0), None)
dist = d['Dist_min_compatibile_WBT_fill_D8_m']
t['Spostamento minimo per area compatibile (m) [Whitebox fill D8]'] = dist


def esito(i):
    if pd.isna(db[i]):
        return 'area DB mancante'
    n = int(t.loc[i, 'N. metodi compatibili'])
    if n == 4:
        return 'compatibile con tutti i metodi'
    if n > 0:
        return 'compatibile solo con alcuni metodi (dipende dall\'algoritmo)'
    if db[i] < 0.25:
        return 'non compatibile: DB sotto la soglia del reticolo (0,25 km²)'
    if pd.isna(dist[i]):
        return 'non compatibile: nessun punto con area compatibile entro 5 km'
    if dist[i] <= 200:
        return 'non compatibile: area compatibile entro 200 m (posizione del ponte/alveo)'
    return 'non compatibile: area compatibile solo oltre 200 m (coordinata o valore DB da verificare)'


t['Esito'] = [esito(i) for i in t.index]
sint = pd.DataFrame(
    [(lab, int(ok.sum()), int(db.notna().sum())) for lab, ok in zip(metodi.values(), oks)] +
    [('Compatibile con almeno un metodo', int(np.logical_or.reduce(oks).sum()), int(db.notna().sum()))],
    columns=['Metodo', 'Compatibili (±15%)', 'Ponti con area DB'])
es = t.Esito.value_counts().rename_axis('Esito').reset_index(name='N. ponti')
note = pd.DataFrame({'Note': [
    "Stesso DEM (mosaico 30 m), stessa regola di aggancio (cella più vicina con area ≥ 0,25 km²); cambia solo "
    "l'algoritmo di estrazione.",
    "Riempimento: le depressioni (anche quelle create da rilevati e argini) vengono allagate fino allo sfioro. "
    "Apertura (breaching, Lindsay 2016): si scava un canale a costo minimo attraverso l'ostacolo.",
    "D8: tutto il flusso va verso una sola cella vicina. D-infinito: il flusso si divide tra due celle.",
    "Lo 'spostamento minimo' è la distanza dal ponte della cella più vicina con area compatibile col database, "
    "entro 5 km. È una diagnostica, non una correzione: per i bacini piccoli (DB < 1 km²) celle con area simile "
    "si trovano quasi ovunque, quindi distanze brevi non dimostrano nulla.",
]})
with pd.ExcelWriter(out, engine='openpyxl') as w:
    t.to_excel(w, sheet_name='Ponti', index=False)
    sint.to_excel(w, sheet_name='Sintesi metodi', index=False)
    es.to_excel(w, sheet_name='Sintesi esiti', index=False)
    note.to_excel(w, sheet_name='Note', index=False)
    for ws in w.book.worksheets:
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(
                max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 60)
        ws.freeze_panes = 'B2' if ws.title == 'Ponti' else 'A2'
    ws = w.book['Ponti']
    for j, name in enumerate(t.columns, 1):
        if name.endswith('diff. %'):
            for row in ws.iter_rows(min_row=2, min_col=j, max_col=j):
                row[0].number_format = '0.0%'
print(sint.to_string(index=False))
print(es.to_string(index=False))
