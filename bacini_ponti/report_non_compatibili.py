"""
Report breve sui ponti non compatibili (Word, Times New Roman 11 pt, testo giustificato, pagina orizzontale).

Uso: python report_non_compatibili.py <parametri.csv> <Database.xlsx> <note_relazioni_consolidate.csv> <out.docx>
"""
import sys

import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

pcsv, dbx, ncsv, out = sys.argv[1:5]
U = pd.read_csv(pcsv)
U['ID'] = U.ID.astype(int)
U = U.set_index('ID')
db = pd.read_excel(dbx).rename(columns={'Unnamed: 0': 'ID'})
db = db[pd.to_numeric(db.ID, errors='coerce').notna()]
db['ID'] = db.ID.astype(int)
db = db.set_index('ID')
adb = pd.to_numeric(db['SUPERFICIE BACINO (km2)'], errors='coerce')
N = pd.read_csv(ncsv).set_index('ID')

DIAG = {
    13: ('DEM: canali di bonifica',
         "In pianura il Toccacielo scorre in un canale a circa 300 m dal ponte e il DEM non lo collega al ponte. "
         "La relazione (bacino collinare, quota media 182 m) conferma l'area del database.",
         'Reticolo dei canali (Consorzio di Bonifica o CTR) da incidere nel DEM.'),
    154: ('DEM: canali di bonifica', 'Stesso tratto e stessa relazione del ponte 13 (SP107, 30 m di distanza).',
          'Come il 13.'),
    19: ('Relazione: sezione lontana dal ponte',
         "La sezione che riproduce area, quota e pendenza della relazione e' a circa 925 m dal ponte; il bacino al "
         "ponte ha la stessa quota e pendenza ma un'area 4,8 volte minore.",
         "Verificare sull'immagine della relazione dove e' stato chiuso il bacino; chiarire con chi ha compilato il DB."),
    117: ('Relazione: sezione lontana dal ponte',
          "La sezione che riproduce la relazione e' a circa 460 m dal ponte, verso il ponte SP14 km 17+200 (61).",
          "Verificare la chiusura del bacino nella relazione e le aree dei ponti SP14 km 17+200-17+800."),
    118: ('Relazione: sezione lontana dal ponte',
          "La sezione che riproduce la relazione e' a circa 900 m dal ponte; l'area calcolata (0,751) coincide con "
          "l'area DB del ponte 61 (0,75).",
          "Come il 117: possibile scambio di aree tra i ponti del tratto SP14."),
    58: ('Relazione non riproducibile',
         "La quota media coincide con il bacino al ponte (260 m) ma l'area e' 22 volte maggiore; nessuna sezione "
         "entro 1 km riproduce i tre valori.", 'Chiarire con chi ha compilato il DB.'),
    164: ('Relazione non riproducibile',
          "Il ponte scavalca il torrente Iesce (OSM e reticolo di riferimento): 215,6 km². I valori della relazione "
          "(0,75 km², 218 m, 26%) non corrispondono a nessuna sezione entro 2 km.",
          "Verificare l'immagine del bacino nella relazione; chiarire con chi ha compilato il DB."),
    174: ('Relazione non riproducibile',
          "Nessuna sezione entro 2 km ha la quota media della relazione (196 m): i bacini vicini hanno quote di 380-400 m.",
          "Verificare l'immagine del bacino nella relazione; chiarire con chi ha compilato il DB."),
}

doc = Document()
sec = doc.sections[0]
sec.orientation = WD_ORIENT.LANDSCAPE
sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)  # A4 orizzontale
for m in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
    setattr(sec, m, Cm(1.8))
st = doc.styles['Normal']
st.font.name = 'Times New Roman'
st.font.size = Pt(11)
st.paragraph_format.space_after = Pt(6)


def par(t, bold=False):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.add_run(t).bold = bold


par('Ponti non compatibili – nota di sintesi', bold=True)
par("Dopo le correzioni (porzioni di DEM, sezione sul tracciato del ponte, DEM esteso e tombini, confronto con le "
    "relazioni di ispezione) i ponti sono 186 compatibili, 13 quasi compatibili, 8 non compatibili e 5 senza area nel "
    "database. Per gli 8 non compatibili il confronto tra area, quota media e pendenza media della relazione e del "
    "bacino calcolato porta a tre situazioni: un limite del DEM in pianura (2 ponti), un bacino della relazione chiuso "
    "lontano dal ponte (3 ponti), valori della relazione non riproducibili da nessuna sezione vicina (3 ponti).")
cols = ['ID', 'Strada / opera', 'Area DB (km²)', 'Area calcolata (km²)', 'Diff.', 'Relazione: quota / pendenza',
        'Calcolato: quota / pendenza', 'Diagnosi', 'Cosa e\' emerso', 'Cosa serve']
t = doc.add_table(rows=1, cols=len(cols))
t.style = 'Table Grid'
for j, c in enumerate(cols):
    t.rows[0].cells[j].text = c
f = lambda v, d=3: f'{v:,.{d}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
for i in [13, 154, 19, 117, 118, 58, 164, 174]:
    n = N.loc[i]
    nome = str(db.loc[i, 'Nome opera']).strip()
    nome = '' if nome in ('-', 'nan') else ' – ' + nome
    g, e, a = DIAG[i]
    row = [str(i), f"{db.loc[i, 'NUOVA NUMERAZIONE']} km {db.loc[i, 'Progressiva km']}{nome}", f(adb[i]), f(U.A_km2[i]),
           f'{100 * (U.A_km2[i] / adb[i] - 1):+.0f}%', f'{f(n.AE_rel, 0)} m / {f(n.S_rel, 1)}%',
           f'{f(U.AE_m[i], 0)} m / {f(100 * U.S[i], 1)}%', g, e, a]
    cells = t.add_row().cells
    for j, v in enumerate(row):
        cells[j].text = v
for r_ in t.rows:
    for c in r_.cells:
        for p in c.paragraphs:
            for r in p.runs:
                r.font.size = Pt(8)
                r.font.name = 'Times New Roman'
for c in t.rows[0].cells:
    c.paragraphs[0].runs[0].bold = True
t.autofit = False
for j, wd in enumerate([0.9, 3.2, 1.5, 1.6, 1.2, 2.2, 2.2, 2.6, 7.4, 4.9]):
    t.columns[j].width = Cm(wd)
    for r_ in t.rows:
        r_.cells[j].width = Cm(wd)
doc.add_paragraph()
par('Azioni proposte', bold=True)
par("1) 13 e 154: acquisire il reticolo dei canali di bonifica della piana di Nova Siri e inciderlo nel DEM, come per il "
    "reticolo di riferimento; il valore del database e' coerente con la relazione.")
par("2) 19, 117, 118: confrontare l'immagine \"Bacino sotteso\" delle relazioni con il bacino calcolato per verificare "
    "dove e' stata chiusa la sezione; per il tratto SP14 km 17+200-17+800 (61, 117, 118) verificare un possibile scambio "
    "delle aree tra i ponti.")
par("3) 58, 164, 174: chiedere a chi ha compilato il database e le relazioni come e da quale punto sono stati calcolati "
    "i bacini; in attesa, si mantiene l'area calcolata con la segnalazione.")
doc.save(out)
print('ok', out)
