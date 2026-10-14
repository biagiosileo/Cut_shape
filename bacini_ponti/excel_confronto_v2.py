"""
Costruisce l'Excel di confronto (una riga per ID 1-212) a partire da
aree_dem30_v2.csv prodotto da bacini_dem30_v2.py.

Uso: python excel_confronto_v2.py <aree_dem30_v2.csv> <file_out.xlsx>
"""
import sys

import numpy as np
import pandas as pd

TOL = 0.15
src, out = sys.argv[1], sys.argv[2]
d = pd.read_csv(src).sort_values('ID')
db = d.A_db_km2


def ok(col):
    return ((d[col] / db - 1).abs() <= TOL) & db.notna()


ok30 = ok('A30_km2')
okg = ok('A30_guidata_300m_km2')
oka = ok('Asta_area_piu_vicina_km2')


def categoria(i):
    r = d.loc[i]
    if pd.isna(r.A_db_km2):
        return '0 - Area del database mancante'
    if ok30[i]:
        return '1 - Compatibile (regola principale a priori)'
    if okg[i]:
        return '2 - Corso compatibile entro 300 m dal ponte (aggancio ambiguo a 30 m)'
    if oka[i]:
        return '3 - Area compatibile spostando la sezione lungo il corso (vedi distanza)'
    if r.A_db_km2 > r.A30_km2:
        return '4 - Database più grande: nessun punto compatibile vicino'
    return '5 - Database più piccolo: nessun punto compatibile vicino'


d['Categoria_v2'] = [categoria(i) for i in d.index]
note = []
for _, r in d.iterrows():
    n = []
    if r.A_db_km2 == 0.10 and r.ID in (98, 99, 101, 103):
        n.append('area DB 0,10 km² ripetuta su 4 ponti: probabile segnaposto')
    if pd.notna(r.A_db_km2) and r.A_db_km2 <= 0.01:
        n.append('area DB ≤ 0,01 km²')
    if r.Bacino_troncato:
        n.append('bacino troncato dal limite del DEM: area = limite inferiore')
    note.append('; '.join(n))
d['Note'] = note

cols = {
    'ID': 'ID', 'Gruppo': 'Gruppo (bacino)', 'X_UTM33N': 'X UTM33N', 'Y_UTM33N': 'Y UTM33N',
    'A_db_km2': 'Area database (km²)',
    'A_5m_originale_km2': 'Area script originale 5 m (km²)', 'Err_5m_originale': 'Errore originale 5 m',
    'OK_5m_originale': 'Compatibile originale 5 m',
    'A30_vicino_km2': 'Area 30 m, regola originale (km²)', 'Err30_vicino': 'Errore 30 m regola originale',
    'A30_km2': 'Area 30 m, regola principale (km²)', 'Regola_principale': 'Regola applicata',
    'Snap30_m': 'Distanza snap regola principale (m)',
    'Err30': 'Errore 30 m regola principale', 'OK30': 'Compatibile 30 m regola principale',
    'A30_maxacc_90m_km2': 'Area 30 m, max acc. 90 m (km²)', 'A30_maxacc_150m_km2': 'Area 30 m, max acc. 150 m (km²)',
    'A30_guidata_300m_km2': 'Area 30 m, guidata 300 m (km²) [diagnostica]',
    'Snap30_guidata_300m_m': 'Distanza snap guidata (m)',
    'Asta_area_piu_vicina_km2': 'Area più vicina al DB lungo il corso ±5 km (km²)',
    'Asta_dist_area_DB_m': 'Distanza lungo il corso (m, + valle / − monte)',
    'Bacino_troncato': 'Bacino troncato dal DEM', 'Categoria_v2': 'Categoria v2', 'Note': 'Note',
}
t = d[list(cols)].rename(columns=cols)

