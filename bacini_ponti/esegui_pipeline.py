"""
Esecuzione completa del calcolo dei bacini dei 212 ponti (versione finale:
DEM 5 m ibrido con reticolo di riferimento inciso, soglia 0,1 km2, sezione
all'intersezione tra tracciato KML e reticolo).

I dati di ingresso sono solo letti; tutti i risultati vanno in <cartella_out>.
Ogni passo viene saltato se il suo risultato esiste gia' (esecuzione
ripartibile). Le finestre a 5 m sono elaborate una per processo per
contenere la memoria.

Uso:
  python esegui_pipeline.py <cartella_dati> <cartella_out>

<cartella_dati> deve contenere (nomi come forniti):
  dem30/            i 13 dem30_bacino_NN.tif (anche in sottocartelle)
  dem5/             i DTM a 5 m dtm5m_bacino_*.tif (anche in sottocartelle)
  cn5/              i Curve Number cn5m_bacino_NN.tif
  gruppi/           i 13 Bacino_NN_ponti.csv (colonne id, X, Y in WGS84)
  doc.kml           attraversamenti (punti di localizzazione e tracciati)
  Database_nuovo_11_08_2026.xlsx
  reticolo/reticolo_tagliato.shp   reticolo idrografico di riferimento
"""
import glob
import json
import os
import re
import subprocess
import sys

import pandas as pd

QUI = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
SOGLIA = '0.1'


def trova(pattern):
    f = sorted(glob.glob(pattern, recursive=True))
    if not f:
        sys.exit(f'File non trovato: {pattern}')
    return f[0]


def esegui(script, *args, env=None, salta_se=None):
    if salta_se and os.path.exists(salta_se):
        print(f'  [già fatto] {script}')
        return
    print(f'  {script} ...', flush=True)
    e = dict(os.environ, **(env or {}))
    r = subprocess.run([PY, os.path.join(QUI, script), *map(str, args)], env=e)
    if r.returncode != 0:
        sys.exit(f'Errore in {script} (codice {r.returncode})')


dati, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
if out == dati or out.startswith(dati + os.sep):
    sys.exit('La cartella dei risultati deve stare fuori dalla cartella dei dati (dati in sola lettura).')
os.makedirs(out, exist_ok=True)
lav = os.path.join(out, 'lavoro')
os.makedirs(lav, exist_ok=True)
db = trova(os.path.join(dati, '*.xlsx'))
kml = trova(os.path.join(dati, '*.kml'))
ret = trova(os.path.join(dati, 'reticolo', '**', '*.shp'))
cn5 = os.path.join(dati, 'cn5')
dem5 = os.path.join(dati, 'dem5')
print('Database:', db, '\nKML:', kml, '\nReticolo:', ret)

# 0. input dei gruppi in un unico file (ID del database, gruppo)
inp = os.path.join(lav, 'input_gruppi_tutti.csv')
if not os.path.exists(inp):
    fr = []
    for f in sorted(glob.glob(os.path.join(dati, 'gruppi', '**', 'Bacino_*_ponti.csv'), recursive=True)):
        d = pd.read_csv(f)
        d['file'] = int(re.search(r'Bacino_(\d+)', os.path.basename(f)).group(1))
        fr.append(d)
    a = pd.concat(fr).rename(columns={'id': 'ID', 'X': 'Longitude', 'Y': 'Latitude'}).sort_values('ID')
    if a.ID.duplicated().any():
        sys.exit(f'ID duplicati nei file dei gruppi: {sorted(a.ID[a.ID.duplicated()])}')
    a.to_csv(inp, index=False)
    print(f'  input: {len(a)} ponti da {len(fr)} gruppi')

print('1. Mosaico DEM 30 m')
mos30 = os.path.join(lav, 'dem30_mosaico.tif')
esegui('mosaico_dem30.py', os.path.join(dati, 'dem30'), mos30, salta_se=mos30)

