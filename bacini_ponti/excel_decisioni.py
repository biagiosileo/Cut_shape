"""
Tabella delle decisioni per ID (1-212): quale area adottare e cosa fare per i
ponti non compatibili.

Regola adottata (non usa l'area del database per scegliere):
  - area calcolata con Whitebox (riempimento + D8) sul DEM a 30 m;
  - se questa area e' < SOGLIA_5M_KM2 il bacino e' piccolo e la cella da 30 m
    e' troppo grossolana: si usa l'area dello script originale sul DEM a 5 m.

Uso: python excel_decisioni.py <aree_metodi_alternativi.csv> <aree_dem30_soglia_0.25.csv> <out.xlsx>
"""
import sys

import numpy as np
import pandas as pd

TOL = 0.15
SOGLIA_5M_KM2 = 1.0

m = pd.read_csv(sys.argv[1])
a = pd.read_csv(sys.argv[2])[['ID', 'Gruppo', 'X_UTM33N', 'Y_UTM33N', 'A_5m_originale_km2']]
d = a.merge(m, on='ID').sort_values('ID').reset_index(drop=True)
db = d.A_db_km2
usa5 = d.A_WBT_fill_D8_km2 < SOGLIA_5M_KM2
d['Fonte'] = np.where(usa5, 'DEM 5 m (script originale)', 'DEM 30 m (Whitebox riempimento + D8)')
d['A_adottata'] = np.where(usa5, d.A_5m_originale_km2, d.A_WBT_fill_D8_km2)
d['Diff_km2'] = d.A_adottata - db
d['Diff'] = d.A_adottata / db - 1
d['OK'] = (d.Diff.abs() <= TOL) & db.notna()
altri = [c for c in ('A_pysheds_fill_D8_km2', 'A_WBT_breach_D8_km2', 'A_WBT_breach_Dinf_km2', 'A_5m_originale_km2')]
d['OK_altro'] = np.logical_or.reduce([((d[c] / db - 1).abs() <= TOL) for c in altri]) & db.notna()
dist = d.Dist_min_compatibile_WBT_fill_D8_m
anomali = {98, 99, 101, 103, 129, 151}


def decisione(r, i):
    if pd.isna(r.A_db_km2):
        return ('Area DB mancante', 'Usare l\'area calcolata; dichiarare che non è verificabile col database.')
    if r.OK:
        return ('Confermato', 'Usare il bacino calcolato (area e parametri morfometrici).')
    if r.ID in anomali:
        return ('Valore DB anomalo', 'Correggere o confermare il valore del database (segnaposto o ≤ 0,01 km²).')
    if r.OK_altro:
        return ('Dipende dal metodo', 'Controllare in GIS su ortofoto quale percorso del corso d\'acqua è corretto; '
                'non scegliere il metodo ponte per ponte.')
    if pd.notna(dist[i]) and dist[i] <= 200:
        return ('Scarto di posizione ≤ 200 m', 'Verificare su ortofoto la coordinata del ponte rispetto all\'alveo; '
                'se va corretta, ricalcolare con la coordinata corretta.')
    if pd.notna(dist[i]):
        return ('Scarto di posizione > 200 m', 'Verificare coordinata e area nel database: probabile ponte su un '
                'altro corso d\'acqua o sezione di chiusura diversa.')
    return ('Nessun punto compatibile entro 5 km', 'Verificare l\'area nel database (possibile errore di valore).')


dec = [decisione(r, i) for i, r in d.iterrows()]
d['Esito'] = [x[0] for x in dec]
d['Azione'] = [x[1] for x in dec]

t = pd.DataFrame({
    'ID': d.ID, 'Gruppo (bacino)': d.Gruppo, 'X UTM33N': d.X_UTM33N, 'Y UTM33N': d.Y_UTM33N,
    'Area database (km²)': db, 'Area adottata (km²)': d.A_adottata, 'Fonte area adottata': d.Fonte,
    'Differenza (km²)': d.Diff_km2, 'Differenza %': d.Diff,
    'Compatibile (±15%)': np.where(db.notna(), d.OK, None),
    'Esito': d.Esito, 'Azione': d.Azione,
    'Area 30 m Whitebox (km²)': d.A_WBT_fill_D8_km2, 'Area 5 m originale (km²)': d.A_5m_originale_km2,
    'Spostamento min. per area compatibile (m)': dist,
})
sint = t.Esito.value_counts().rename_axis('Esito').reset_index(name='N. ponti')
regola = pd.DataFrame({'Regola': [
    "Area adottata: DEM 30 m (mosaico) con Whitebox riempimento + D8 e aggancio alla cella più vicina con area "
    "≥ 0,25 km²; se l'area così ottenuta è < 1 km², si usa l'area dello script originale sul DEM 5 m.",
    "La scelta tra 5 m e 30 m dipende solo dall'area calcolata, non da quella del database (soglia tra 0,5 e "
    "2 km²: 151-153 compatibili, risultato stabile).",
    "Compatibile: |area adottata − area DB| / area DB ≤ 15%.",
    "Esiti dei non compatibili in ordine di priorità: valore DB anomalo; dipende dal metodo; scarto di posizione "
    "≤ 200 m; scarto > 200 m; nessun punto compatibile entro 5 km.",
]})
with pd.ExcelWriter(sys.argv[3], engine='openpyxl') as w:
    t.to_excel(w, sheet_name='Decisioni', index=False)
    sint.to_excel(w, sheet_name='Sintesi', index=False)
    regola.to_excel(w, sheet_name='Regola', index=False)
    for ws in w.book.worksheets:
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(
                max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 70)
        ws.freeze_panes = 'B2' if ws.title == 'Decisioni' else 'A2'
    ws = w.book['Decisioni']
    j = list(t.columns).index('Differenza %') + 1
    for row in ws.iter_rows(min_row=2, min_col=j, max_col=j):
        row[0].number_format = '0.0%'
print(sint.to_string(index=False))
for e, g in t.groupby('Esito'):
    if e != 'Confermato':
        print(e, ':', g.ID.tolist())
