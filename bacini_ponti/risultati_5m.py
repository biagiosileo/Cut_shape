"""
Risultati finali dell'analisi a 5 m (DEM ibrido): Excel per ID 1-212 con area,
confronto col database, esito, tutte le segnalazioni e parametri morfometrici;
GeoPackage per QGIS con bacini, sezioni di chiusura ed esiti.

Uso: python risultati_5m.py <cartella_run5> <soglia_km2> <cartella_coordinate>
                            <aree_metodi_alternativi.csv> <out_dir>
"""
import os
import sys

import numpy as np
import pandas as pd
import geopandas as gpd

TOL = 0.15
run, soglia, cdir, alt30, out = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
os.makedirs(out, exist_ok=True)

agg = pd.read_csv(os.path.join(run, 'aggancio_5m.csv'))
agg = agg[np.isclose(agg.Soglia_km2, soglia)].set_index('ID')
par = pd.read_csv(os.path.join(run, 'finali', 'bacini_5m_parametri.csv')).set_index('ID')
cc = pd.read_csv(os.path.join(cdir, 'controllo_coordinate.csv')).set_index('ID')
a30 = pd.read_csv(alt30).set_index('ID')
a5o = pd.read_csv(os.path.join(cdir, '..', 'aree_dem30_soglia_0.25.csv')).set_index('ID')

ids = range(1, 213)
d = pd.DataFrame(index=pd.Index(ids, name='ID'))
d['Gruppo'] = cc.Gruppo
d['Strada'] = cc.SP
d['Progressiva'] = cc.km
d['Nome_opera'] = cc.Nome_opera
d['A_db'] = cc.A_db_km2
d['A_5m'] = par.A_km2
d['Diff_km2'] = d.A_5m - d.A_db
d['Diff_pct'] = (d.A_5m / d.A_db - 1)
d['Compatibile'] = np.where(d.A_db.notna(), d.Diff_pct.abs() <= TOL, None)
d['Quota_area_5m'] = par.Quota_area_DEM5m
d['Tipo_aggancio'] = agg.Tipo_intersezione
d['Dist_tracciato_reticolo_m'] = agg.Dist_tracciato_m
d['N_corsi_intersecati'] = agg.N_corsi_intersecati
for k, lab in (('input', 'input'), ('inizio', 'inizio_DB'), ('fine', 'fine_DB'), ('kml', 'KML')):
    d[f'A_{lab}'] = agg[f'A_{k}']
d['A_30m_Whitebox'] = a30.A_WBT_fill_D8_km2
d['A_5m_script_originale'] = a5o.A_5m_originale_km2
d['Dist_inizio_fine_m'] = cc.Dist_inizio_fine_m
d['Dist_KML_medio_DB_m'] = cc.Dist_medio_DB_KML_m

note_coord = {
    90: 'coordinata finale DB a 20 km dall\'iniziale (probabile errore di battitura nella latitudine)',
    143: 'coordinata finale DB identica a quella dell\'ID 8 (probabile copia-incolla)',
    77: 'punto KML/tracciato scambiato con quello dell\'ID 204',
    204: 'punto KML/tracciato scambiato con quello dell\'ID 77',
}
segnaposto = {98, 99, 101, 103}


def segnalazioni(i, r):
    s = []
    if pd.isna(r.A_db):
        s.append('area DB mancante')
    elif i in segnaposto:
        s.append('area DB 0,10 km² ripetuta su 4 ponti: probabile segnaposto')
    elif r.A_db <= 0.01:
        s.append(f'area DB anomala ({r.A_db:g} km²)')
    if i in note_coord:
        s.append(note_coord[i])
    if r.Dist_inizio_fine_m > 300:
        s.append(f'inizio e fine DB distanti {r.Dist_inizio_fine_m:.0f} m')
    elif r.Dist_inizio_fine_m > 150:
        s.append(f'inizio e fine DB distanti {r.Dist_inizio_fine_m:.0f} m (attraversamento lungo o coordinate imprecise)')
    if r.Dist_KML_medio_DB_m > 500 and i not in note_coord:
        s.append(f'punto KML a {r.Dist_KML_medio_DB_m:.0f} m dal punto medio DB')
    if r.Tipo_aggancio != 'sul tracciato':
        dd = '' if pd.isna(r.Dist_tracciato_reticolo_m) else f' ({r.Dist_tracciato_reticolo_m:.0f} m)'
        s.append(f'il tracciato non interseca il reticolo: {r.Tipo_aggancio}{dd}')
    if r.N_corsi_intersecati and r.N_corsi_intersecati > 1:
        s.append(f'il tracciato interseca {int(r.N_corsi_intersecati)} corsi: preso quello con area maggiore')
    if pd.notna(r.Quota_area_5m) and r.Quota_area_5m < 0.999:
        s.append(f'bacino ibrido: {100 * (1 - r.Quota_area_5m):.0f}% dell\'area da DEM 30 m')
    if r.Compatibile is False or r.Compatibile == False:  # noqa: E712
        alt = [lab for lab in ('input', 'inizio_DB', 'fine_DB', 'KML')
               if pd.notna(r[f'A_{lab}']) and abs(r[f'A_{lab}'] / r.A_db - 1) <= TOL]
        if alt:
            s.append('area compatibile agganciando da: ' + ', '.join(alt))
        if pd.notna(r.A_30m_Whitebox) and abs(r.A_30m_Whitebox / r.A_db - 1) <= TOL:
            s.append('compatibile col DEM a 30 m')
    return s


