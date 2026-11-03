"""
Documento breve (Word) sulle modifiche al codice pysheds_bridges.py iniziale e sui file di input della consegna
finale. Times New Roman 11 pt, testo giustificato, A4.

Uso: python documento_modifiche_codice.py <out.docx>
"""
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

out = sys.argv[1]
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
for m in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
    setattr(sec, m, Cm(2.0))
st = doc.styles['Normal']
st.font.name = 'Times New Roman'
st.font.size = Pt(11)
st.paragraph_format.space_after = Pt(6)


def par(t, bold=False, italic=False):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(t)
    r.bold, r.italic = bold, italic
    return p


def tabella(cols, righe, larghezze):
    t = doc.add_table(rows=1, cols=len(cols))
    t.style = 'Table Grid'
    for j, c in enumerate(cols):
        t.rows[0].cells[j].text = c
    for riga in righe:
        cells = t.add_row().cells
        for j, v in enumerate(riga):
            cells[j].text = v
    for i, r_ in enumerate(t.rows):
        for c in r_.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
                    r.font.name = 'Times New Roman'
                    r.bold = i == 0
                p.paragraph_format.keep_with_next = i == 0  # intestazione mai sola a fine pagina
    t.autofit = False
    for j, wd in enumerate(larghezze):
        t.columns[j].width = Cm(wd)
        for r_ in t.rows:
            r_.cells[j].width = Cm(wd)
    doc.add_paragraph()


par('Modifiche al codice di calcolo dei bacini dei ponti', bold=True)
par("Codice iniziale: pysheds_bridges.py (482 righe, DEM ASCII dell'area di Matera). Codice definitivo: "
    "pysheds_bridges_5m.py (633 righe con i commenti). Ogni modifica e' segnata nel codice con [MODIFICA 5 m]. "
    "Le righe indicate sono quelle dei due file.")

par('1. Modifiche al codice', bold=True)
tabella(
    ['N.', 'Riga iniziale → definitiva', 'Modifica', 'Perché'],
    [
        ['1', '39-41, 83-85 → 60-62, 170-198',
         "DEM unico GeoTIFF (dem5m_unico.tif) e CN (cn5m_unico.tif) letti a porzioni con la funzione "
         "leggi_porzione; quote da cm interi a metri (scala 0,01) e arrotondate al cm.",
         "Il DEM a 5 m dell'intera area (19.429 × 25.050 celle) non entra in memoria con riempimento, direzioni "
         "e accumulo; il codice iniziale leggeva per intero un DEM ASCII piccolo."],
        ['2', '- → 109-155',
         "Modalità generale: lanciato senza argomenti, lo script rilancia se stesso una volta per porzione "
         "(processo separato), salta le porzioni già fatte e riunisce i risultati.",
         "La memoria si libera tra una porzione e l'altra; un lancio interrotto riprende da dove era arrivato; "
         "in uscita restano gli stessi tre file del codice iniziale."],
        ['3', '327 → 449; ponti.csv',
         "ponti.csv ha in più le colonne porzione, xmin, ymin, xmax, ymax; ogni processo elabora solo i ponti "
         "della sua porzione.",
         "Ogni porzione contiene per intero i bacini dei suoi ponti (56 porzioni)."],
        ['4', '58 → 78', 'ACC_THRESHOLD da 500 a 4000 celle (0,1 km²).',
         "A 5 m 500 celle sono 0,0125 km²: il reticolo è troppo fitto e il punto si aggancia a fossi laterali. "
         "4000 celle è la soglia con più ponti compatibili, scelta con validazione incrociata sui ponti con "
         "area nel database."],
        ['5', '349 → 476-481',
         "Soglia di aggancio per singolo ponte: colonna facoltativa soglia di ponti.csv.",
         "10 ponti stanno su fossi più piccoli di 0,1 km² (64, 103, 116, 117, 129, 151, 153, 168, 177, 202): con "
         "4000 celle si aggancerebbero al corso d'acqua sbagliato."],
        ['6', '72 → 92', 'Avviso di snap da 50 a 10 m.',
         "Le coordinate di ponti.csv sono già sul tracciato del ponte e sul reticolo: uno spostamento oltre "
         "10 m (2 celle) indica un aggancio da controllare."],
        ['7', '98 → 216', 'resolve_flats con eps=1e-6 e max_iter=10000 (default 1e-5 e 1000).',
         "Sulle grandi aree piatte i valori di default innalzano il DEM di oltre 1 cm e creano pozzi "
         "artificiali che interrompono il bacino (ponti 24 e 25)."],
        ['8', '- → 49; 424 → 570',
         "np.in1d = np.isin se manca; np.asarray(basin).astype(np.uint8).",
         "Compatibilità con numpy 2: pysheds usa np.in1d, rimosso in numpy 2; la conversione diretta del "
         "bacino dava un errore di tipo."],
        ['9', '- → 500-505',
         "Avviso se il bacino tocca il bordo della porzione.",
         "Un bacino che arriva al bordo può essere troncato (caso del ponte 6): l'avviso indica di allargare "
         "la porzione."],
        ['10', '173, 468, 479 → 294, 618-631, 113-153',
         "Risultati per porzione in porzioni/; poi unione in 'parametri morfologici.csv' (ordinato per ID), "
         "bacini_afferenti.geojson e reticolo_idrografico.geojson (rami dissolti, con id_ramo e lung_m).",
         "Le porzioni si sovrappongono: il reticolo unito compare una volta sola; l'ID del database (1-212) resta "
         "invariato in tutti gli output."],
    ],
    [0.9, 3.3, 6.0, 6.8])
