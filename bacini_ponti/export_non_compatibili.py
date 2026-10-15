"""
Esporta i ponti non compatibili (ID del database) in:
  - un Excel con un unico foglio che riunisce area, esito, probabile origine
    dell'errore, criticita' dal database, reticolo di riferimento, aste ISPRA,
    segnalazioni e parametri morfometrici;
  - shapefile (EPSG:32633): punti dei ponti, sezioni di chiusura, bacini;
    nomi dei campi abbreviati a 10 caratteri (legenda in un file di testo).

Uso: python export_non_compatibili.py <Risultati_5m_ibrido.xlsx (con origine)> <Criticita_da_database.xlsx>
        <confronto_aste_ISPRA.csv> <risultati_5m.gpkg> <controllo_coordinate.gpkg> <out_dir>
"""
import os
import sys

import pandas as pd
import geopandas as gpd

xlsx, crit, ispra, rgpkg, cgpkg, out = sys.argv[1:7]
os.makedirs(out, exist_ok=True)
P = pd.read_excel(xlsx, sheet_name='Ponti').set_index('ID')
M = pd.read_excel(xlsx, sheet_name='Parametri morfometrici').set_index('ID')
K = pd.read_excel(crit, sheet_name='Non compatibili').set_index('ID')
I = pd.read_csv(ispra).set_index('ID')
nc = P.index[(P['Compatibile (±15%)'] != True) & P['Area database (km²)'].notna()]  # noqa: E712

orig = P['Probabile origine errore'].copy()
# correzioni da informazioni non usate nella classificazione automatica
# (nome dell'opera e tipologia di reticolo nel database, aste ISPRA)
CORR = {107: 'Calcolo: alveo abbandonato (Bradano Vecchio, aste ISPRA)',
        108: 'Calcolo: alveo abbandonato (Bradano Vecchio, aste ISPRA)',
        164: 'Calcolo: canale artificiale di scolo (DB), bacino non ricostruibile dal DEM',
        21: 'Database: opera su ferrovia (DB), area non riferibile al fosso attraversato'}
for i, v in CORR.items():
    if i in nc:
        orig[i] = v

T = pd.DataFrame(index=nc)
T['Gruppo'] = P.Gruppo
T['Strada'] = P.Strada
T['Progressiva'] = P.Progressiva
T['Nome opera'] = K['Nome opera']
T['Area database (km²)'] = P['Area database (km²)']
T['Area calcolata 5 m (km²)'] = P['Area calcolata 5 m (km²)']
T['Differenza (km²)'] = P['Differenza (km²)']
T['Differenza %'] = P['Differenza %']
T['Esito'] = P.Esito
T['Probabile origine errore'] = orig
T['Criticità dal database'] = K['Criticità dal database']
T['Tipologia reticolo (DB)'] = K['Tipologia reticolo']
T['Tipologia alveo (DB)'] = K['Tipologia alveo']
T['Pendenza tratto % (DB)'] = K['Pendenza tratto %']
T['Larghezza alveo inciso (m, DB)'] = P['Larghezza alveo inciso DB (m)']
T['Area stimata da larghezza alveo (km²)'] = P['Area stimata da larghezza alveo (km²)']
T['Corso reticolo regionale'] = P.get('Corso di riferimento attraversato')
T['Sezione sul corso regionale'] = P.get('Sezione sul corso di riferimento')
T['Asta ISPRA 1:250.000'] = I.ISPRA_nome
T['Distanza asta ISPRA (m)'] = I.ISPRA_dist_m
T['Coerenza monte-valle'] = P['Coerenza monte-valle']
T['Aggancio'] = P.Aggancio
T['Quota area da DEM 5 m'] = P['Quota area da DEM 5 m']
T['Distanza inizio-fine DB (m)'] = P['Distanza inizio-fine DB (m)']
T['Segnalazioni'] = P.Segnalazioni
for c in ('Perimetro P (km)', 'Percorso di flusso più lungo L (km)', 'Lunghezza bacino Lb (km)', 'Rilievo R (m)',
          'Quota media (m)', 'Pendenza media S', 'CN medio', 'Quota area con CN', 'Pendenza tratto 500 m'):
    T[c] = M[c]
T['Verificato'] = ''
T['Esito verifica'] = ''
T['Note verifica'] = ''
T = T.reset_index().rename(columns={'index': 'ID'})
xo = os.path.join(out, 'Ponti_non_compatibili.xlsx')
with pd.ExcelWriter(xo, engine='openpyxl') as w:
    T.to_excel(w, sheet_name='Ponti non compatibili', index=False)
    ws = w.sheets['Ponti non compatibili']
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(
            max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 55)
    ws.freeze_panes = 'B2'
    ws.auto_filter.ref = ws.dimensions
    j = list(T.columns).index('Differenza %') + 1
    for row in ws.iter_rows(min_row=2, min_col=j, max_col=j):
        row[0].number_format = '0.0%'

campi = {'ID': 'ID', 'Gruppo': 'Gruppo', 'Strada': 'Strada', 'Progressiva': 'Progr',
         'Area database (km²)': 'A_DB_km2', 'Area calcolata 5 m (km²)': 'A_calc_km2', 'Differenza %': 'Diff_pct',
         'Probabile origine errore': 'Origine', 'Criticità dal database': 'Critic_DB',
         'Corso reticolo regionale': 'Corso_reg', 'Asta ISPRA 1:250.000': 'Asta_ISPRA',
         'Segnalazioni': 'Segnalaz'}
att = T[list(campi)].rename(columns=campi)
att['Diff_pct'] = att.Diff_pct * 100
for c in ('Origine', 'Critic_DB', 'Segnalaz', 'Corso_reg', 'Asta_ISPRA', 'Strada', 'Progr'):
    att[c] = att[c].fillna('').astype(str).str.slice(0, 254)
pts = gpd.read_file(cgpkg, layer='input_script').set_index('ID').geometry
sez = gpd.read_file(rgpkg, layer='sezioni_chiusura').set_index('ID').geometry
bac = gpd.read_file(rgpkg, layer='bacini').set_index('ID').geometry
for nome, geo in (('ponti_non_compatibili', pts), ('sezioni_chiusura_non_compatibili', sez),
                  ('bacini_non_compatibili', bac)):
    g = gpd.GeoDataFrame(att.merge(geo.rename('geometry'), left_on='ID', right_index=True), crs=32633)
    g.to_file(os.path.join(out, f'{nome}.shp'), encoding='utf-8')
with open(os.path.join(out, 'LEGGIMI_campi_shapefile.txt'), 'w', encoding='utf-8') as f:
    f.write('Shapefile dei ponti non compatibili (EPSG:32633 - WGS 84 / UTM 33N). ID = ID del database.\n'
            'ponti_non_compatibili: punto di input dello script (punto medio inizio-fine DB)\n'
            'sezioni_chiusura_non_compatibili: sezione dove e\' stato chiuso il bacino\n'
            'bacini_non_compatibili: bacino calcolato (DEM 5 m ibrido, reticolo di riferimento inciso)\n\n'
            'Campi:\n' + '\n'.join(f'  {v:<10} = {k}' for k, v in campi.items()) +
            '\n\nTutti gli altri dati sono nell\'Excel Ponti_non_compatibili.xlsx (stesso ID).\n')
print(len(T), 'ponti non compatibili esportati')