def esito(i, r, s):
    if pd.isna(r.A_db):
        return 'Area DB mancante'
    if r.Compatibile:
        return 'Compatibile'
    if i in segnaposto or r.A_db <= 0.01:
        return 'Non compatibile: valore DB anomalo'
    if i in note_coord or r.Dist_inizio_fine_m > 300:
        return 'Non compatibile: coordinate DB/KML incongruenti'
    if any(x.startswith('area compatibile agganciando') for x in s):
        return 'Non compatibile: dipende dal punto di aggancio'
    if r.Tipo_aggancio != 'sul tracciato':
        return 'Non compatibile: tracciato lontano dal reticolo'
    ratio = r.A_5m / r.A_db
    if 0.5 <= ratio <= 2:
        return 'Non compatibile: differenza moderata (15-100%)'
    return 'Non compatibile: differenza oltre un fattore 2 (DB o coordinate da verificare)'


segn = {i: segnalazioni(i, d.loc[i]) for i in d.index}
d['Esito'] = [esito(i, d.loc[i], segn[i]) for i in d.index]
d['N_segnalazioni'] = [len(segn[i]) for i in d.index]
d['Segnalazioni'] = ['; '.join(segn[i]) for i in d.index]

nomi = {
    'Gruppo': 'Gruppo', 'Strada': 'Strada', 'Progressiva': 'Progressiva', 'Nome_opera': 'Nome opera',
    'A_db': 'Area database (km²)', 'A_5m': 'Area calcolata 5 m (km²)', 'Diff_km2': 'Differenza (km²)',
    'Diff_pct': 'Differenza %', 'Compatibile': 'Compatibile (±15%)', 'Esito': 'Esito',
    'N_segnalazioni': 'N. segnalazioni', 'Segnalazioni': 'Segnalazioni',
    'Quota_area_5m': 'Quota area da DEM 5 m', 'Tipo_aggancio': 'Aggancio',
    'Dist_tracciato_reticolo_m': 'Distanza tracciato-reticolo (m)', 'N_corsi_intersecati': 'N. corsi intersecati',
    'A_input': 'Area 5 m da input (km²)', 'A_inizio_DB': 'Area 5 m da inizio DB (km²)',
    'A_fine_DB': 'Area 5 m da fine DB (km²)', 'A_KML': 'Area 5 m da punto KML (km²)',
    'A_30m_Whitebox': 'Area 30 m Whitebox (km²)', 'A_5m_script_originale': 'Area script originale 5 m (km²)',
    'Dist_inizio_fine_m': 'Distanza inizio-fine DB (m)', 'Dist_KML_medio_DB_m': 'Distanza KML - punto medio DB (m)',
}
ponti = d.reset_index()[['ID'] + list(nomi)].rename(columns=nomi)

morf_cols = {
    'A_km2': 'A (km²)', 'Quota_area_DEM5m': 'Quota area DEM 5 m', 'P_km': 'Perimetro P (km)',
    'L_km': 'Percorso di flusso più lungo L (km)', 'Lb_km': 'Lunghezza bacino Lb (km)',
    'Quota_min_m': 'Quota min (m)', 'Quota_max_m': 'Quota max (m)', 'AE_m': 'Quota media (m)',
    'Rilievo_m': 'Rilievo R (m)', 'S_media': 'Pendenza media S', 'CN_medio': 'CN medio',
    'Quota_area_con_CN': 'Quota area con CN', 'Pendenza_tratto_500m': 'Pendenza tratto 500 m',
    'Lunghezza_tratto_m': 'Lunghezza tratto (m)', 'FF': 'Form factor A/L²', 'Elongazione_Re': 'Elongazione Re',
    'Forma_Lb_Rf': 'Form factor A/Lb²', 'Shape_factor': 'Shape factor L/√A', 'Compattezza_Kc': 'Compattezza Kc',
    'Circolarita_Rc': 'Circolarità Rc', 'Melton': 'Melton', 'Integrale_ipsometrico': 'Integrale ipsometrico',
    'Rapporto_rilievo_Rr': 'Rapporto di rilievo R/Lb', 'Rilievo_relativo': 'Rilievo relativo R/P',
    'X_sezione': 'X sezione', 'Y_sezione': 'Y sezione',
}
morf = par.reindex(ids)[list(morf_cols)].rename(columns=morf_cols)
morf.insert(0, 'Area database (km²)', d.A_db)
morf.insert(1, 'Esito', d.Esito)
morf = morf.reset_index()

