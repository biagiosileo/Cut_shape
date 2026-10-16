"""
Ripartisce i ponti in finestre piu' piccole per il codice dell'utente (pysheds richiede
circa 100 byte di RAM per cella): per ogni ponte l'ingombro del bacino finale a 5 m
piu' MARGINE_M, ritagliato dentro la finestra del calcolo finale (stessa griglia e
stesso DEM). I ponti il cui ingombro sta dentro quello di un altro ponte della stessa
finestra vanno nella stessa finestra; le finestre piccole vicine si uniscono finche'
l'unione resta sotto MAX_CELLE e non supera FATTORE volte la somma delle parti.
Le finestre sopra MAX_CELLE contengono solo i ponti con bacino grande, cosi' i ponti con
bacino piccolo restano in finestre leggere.

Uso: python finestre_codice_utente.py <finestre.json> <risultati_5m.gpkg> <out.json>
"""
import json
import sys

import geopandas as gpd

MARGINE_M = float(__import__('os').environ.get('MARGINE_M', '500'))
MAX_CELLE = 30e6
FATTORE = 1.5
C5 = 5.0

fj, rgpkg, out = sys.argv[1:4]
fin = json.load(open(fj))
bac = gpd.read_file(rgpkg, layer='bacini').set_index('ID').bounds


def celle(b):
    return (b[2] - b[0]) / C5 * (b[3] - b[1]) / C5


def ritaglia(b, w):
    # allinea alla griglia della finestra di origine e la limita ai suoi bordi
    x0, y0, x1, y1 = w['bounds']
    ox, oy = x0, y1
    import math
    xmin = max(x0, ox + math.floor((b[0] - ox) / C5) * C5)
    xmax = min(x1, ox + math.ceil((b[2] - ox) / C5) * C5)
    ymax = min(y1, oy - math.floor((oy - b[3]) / C5) * C5)
    ymin = max(y0, oy - math.ceil((oy - b[1]) / C5) * C5)
    return [xmin, ymin, xmax, ymax]


def unione(a, b):
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


nuove = []
for w in fin['finestre']:
    gr = []
    ids = sorted((int(i) for i in w['ponti']), key=lambda i: -celle(list(bac.loc[i])))
    for i in ids:
        r = bac.loc[i]
        b = ritaglia([r.minx - MARGINE_M, r.miny - MARGINE_M, r.maxx + MARGINE_M, r.maxy + MARGINE_M], w)
        for g in gr:
            # nelle finestre grandi solo ponti con bacino comparabile (almeno meta' della finestra)
            if (g['b'][0] <= b[0] and g['b'][1] <= b[1] and g['b'][2] >= b[2] and g['b'][3] >= b[3]
                    and celle(g['b']) <= max(MAX_CELLE, 2 * celle(b))):
                g['ponti'].append(i)
                break
        else:
            gr.append({'b': b, 'ponti': [i], 'somma': celle(b)})
    unito = True
    while unito:
        unito = False
        best = None
        for a in range(len(gr)):
            for c in range(a + 1, len(gr)):
                u = unione(gr[a]['b'], gr[c]['b'])
                cu = celle(u)
                if cu <= MAX_CELLE and cu <= FATTORE * (gr[a]['somma'] + gr[c]['somma']):
                    if best is None or cu < best[0]:
                        best = (cu, a, c, u)
        if best:
            cu, a, c, u = best
            gr[a] = {'b': u, 'ponti': gr[a]['ponti'] + gr[c]['ponti'], 'somma': gr[a]['somma'] + gr[c]['somma']}
            del gr[c]
            unito = True
    for g in gr:
        nuove.append({'origine': w['k'], 'bounds': g['b'], 'ponti': sorted(g['ponti'])})

nuove.sort(key=lambda g: min(g['ponti']))
for k, g in enumerate(nuove, 1):
    g['k'] = k
    g['shape'] = [int(round((g['bounds'][3] - g['bounds'][1]) / C5)), int(round((g['bounds'][2] - g['bounds'][0]) / C5))]
json.dump({'finestre': nuove}, open(out, 'w'), indent=1)
tot = sum(g['shape'][0] * g['shape'][1] for g in nuove)
print(len(nuove), 'finestre, celle totali (milioni):', round(tot / 1e6), '| max:',
      round(max(g['shape'][0] * g['shape'][1] for g in nuove) / 1e6), '| ponti:', sum(len(g['ponti']) for g in nuove))
for g in sorted(nuove, key=lambda g: -g['shape'][0] * g['shape'][1])[:12]:
    print(g['k'], g['origine'], round(g['shape'][0] * g['shape'][1] / 1e6, 1), g['ponti'])