regole = [('Script originale, DEM 5 m (riferimento)', 'A_5m_originale_km2'),
          ('DEM 30 m, regola originale (cella più vicina)', 'A30_vicino_km2'),
          ('DEM 30 m, max accumulo entro 30 m', 'A30_maxacc_30m_km2'),
          ('DEM 30 m, max accumulo entro 60 m', 'A30_maxacc_60m_km2'),
          ('DEM 30 m, regola principale a priori: max accumulo entro 60 m, altrimenti cella più vicina', 'A30_km2'),
          ('DEM 30 m, max accumulo entro 90 m', 'A30_maxacc_90m_km2'),
          ('DEM 30 m, max accumulo entro 150 m', 'A30_maxacc_150m_km2'),
          ('DEM 30 m, max accumulo entro 300 m', 'A30_maxacc_300m_km2'),
          ('DEM 30 m, guidata dal DB entro 300 m (solo diagnostica, non indipendente)', 'A30_guidata_300m_km2')]
n_db = int(db.notna().sum())
sens = pd.DataFrame([(lab, int(ok(c).sum()), n_db, ok(c).sum() / n_db) for lab, c in regole],
                    columns=['Regola', 'Compatibili (±15%)', 'Ponti con area DB', 'Quota'])
cat = d.Categoria_v2.value_counts().sort_index().rename_axis('Categoria v2').reset_index(name='N. ponti')
metodo = pd.DataFrame({'Metodo e limiti': [
    "DEM: mosaico dei 13 ritagli a 30 m (EPSG:32633), stessa griglia; condizionamento come lo script originale "
    "(fill_pits, fill_depressions, resolve_flats), D8, accumulo (pysheds).",
    "Area = accumulo della cella di chiusura × 900 m²; verificata uguale al conteggio delle celle di grid.catchment.",
    "Regola principale scelta prima di vedere i risultati: cella di reticolo (≥ 0,0125 km², come l'originale) con "
    "accumulo massimo entro 60 m dal ponte; se entro 60 m non c'è reticolo, la cella più vicina (5 ponti). Le altre regole sono analisi di sensibilità.",
    "La regola 'guidata' sceglie, entro 300 m, la cella con area più vicina al database: usa il dato da verificare, "
    "quindi indica solo se esiste un corso compatibile vicino; non è un risultato indipendente.",
    "Ricerca lungo il corso: dalla cella principale si scende lungo il D8 e si risale il ramo con accumulo maggiore "
    "per 5 km, cercando l'area più vicina a quella del database.",
    "Troncamento: il bacino confina con celle nodata o col bordo del mosaico sopra 20 m di quota (e 20 m sopra la "
    "sezione); la costa non conta. Nessun bacino risulta troncato nel mosaico.",
    "Limite: a 30 m il percorso del fiume ricostruito nelle piane può discostarsi di centinaia di metri dall'alveo "
    "reale, e i bacini sotto ~0,5 km² sono descritti da poche centinaia di celle.",
    "Coordinate dei ponti: longitudine/latitudine WGS84 di cmp.csv, trasformate in UTM 33N.",
]})

with pd.ExcelWriter(out, engine='openpyxl') as w:
    t.to_excel(w, sheet_name='Ponti', index=False)
    sens.to_excel(w, sheet_name='Sensibilità regole', index=False)
    cat.to_excel(w, sheet_name='Sintesi categorie', index=False)
    metodo.to_excel(w, sheet_name='Metodo e limiti', index=False)
    for ws in w.book.worksheets:
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(
                max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 70)
        ws.freeze_panes = 'B2' if ws.title == 'Ponti' else 'A2'
    ws = w.book['Ponti']
    pct = {c for c in t.columns if c.startswith('Errore')}
    for j, name in enumerate(t.columns, 1):
        if name in pct:
            for row in ws.iter_rows(min_row=2, min_col=j, max_col=j):
                row[0].number_format = '0.0%'
    ws2 = w.book['Sensibilità regole']
    for row in ws2.iter_rows(min_row=2, min_col=4, max_col=4):
        row[0].number_format = '0.0%'
print(sens.to_string(index=False))
print(cat.to_string(index=False))