soglie = pd.read_csv(os.path.join(run, 'soglie_regole_5m.csv'))
cv = pd.read_csv(os.path.join(run, 'validazione_incrociata_5m.csv'))
sint = d.Esito.value_counts().rename_axis('Esito').reset_index(name='N. ponti')
metodo = pd.DataFrame({'Metodo': [
    'DEM: DTM 5 m dei 13 gruppi (47 file, 7.005 km² validi); dove il bacino esce dal 5 m, DEM 30 m ricampionato '
    '(bilineare) a 5 m solo per la parte esterna (bacino "ibrido", quota indicata per ogni ponte).',
    'Calcolo per finestre: ingombro del bacino a 30 m + 1 km; finestre condivise tra ponti dello stesso corso. '
    'Condizionamento: Whitebox fill_depressions; direzioni D8; accumulo.',
    f'Reticolo: celle con area contribuente ≥ {soglia:g} km². Soglia scelta con validazione incrociata '
    '(scelta su metà dei ponti, verifica sull\'altra metà, 500 ripetizioni).',
    'Sezione di chiusura: intersezione tra il tracciato del ponte nel doc.kml e il reticolo (se più corsi, quello '
    'con area maggiore); se il tracciato non interseca il reticolo, punto del reticolo più vicino al tracciato.',
    'Compatibilità: |area calcolata − area database| / area database ≤ 15%.',
    'Parametri: P dal poligono del bacino (buchi riempiti, semplificato a 2,5 m); L lungo il D8 fino alla sezione; '
    'Lb distanza in linea retta sezione-punto più lontano del confine; S massima pendenza discendente D8 sul DEM; '
    'CN medio solo su celle con CN > 0 (CN disponibile solo sul 5 m: vedi "Quota area con CN"); pendenza di tratto '
    'su 500 m centrati sulla sezione.',
    'Le coordinate non sono state corrette: le incongruenze sono segnalate per ID.',
]})
xlsx = os.path.join(out, 'Risultati_5m_ibrido.xlsx')
with pd.ExcelWriter(xlsx, engine='openpyxl') as w:
    ponti.to_excel(w, sheet_name='Ponti', index=False)
    morf.to_excel(w, sheet_name='Parametri morfometrici', index=False)
    ponti[ponti['N. segnalazioni'] > 0].to_excel(w, sheet_name='Segnalazioni', index=False)
    sint.to_excel(w, sheet_name='Sintesi esiti', index=False)
    soglie.to_excel(w, sheet_name='Soglie e punti', index=False)
    cv.to_excel(w, sheet_name='Validazione incrociata', index=False)
    metodo.to_excel(w, sheet_name='Metodo', index=False)
    for ws in w.book.worksheets:
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(
                max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 70)
        ws.freeze_panes = 'B2'
    ws = w.book['Ponti']
    j = list(ponti.columns).index('Differenza %') + 1
    for row in ws.iter_rows(min_row=2, min_col=j, max_col=j):
        row[0].number_format = '0.0%'

gp_in = os.path.join(run, 'finali', 'bacini_5m.gpkg')
gp = os.path.join(out, 'risultati_5m.gpkg')
if os.path.exists(gp):
    os.remove(gp)
att = d.reset_index()[['ID', 'A_db', 'A_5m', 'Diff_pct', 'Compatibile', 'Esito', 'Quota_area_5m', 'Tipo_aggancio',
                       'N_segnalazioni', 'Segnalazioni']]
att['Diff_pct'] = att.Diff_pct * 100
att['Compatibile'] = att.Compatibile.astype(str)
for lay in ('bacini', 'sezioni_chiusura'):
    g = gpd.read_file(gp_in, layer=lay)[['ID', 'geometry']].merge(att, on='ID')
    g.to_file(gp, layer=lay, driver='GPKG')
print(sint.to_string(index=False))
print('compatibili', int((d.Compatibile == True).sum()), '/', int(d.A_db.notna().sum()))  # noqa: E712
