"""
Analisi degli incroci tracciato-reticolo calcolati con il codice invariato sul DEM a 5 m (crea_punti_incroci_5m.py
+ pysheds_bridges_5m.py): per ogni ponte quante aste passano sotto il ponte, con quale area, quale e' stata usata
e come e' stato trattato il ponte.

Uso: python analisi_incroci_5m.py <cartella incroci_5m> <situazioni_dubbie_212.csv> <ponti_iniziali.shp>
        <ponti.csv finale> <out_dir>
"""
import os
import re
import sys

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

STESSA_ASTA = 0.05     # aree entro il 5%: stessa asta (il tracciato la attraversa piu' volte)
MIN_ALTRA_KM2 = 0.1    # aste piu' piccole di cosi' non contano come "altra asta"

cart, tab, shp, ponti, out = sys.argv[1:6]
os.makedirs(out, exist_ok=True)
T = pd.read_csv(tab).set_index('ID')
I = gpd.read_file(shp).set_index('ID')
pc = pd.read_csv(ponti).set_index('id')
Q = pd.read_csv(os.path.join(cart, 'incroci_punti.csv'))
E = pd.read_csv(os.path.join(cart, 'incroci_ponti.csv')).set_index('ID')
Pm = pd.read_csv(os.path.join(cart, 'parametri morfologici.csv'))
Pm['ID'] = Pm.ID.astype(int)
Q = Q.merge(Pm[['ID', 'A_km2', 'Snap_Distance_m']].rename(columns={'ID': 'id'}), on='id', how='left')
log = open(os.path.join(cart, 'run.log'), encoding='utf-8', errors='replace').read()
tronc = {int(float(m)) for m in re.findall(r'Ponte ([\d.]+): ATTENZIONE - il bacino arriva al bordo', log)}
Q['Troncato'] = Q.id.isin(tronc)
MULTI = {107, 108, 109, 111, 196}


def trattamento(i):
    m = str(I.motivo.get(i, '') or '')
    if i in MULTI:
        return 'sezione sull\'asta indicata dalla relazione di ispezione (multi-asta)'
    if 'tombino' in m:
        return 'sezione sul taglio del tombino'
    if not pd.isna(pc.soglia.get(i)):
        return 'fosso piccolo: sezione sul fosso con soglia di aggancio ridotta'
    if 'tracciato' in m:
        return 'punto spostato sul tracciato KML, asta con area maggiore'
    return 'punto iniziale gia\' sul corso d\'acqua attraversato'


righe = []
for i in sorted(T.index):
    a0 = T.A_calcolata_km2[i]
    q = Q[Q.ID_ponte == i].sort_values('A_km2', ascending=False)
    r = {'ID': i, 'Nome_opera': T.Nome_opera[i], 'A_relazione_km2': T.A_relazione_km2[i], 'A_codice_km2': a0,
         'Classe': T.Classe[i], 'Caso_dubbio': T.Categoria[i], 'Trattamento': trattamento(i),
         'Tracciato': E.Tracciato.get(i, 'assente'), 'Lungh_tracciato_m': E.Lungh_m.get(i),
         'N_incroci': len(q)}
    # aste distinte: aree che differiscono piu' del 5%
    aste = []
    for _, x in q.iterrows():
        if pd.isna(x.A_km2):
            continue
        for s in aste:
            if abs(x.A_km2 - s['A']) <= STESSA_ASTA * max(x.A_km2, s['A']):
                s['n'] += 1; s['dist'] = min(s['dist'], x.Dist_punto_ponte_m); s['tr'] |= bool(x.Troncato)
                break
        else:
            aste.append({'A': x.A_km2, 'n': 1, 'dist': x.Dist_punto_ponte_m, 'tr': bool(x.Troncato)})
    usata = [s for s in aste if abs(s['A'] - a0) <= STESSA_ASTA * max(s['A'], a0)]
    altre = [s for s in aste if s not in usata and s['A'] >= MIN_ALTRA_KM2]
    r['Aste_sotto_il_ponte'] = len(usata[:1]) + len(altre) if aste else 0
    r['Asta_usata_sul_tracciato'] = 'si' if usata else 'no'
    r['Aree_aste_km2'] = '; '.join(f"{s['A']:.3f}{' (troncata)' if s['tr'] else ''} a {s['dist']:.0f} m"
                                   for s in aste)
    piu_grandi = [s for s in altre if s['A'] > a0]
    piu_piccole = [s for s in altre if s['A'] < a0]
    r['A_asta_maggiore_non_usata_km2'] = round(max(s['A'] for s in piu_grandi), 3) if piu_grandi else None
    if not aste:
        esito = 'il tracciato non incrocia il reticolo a 0.1 km2'
    elif piu_grandi:
        esito = 'sotto il ponte passa un\'asta piu\' grande di quella usata'
    elif piu_piccole:
        esito = 'sotto il ponte passa anche un\'asta piu\' piccola (usata la principale)'
    elif not usata:
        esito = 'l\'asta sul tracciato ha area diversa da quella usata'
    else:
        esito = 'una sola asta sotto il ponte, quella usata'
    r['Esito'] = esito
    righe.append(r)

R = pd.DataFrame(righe)
R.to_csv(os.path.join(out, 'aste_sotto_i_ponti_5m.csv'), index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 80)
print(R.Esito.value_counts())
print(pd.crosstab(R.Esito, R.Trattamento))
for e in R.Esito.unique():
    if e.startswith('una sola'):
        continue
    print('\n==', e)
    print(R[R.Esito == e][['ID', 'A_relazione_km2', 'A_codice_km2', 'Classe', 'Caso_dubbio', 'Trattamento',
                           'Aree_aste_km2']].to_string(index=False))