print('2. Controllo coordinate (database, KML, input) e tracciati')
cdir = os.path.join(out, 'coordinate')
gpkg = os.path.join(cdir, 'controllo_coordinate.gpkg')
esegui('controllo_coordinate.py', db, kml, inp, cdir, salta_se=os.path.join(cdir, 'controllo_coordinate.csv'))
esegui('intersezione_tracciati.py', mos30, gpkg, cdir, salta_se=os.path.join(cdir, 'intersezione_tracciati.csv'))

print('3. Ingombro dei bacini a 30 m')
ingombro = os.path.join(lav, 'ingombro_bacini30.csv')
esegui('bacini30_ingombro.py', mos30, gpkg, ingombro, salta_se=ingombro)

print('4. Idrologia a 5 m (DEM ibrido + reticolo inciso), una finestra per processo')
run = os.path.join(lav, 'run5_inciso')
run_dem = os.path.join(lav, 'run5_non_inciso')
args5 = [dem5, mos30, ingombro, gpkg]
# numero di finestre: elenco senza elaborazione
r = subprocess.run([PY, os.path.join(QUI, 'dem5_finestre.py'), *args5, run], capture_output=True, text=True,
                   env=dict(os.environ, SOLO_ELENCO='1'))
n_fin = len(re.findall(r'^\s+finestra \d+:', r.stdout, flags=re.M))
for k in range(n_fin):
    # DEM inciso (per il flusso) e DEM non inciso (per quote e pendenze)
    esegui('dem5_finestre.py', *args5, run, env={'SOLO_FINESTRA': str(k), 'BRUCIA': ret, 'CANCELLA_DEM': '1'})
    esegui('dem5_finestre.py', *args5, run_dem, env={'SOLO_FINESTRA': str(k)},
           salta_se=os.path.join(run_dem, 'finestre', f'f{k:03d}_dem_ibrido.tif'))

print('5. Aggancio e scelta della soglia')
agg = os.path.join(run, 'aggancio_5m.csv')
esegui('aggancio_5m.py', os.path.join(run, 'toppe'), gpkg, agg, salta_se=agg)
esegui('scelta_soglia_5m.py', agg, run, salta_se=os.path.join(run, 'validazione_incrociata_5m.csv'))

print('6. Bacini finali e parametri morfometrici, una finestra per processo')
fin = os.path.join(run, 'finali')
for k in range(n_fin):
    esegui('bacini_5m_finali.py', run, agg, 'A_intersezione', SOGLIA, cn5, fin,
           env={'SOLO_FINESTRA': str(k), 'DEM_RUN': run_dem},
           salta_se=os.path.join(fin, 'parti', f'parametri_f{k:03d}.csv'))
esegui('bacini_5m_finali.py', run, agg, 'A_intersezione', SOGLIA, cn5, fin, env={'UNISCI': '1', 'SOLO_FINESTRA': ''})

print('7. Risultati, confronto col reticolo di riferimento, origine degli errori')
res = os.path.join(out, 'risultati')
nota = ('Incisione (stream burning): il reticolo idrografico di riferimento è abbassato di 5 m nel DEM prima del '
        'condizionamento; quote, pendenze e rilievo sono calcolati sul DEM non inciso.')
alt30 = os.path.join(lav, 'aree_30m_nessuna.csv')
if not os.path.exists(alt30):
    pd.DataFrame({'ID': range(1, 213), 'A_WBT_fill_D8_km2': float('nan')}).to_csv(alt30, index=False)
esegui('risultati_5m.py', run, SOGLIA, cdir, alt30, res, env={'NOTA_METODO': nota})
esegui('confronto_reticolo_riferimento.py', ret, mos30, gpkg, os.path.join(res, 'risultati_5m.gpkg'),
       os.path.join(res, 'Risultati_5m_ibrido.xlsx'), res)
esegui('origine_errore.py', os.path.join(res, 'Risultati_5m_ibrido.xlsx'), os.path.join(res, 'risultati_5m.gpkg'),
       gpkg, db, os.path.join(run, 'toppe'), os.path.join(out, 'verifica'),
       env={'RIF_CSV': os.path.join(res, 'confronto_reticolo_riferimento.csv'), 'RIF_SHP': ret})
print('Fatto. Risultati in', out)