par("Non sono cambiati: condizionamento del DEM (fill_pits, fill_depressions, resolve_flats), direzioni D8, "
    "accumulo, delineazione del bacino, formule di tutti i parametri (area, pendenza e quota media, CN, "
    "percorso di flusso più lungo, perimetro, Melton, integrale ipsometrico, pendenza di tratto, ecc.) e colonne "
    "del CSV in uscita. Le formule sono state verificate a parte sui risultati.")

par('2. Modifiche ai file di input', bold=True)
par("DEM unico v3 = DEM unico originale + 6 patch sulla stessa griglia (patch_*.tif, applicate da esegui.py; il "
    "risultato è identico cella per cella a dem5m_unico_v3.tif):").paragraph_format.keep_with_next = True
tabella(
    ['Patch', 'Cosa fa', 'Ponti'],
    [
        ['patch_alto_Agri', "Celle senza dato dell'alto Agri riempite con il DEM Copernicus GLO-30 (correzione "
                            "mediana 1,44 m) e reticolo di riferimento inciso di 5 m.", '6 (Agri)'],
        ['patch_costa_NovaSiri, _Scanzano, _Bernalda',
         "Celle senza dato della costa riempite con le tavole DTM a 5 m, poi con Copernicus; il mare resta senza "
         "dato.", '113, 155'],
        ['patch_tombino_105, _tombino_198', "Taglio del rilevato stradale in corrispondenza del tombino.",
         '105, 198'],
    ],
    [4.5, 9.5, 3.0])
par("ponti.csv (212 righe, ID del database 1-212, stesso ordine): porzioni nuove o allargate per i bacini "
    "troncati (porzione_53-58, porzione_69 per il ponte 6, porzione_70 per il 113, porzione_71 per il 155); "
    "sezioni ricollocate sul tracciato del ponte nel KML (ponti delle porzioni 62-68); sezioni "
    "spostate dopo il confronto con le relazioni di ispezione (105, 107, 108, 109, 111, 196); soglia ridotta per "
    "i 10 ponti del punto 5.")

par('3. Risultato', bold=True)
par("Con il codice e gli input della consegna: 186 ponti compatibili (±15%), 13 quasi compatibili, 8 non "
    "compatibili e 5 senza area nel database (aree del database corrette per i refusi dei ponti 21 e 190). Gli 8 "
    "non compatibili sono descritti nel report dedicato.")
doc.save(out)
print('ok', out)
