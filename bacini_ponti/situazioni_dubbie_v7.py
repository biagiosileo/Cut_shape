"""
Database delle situazioni dubbie, versione 7: due fogli, un colore per ogni significato.
  "Legenda e statistiche"  classi di compatibilita' (colore, criterio, numero, ID) e categorie delle situazioni
                           dubbie (colore, significato, numero, ID)
  "Database"               database originale dei 212 ponti (variabili delle ispezioni + variabili del codice),
                           senza colonne aggiunte; colori originali delle classi sulle colonne del codice
                           (celeste quasi compatibile, giallo non compatibile, grigio senza area); cella ID dei 36
                           ponti con situazioni dubbie in rosso chiaro
Uso: python situazioni_dubbie_v7.py <Database.xlsx originale> <situazioni_dubbie_212.csv (v4)> <out.xlsx>
"""
import sys

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

dbx, csv, out = sys.argv[1:4]
T = pd.read_csv(csv).set_index('ID')
CAT = [('canali di bonifica', 'C9D6F0', 'azzurro', 'pianura con canali: il canale non e\' rappresentato nel DEM e il '
        'bacino calcolato puo\' essere incompleto'),
       ('multi-asta', 'D9C3E9', 'viola', 'sotto il ponte passano piu\' aste; la sezione e\' sull\'asta indicata dalla '
        'relazione, da confermare'),
       ('area relazione non riproducibile', 'F4B6B6', 'rosso', 'nessuna sezione vicino al ponte riproduce l\'area '
        'della relazione'),
       ('quasi compatibile', 'FBD5A8', 'arancio', 'differenza di area contenuta, nessuna azione'),
       ('sezione lontana dal ponte', 'FFE066', 'giallo scuro', 'sezione di calcolo a piu\' di 50 m dal ponte del '
        'database'),
       ('coordinate database errate', 'BFE6E6', 'verde acqua', 'un estremo del ponte nel database e\' lontano dal '
        'ponte; sezione corretta'),
       ('anagrafica KML incongruente', 'A6A6A6', 'grigio scuro', 'nel KML il nome del ponte e\' associato a un\'altra '
        'progressiva; sezione corretta')]
DUBBIO = 'F4B6B6'  # unico colore delle situazioni dubbie (cella ID)

wb = load_workbook(dbx)
for n in wb.sheetnames[1:]:
    del wb[n]
ws = wb.worksheets[0]
ws.title = 'Database'
n = 0
for r in range(2, ws.max_row + 1):
    try:
        i = int(ws.cell(r, 1).value)
    except (TypeError, ValueError):
        continue
    n += 1
    if T.Categoria[i] != 'nessuna':
        ws.cell(r, 1).fill = PatternFill('solid', fgColor=DUBBIO)
        ws.cell(r, 1).font = Font(bold=True)
assert n == 212

L = wb.create_sheet('Legenda e statistiche', 0)
r = 1


def riga(vals, fill=None, bold=False):
    global r
    for k, v in enumerate(vals, 1):
        x = L.cell(r, k, v)
        x.alignment = Alignment(wrap_text=True, vertical='top')
        x.font = Font(bold=bold)
        if fill:
            x.fill = PatternFill('solid', fgColor=fill)
    r += 1


def ids(sel):
    return ', '.join(map(str, sorted(sel)))


L.cell(r, 1, 'Compatibilita\' delle aree (colori delle colonne dei parametri calcolati dal codice, foglio Database)'
       ).font = Font(bold=True, size=12); r += 1
riga(['Colore', 'Classe', 'Criterio (area calcolata rispetto a SUPERFICIE BACINO)', 'N. ponti', 'ID'], bold=True)
cls = [('bianco', 'compatibile', '|differenza %| <= 15%', None),
       ('celeste', 'quasi compatibile', '|differenza %| <= 25%, oppure |differenza| <= 0.1 km2 e |differenza %| <= 50%',
        'BDD7EE'),
       ('giallo', 'non compatibile', 'oltre le soglie precedenti', 'FFF2CC'),
       ('grigio', 'senza area relazione', 'SUPERFICIE BACINO assente nel database', 'D9D9D9')]
for col, c, crit, f in cls:
    sel = T.index[T.Classe == c]
    riga([col, c, crit, len(sel), 'tutti gli altri' if c == 'compatibile' else ids(sel)], f)
riga(['', 'totale', '', len(T), ''], bold=True)
r += 1
riga(['Per i ponti 21 e 190 la classe usa l\'area della relazione corretta per il refuso (13.33 e 2.167 km2). '
      'Pendenze in % (il codice le calcola in m/m).'])
L.merge_cells(start_row=r - 1, start_column=1, end_row=r - 1, end_column=5)
L.row_dimensions[r - 1].height = 30
r += 1
L.cell(r, 1, 'Situazioni dubbie (cella ID in rosso chiaro nel foglio Database)').font = Font(bold=True, size=12); r += 1
riga(['rosso chiaro', 'situazione dubbia', 'ponte da verificare; la categoria e\' indicata qui sotto', int((T.Categoria != 'nessuna').sum()), ids(T.index[T.Categoria != 'nessuna'])], DUBBIO)
r += 1
riga(['', 'Categoria', 'Significato', 'N. ponti', 'ID'], bold=True)
for c, h, nome, sig in CAT:
    sel = T.index[T.Categoria == c]
    riga(['', c, sig, len(sel), ids(sel)])
riga(['', 'totale', '', int((T.Categoria != 'nessuna').sum()), ''], bold=True)
r += 1
nc = T.index[T.Classe == 'non compatibile']
riga([f'I {len(nc)} non compatibili sono tutti tra le situazioni dubbie: '
      f'{ids(nc[T.Categoria[nc] == "canali di bonifica"])} canali di bonifica; '
      f'{ids(nc[T.Categoria[nc] == "area relazione non riproducibile"])} area della relazione non riproducibile.'])
L.merge_cells(start_row=r - 1, start_column=1, end_row=r - 1, end_column=5)
L.row_dimensions[r - 1].height = 30
for k, w in enumerate([13, 30, 62, 9, 48], 1):
    L.column_dimensions[get_column_letter(k)].width = w
L.page_setup.orientation = 'landscape'
L.sheet_properties.pageSetUpPr.fitToPage = True
L.page_setup.fitToWidth, L.page_setup.fitToHeight = 1, 0
wb.active = 0
wb.save(out)
print(out)
print(T.Classe.value_counts().to_string()); print(T.Categoria.value_counts().to_string())
