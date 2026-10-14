"""
Excel del controllo coordinate (una riga per ID 1-212) con l'effetto del punto
di aggancio sull'area (punto medio DB = input attuale, oppure punto KML).

Uso: python excel_coordinate.py <controllo_coordinate.csv> <controllo_coordinate.gpkg>
                               <punto_aggancio.csv> <out.xlsx>
"""
import sys

import numpy as np
import pandas as pd
import geopandas as gpd

TOL = 0.15
csv, gpkg, agg, out = sys.argv[1:5]
t = pd.read_csv(csv)
ini = gpd.read_file(gpkg, layer='db_inizio').set_index('ID')
fin = gpd.read_file(gpkg, layer='db_fine').set_index('ID')
kml = gpd.read_file(gpkg, layer='kml_abbinato').set_index('ID')
t['Dist_KML_DB_inizio_m'] = [kml.geometry[i].distance(ini.geometry[i]) if i in kml.index and i in ini.index
                             else np.nan for i in t.ID]
t['Dist_KML_DB_fine_m'] = [kml.geometry[i].distance(fin.geometry[i]) if i in kml.index and i in fin.index
                           else np.nan for i in t.ID]
a = pd.read_csv(agg)[['ID', 'A_medio', 'A_kml']]
t = t.merge(a, on='ID', how='left')
ok = lambda c: np.where(t.A_db_km2.notna(), (t[c] / t.A_db_km2 - 1).abs() <= TOL, None)
t['OK_punto_medio'] = ok('A_medio')
t['OK_punto_KML'] = ok('A_kml')

note = {
    90: 'Coordinata finale DB a 20 km dall\'iniziale (latitudine 40,2459 invece di ~40,4289?): errore di battitura.',
    143: 'Coordinata finale DB identica a quella dell\'ID 8: probabile copia-incolla.',
    83: 'Inizio e fine DB distanti 1,6 km; punto KML lontano da entrambi.',
    73: 'Inizio e fine DB distanti 1,1 km: punto medio fuori dall\'alveo; col punto KML l\'area torna (119,65 contro 119,74).',
    78: 'Inizio e fine DB distanti 1,1 km.',
    82: 'Inizio e fine DB distanti 1,2 km.',
    77: 'Punto KML a 27 m dalla coordinata DB dell\'ID 204: KML (o DB) di 77 e 204 scambiati.',
    204: 'Punto KML a 40 m dalla coordinata DB dell\'ID 77: KML (o DB) di 77 e 204 scambiati.',
}
t['Nota'] = t.ID.map(note).fillna('')
cols = {
    'ID': 'ID', 'Gruppo': 'Gruppo', 'SP': 'Strada', 'km': 'Progressiva', 'Nome_opera': 'Nome opera',
    'A_db_km2': 'Area DB (km²)', 'Coord_ini_testo': 'Coord. iniziali DB', 'Coord_fin_testo': 'Coord. finali DB',
    'Dist_inizio_fine_m': 'Distanza inizio-fine DB (m)',
    'Dist_input_medio_DB_m': 'Distanza input script - punto medio DB (m)',
    'KML_nome': 'Punto KML abbinato', 'KML_abbinamento': 'Abbinamento KML',
    'Dist_KML_DB_inizio_m': 'Distanza KML - inizio DB (m)', 'Dist_KML_DB_fine_m': 'Distanza KML - fine DB (m)',
    'Dist_input_KML_m': 'Distanza input script - KML (m)', 'KML_tracciato_m': 'Lunghezza tracciato KML (m)',
    'A_medio': 'Area 30 m dal punto medio (km²)', 'OK_punto_medio': 'Compatibile dal punto medio',
    'A_kml': 'Area 30 m dal punto KML (km²)', 'OK_punto_KML': 'Compatibile dal punto KML',
    'N_segnalazioni': 'N. segnalazioni', 'Segnalazioni': 'Segnalazioni', 'Nota': 'Nota',
}
x = t[list(cols)].rename(columns=cols).sort_values('ID')
d_if = t.Dist_inizio_fine_m
sint = pd.DataFrame([
    ('Input dello script = punto medio tra coordinata iniziale e finale DB', int((t.Dist_input_medio_DB_m < 1).sum())),
    ('Punto KML = coordinata iniziale DB (entro 5 m)', int((t.Dist_KML_DB_inizio_m < 5).sum())),
    ('Punto KML lontano oltre 20 m sia dall\'inizio sia dalla fine DB', int(((t.Dist_KML_DB_inizio_m > 20) & (t.Dist_KML_DB_fine_m > 20)).sum())),
    ('Distanza inizio-fine DB ≤ 50 m', int((d_if <= 50).sum())),
    ('Distanza inizio-fine DB 50-300 m', int(((d_if > 50) & (d_if <= 300)).sum())),
    ('Distanza inizio-fine DB > 300 m', int((d_if > 300).sum())),
    ('Ponti abbinati al KML per strada e progressiva', int((t.KML_abbinamento == 'strada+km').sum())),
    ('Compatibili ±15% agganciando dal punto medio (input attuale)', int((x['Compatibile dal punto medio'] == True).sum())),
    ('Compatibili ±15% agganciando dal punto KML', int((x['Compatibile dal punto KML'] == True).sum())),
], columns=['Controllo', 'N. ponti'])
with pd.ExcelWriter(out, engine='openpyxl') as w:
    x.to_excel(w, sheet_name='Ponti', index=False)
    sint.to_excel(w, sheet_name='Sintesi', index=False)
    x[x['N. segnalazioni'] > 0].to_excel(w, sheet_name='Segnalati', index=False)
    for ws in w.book.worksheets:
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(
                max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 60)
        ws.freeze_panes = 'B2'
print(sint.to_string(index=False))
