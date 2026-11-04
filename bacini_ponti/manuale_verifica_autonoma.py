"""
Manuale illustrato (Word + PDF) per la VERIFICA AUTONOMA di tutte le variabili morfologiche con QGIS 3.34 + GRASS.
Input: shape ponti_analisi (tutti i ponti), DEM unito (.tif), Curve Number (.tif). Prima si calcola tutto in QGIS e a
mano; il confronto con il codice si fa solo alla fine (Parte D). Figure: schermate reali della prova sul ponte 100.

Uso: python manuale_verifica_autonoma.py <schermate A> <schermate B> <schermate nuove> <out.docx>
"""
import os
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

SA, SB, SN, out = sys.argv[1:5]
CROP = {'03a_menu_raster_estrazione.png': (300, 50, 1000, 330), '04a_menu_raster_conversione.png': (300, 50, 1000, 330),
        '05a_strumenti_processing_rwatershed.png': (0, 0, 311, 230), '10d_tabella_attributi.png': (0, 0, 1460, 95),
        'B1d_tabella_ponte.png': (0, 0, 640, 60), 'NB1c_tabella_coordinate.png': (0, 0, 1220, 62)}
NFIG = [0]

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
for m in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
    setattr(sec, m, Cm(2.0))
for nome in ('Normal', 'List Number', 'List Bullet'):
    st = doc.styles[nome]
    st.font.name = 'Times New Roman'
    st.font.size = Pt(11)
    st.paragraph_format.space_after = Pt(4)
for liv, dim in ((1, 15), (2, 12.5), (3, 11.5)):
    h = doc.styles[f'Heading {liv}']
    h.font.name, h.font.size, h.font.bold = 'Times New Roman', Pt(dim), True
    h.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    h.paragraph_format.space_before = Pt(12 if liv == 1 else 9)
    h.paragraph_format.keep_with_next = True


def par(t, bold=False, italic=False, size=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(t)
    r.bold, r.italic = bold, italic
    if size:
        r.font.size = Pt(size)
    return p


def punti(voci, stile='List Bullet'):
    for v in voci:
        p = doc.add_paragraph(style=stile)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if isinstance(v, tuple):
            p.add_run(v[0]).bold = True
            p.add_run(v[1])
        else:
            p.add_run(v)


def codice(t):
    """Riquadro con testo da copiare (espressioni, formule)."""
    tb = doc.add_table(rows=1, cols=1)
    tb.style = 'Table Grid'
    c = tb.rows[0].cells[0]
    c.text = ''
    r = c.paragraphs[0].add_run(t)
    r.font.name = 'Courier New'
    r.font.size = Pt(9)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def figura(cart, nome, didascalia, larg=15.0):
    p = os.path.join(cart, nome)
    if nome in CROP:
        q = os.path.join(cart, '_crop_' + nome)
        Image.open(p).crop(CROP[nome]).save(q)
        p = q
    d = doc.add_paragraph()
    d.alignment = WD_ALIGN_PARAGRAPH.CENTER
    d.paragraph_format.keep_with_next = True
    d.add_run().add_picture(p, width=Cm(larg))
    NFIG[0] += 1
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = c.add_run(f'Figura {NFIG[0]} – {didascalia}')
    r.italic = True
    r.font.size = Pt(9)


def passo(sigla, titolo, dove, testo, controllo=None, figure=(), cart=None):
    doc.add_heading(f'{sigla} – {titolo}', 3)
    if dove:
        q = doc.add_paragraph()
        q.paragraph_format.keep_with_next = True
        q.add_run('Dove: ').bold = True
        q.add_run(dove).italic = True
    punti(testo)
    if controllo:
        q = doc.add_paragraph()
        q.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        q.add_run('Controllo: ').bold = True
        q.add_run(controllo)
    for fg in figure:
        figura(cart, *fg)


def tabella(cols, righe, larghezze, dim=9, grassetto_col0=False):
    t = doc.add_table(rows=1, cols=len(cols))
    t.style = 'Table Grid'
    for j, c in enumerate(cols):
        t.rows[0].cells[j].text = c
    for riga in righe:
        cells = t.add_row().cells
        for j, v in enumerate(riga):
            cells[j].text = '' if v is None else str(v)
    for i, r_ in enumerate(t.rows):
        for j, c in enumerate(r_.cells):
            for p in c.paragraphs:
                p.paragraph_format.keep_with_next = i == 0
                for r in p.runs:
                    r.font.size = Pt(dim)
                    r.font.name = 'Times New Roman'
                    r.bold = i == 0 or (grassetto_col0 and j == 0)
    t.autofit = False
    for j, wd in enumerate(larghezze):
        t.columns[j].width = Cm(wd)
        for r_ in t.rows:
            r_.cells[j].width = Cm(wd)
    doc.add_paragraph()


def a_capo_pagina():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ============================================================ frontespizio
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run('Verifica autonoma delle variabili morfologiche dei bacini dei ponti')
r.bold, r.font.size = True, Pt(18)
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
t.add_run('Manuale operativo illustrato con QGIS 3.34 LTR e GRASS. Dati di partenza: shape dei ponti, DEM unito, '
          'Curve Number').italic = True

doc.add_heading('Principio della verifica', 1)
par("La verifica si fa in modo indipendente dal codice: si parte solo dai tre file di input, si calcolano tutte le "
    "variabili con QGIS e con calcoli fatti a mano, e soltanto alla fine si confrontano i risultati con quelli del "
    "codice. In questo modo il confronto non influenza le scelte fatte durante il calcolo.")
tabella(['Fase', 'Cosa si fa', 'Cosa si usa'],
        [['Parte A – Dal DEM al bacino', 'area di lavoro attorno al ponte, DEM in metri, direzioni di flusso, '
          'reticolo, sezione di chiusura, poligono del bacino', 'shape ponti, DEM unito'],
         ['Parte B – Misure in QGIS', 'coordinate, area, perimetro, quote, Curve Number, pendenze, percorso di flusso '
          'più lungo, tratto di canale', 'risultati della Parte A, Curve Number'],
         ['Parte C – Calcoli a mano', 'variabili derivate con le formule, scritte e svolte passo per passo nel foglio '
          '"Calcolo"', 'misure della Parte B'],
         ['Parte D – Confronto a posteriori', 'solo ora si apre parametri morfologici.csv e si compila il foglio '
          '"Confronto"; poi documentazione', 'risultati del codice']],
        [4.2, 8.8, 4.0])
par("Le figure sono schermate reali di QGIS 3.34 LTR in italiano, prese durante la verifica completa del ponte 100 "
    "(bacino di circa 0,5 km²); i numeri di esempio sono quelli ottenuti in quella prova. Nelle finestre compaiono i "
    "percorsi della macchina usata per la prova: sul proprio PC saranno del tipo C:\\PONTI\\verifica\\ponte_100. Le "
    "figure sono una guida: le prove della propria verifica sono le proprie schermate e la propria cronologia di "
    "Processing (Parte D).", italic=True)

# ============================================================ input
doc.add_heading('1. Input e strumenti', 1)
tabella(['File / strumento', 'Contenuto', 'Note'],
        [['ponti_analisi.shp', 'punti dei 212 ponti, EPSG:32633 (UTM 33N); campi ID (database 1-212) e soglia', 'soglia: '
          'soglia del reticolo in celle per i fossi piccoli; vuota = 4000 celle'],
         ['DEM unito (dem5m_unico_v4.tif)', 'DEM a 5 m, EPSG:32633', 'quote in centimetri interi con scala 0,01: '
          'vanno convertite in metri (passo A2)'],
         ['Curve Number (cn5m_unico.tif)', 'CN sulla stessa griglia del DEM', ''],
         ['QGIS 3.34 LTR con GRASS', 'Processing › Strumenti deve mostrare il gruppo GRASS', 'se manca: Plugin › '
          'Gestisci e installa plugin › Installati › "GRASS GIS provider"'],
         ['Foglio_calcolo_verifica_autonoma.xlsx', 'foglio "Calcolo" (misure e calcoli a mano) e foglio "Confronto" '
          '(da usare solo alla fine)', 'un foglio per ponte: copiare i modelli']],
        [4.4, 6.6, 6.0])

doc.add_heading('2. Le variabili da calcolare', 1)
V = [
    ['Longitude, Latitude', 'coordinate WGS84 del ponte', 'B1'],
    ['X_UTM33N, Y_UTM33N', 'coordinate UTM 33N del ponte', 'B1'],
    ['Snap_Distance_m', 'distanza tra il ponte e la cella di chiusura sul reticolo', 'A4 + C'],
    ['A_km2', 'area del bacino', 'B2'],
    ['Basin_Perimeter_km', 'perimetro del bacino (lati delle celle di confine)', 'B2'],
    ['AE_m', 'quota media sul DEM non riempito', 'B3'],
    ['Relief_m', 'quota massima − quota minima', 'B3 + C'],
    ['Curve_Number_mean', 'Curve Number medio', 'B3'],
    ['S', 'media della massima pendenza in discesa verso le 8 celle vicine (D8), sul DEM riempito (m/m)', 'B4'],
    ['Cell_Slope', 'pendenza D8 della cella di chiusura (m/m)', 'B5'],
    ['Longest_flow_length_km', 'lunghezza del percorso di flusso più lungo fino alla sezione', 'B6 + C'],
    ['Reach_Slope_Centered', 'pendenza del canale da 250 m a monte a 250 m a valle della sezione', 'B7 + C'],
    ['Reach_Length_Centered_m', 'lunghezza del tratto usato', 'B7 + C'],
    ['Reach_Slope_Centered_is_fallback', 'si/no: tratto non tracciabile, si usa S', 'B7'],
    ['Form_factor_FF, Melton_relative_relief, Hypsometric_integral, Elongation_ratio, Shape_factor, Compactness, '
     'Circularity, Relief_Ratio, Relative_relief', 'variabili derivate (formule nella Parte C)', 'C'],
]
tabella(['Variabile', 'Definizione', 'Passo'], V, [6.4, 9.0, 1.6], dim=9)

doc.add_heading('3. Preparazione', 1)
punti([('Cartella: ', 'una per ponte, es. C:\\PONTI\\verifica\\ponte_100; i file prodotti hanno il prefisso p100_.'),
       ('Impronte dei tre input: ', 'PowerShell  Get-FileHash ponti_analisi.shp, Get-FileHash dem5m_unico_v4.tif, '
                                    'Get-FileHash cn5m_unico.tif: copiarle nel registro.'),
       ('Progetto: ', 'nuovo progetto con SR EPSG:32633; caricare i tre input; salvare il progetto nella cartella.'),
       ('Cronologia: ', 'Processing › Cronologia registra ogni algoritmo con parametri, data e ora: non cancellarla.')])
figura(SN, 'N00_qgis_input.png', 'i tre input caricati in QGIS: ponti_analisi (etichette con ID), DEM unito e Curve Number', 15.5)

# ============================================================ PARTE A
a_capo_pagina()
doc.add_heading('Parte A – Dal DEM al bacino', 1)
passo('A0', 'Scelta del ponte', 'Strumenti di Processing › Selezione del vettore › Estrai per attributo',
      ["Layer ponti_analisi; attributo ID; operatore =; valore 100 → p100_ponte.gpkg.",
       "Annotare il campo soglia del ponte: se è vuoto, la soglia del reticolo è 4000 celle (0,1 km²)."],
      None, [('NA0_estrai_per_attributo.png', 'Estrai per attributo: il ponte con ID = 100', 13.5)], SN)
passo('A1', 'Area di lavoro e ritaglio di DEM e Curve Number',
      'Vettore › Strumenti di geoprocessing › Buffer; Raster › Estrazione › Ritaglia raster da estensione',
      ["Buffer di p100_ponte.gpkg con distanza 3000 m → p100_area_lavoro.gpkg (cerchio di 3 km attorno al ponte).",
       "Ritaglia raster da estensione: layer = DEM unito; Estensione del ritaglio = pulsante a destra › Calcola da "
       "layer › p100_area_lavoro → p100_dem_ritaglio.tif. Per il ponte 100 l'estensione è 619645–625645 (X) e "
       "4466207–4472207 (Y).",
       "Ripetere con il Curve Number e la stessa estensione → p100_cn.tif.",
       "La distanza del buffer va scelta più grande del bacino atteso: 3 km per bacini di pochi km²; per i fiumi "
       "maggiori decine di km. Se il bacino arriva al bordo, si allarga e si ripete (passo A6)."],
      None,
      [('NA1a_buffer.png', 'Buffer di 3000 m attorno al ponte', 13.5),
       ('NA1b_ritaglia_dem.png', 'Ritaglia raster da estensione: DEM unito sull\'area di lavoro', 13.5),
       ('NA1c_ritaglia_cn.png', 'Ritaglia raster da estensione: Curve Number sulla stessa estensione', 13.5)], SN)
passo('A2', 'Conversione delle quote in metri', 'Raster › Conversione › Trasforma (converti formato)',
      ["Raster in ingresso p100_dem_ritaglio.tif; in Parametri avanzati, riga di comando aggiuntiva:  -unscale -ot Float32",
       "→ p100_dem_m.tif. Da qui in poi si usa sempre questo DEM in metri."],
      "con lo strumento Informazioni la quota deve essere in metri (centinaia), non in centimetri (decine di migliaia).",
      [('04a_menu_raster_conversione.png', 'menu Raster › Conversione', 10),
       ('04b_converti.png', 'Trasforma (converti formato): la Console GDAL/OGR mostra il comando con -unscale -ot Float32', 13.5)], SA)
passo('A3', 'Direzioni di flusso, accumulo e reticolo', 'Strumenti di Processing › GRASS › Raster › r.watershed',
      ["Elevation = p100_dem_m.tif; Minimum size of exterior watershed basin = soglia del ponte (4000 se vuota).",
       "Spuntare -s (Single Flow Direction, D8) e -a (positive flow accumulation); dimensione celle della regione 5.",
       "Uscite: accumulo → p100_accumulo.tif; Drainage direction → p100_direzioni.tif; Stream segments → p100_reticolo.tif."],
      "il reticolo deve seguire i corsi d'acqua e passare sotto il ponte.",
      [('05a_strumenti_processing_rwatershed.png', 'r.watershed negli Strumenti di Processing', 5.5),
       ('05b_r_watershed.png', 'r.watershed: soglia 4000, opzioni -s e -a', 13.5),
       ('05b_r_watershed_uscite.png', 'r.watershed, parte bassa: file di uscita', 13.5),
       ('05c_mappa_reticolo.png', 'reticolo (blu) e ponte 100 (triangolo rosso)', 13)], SA)
passo('A4', 'Sezione di chiusura', 'strumento Informazioni sui layer p100_reticolo e p100_accumulo',
      ["Sulla cella del reticolo che passa sotto il ponte, la più vicina al punto, leggere l'accumulo e le coordinate "
       "del centro della cella (XS, YS), da scrivere nel foglio Calcolo.",
       "Ponte 100: XS = 622646,50; YS = 4469205,85; accumulo 19.942 celle."],
      "accumulo × 25 / 1.000.000 dà già l'area in km² (19.942 × 25 / 10⁶ = 0,499).",
      [('06a_mappa_sezione_zoom.png', 'sezione scelta (quadrato giallo) vicino al punto del ponte', 11)], SA)
passo('A5', 'Delineazione del bacino',
      'GRASS › r.water.outlet; Raster › Conversione › Poligonizzazione (da raster a vettore); Estrai per espressione',
      ["r.water.outlet: direzioni = p100_direzioni.tif; coordinate = XS,YS del passo A4 → p100_bacino.tif.",
       "Poligonizzazione → p100_bacino_tutti.gpkg; Estrai per espressione \"DN\" = 1 → p100_bacino.gpkg."],
      None,
      [('07a_r_water_outlet.png', 'r.water.outlet con le coordinate della sezione', 13.5),
       ('07b_poligonizza.png', 'Poligonizzazione del raster del bacino', 13.5),
       ('07c_estrai_dn1.png', 'Estrai per espressione: DN = 1', 13.5)], SA)
passo('A6', 'Controllo del bordo', 'mappa con p100_bacino e p100_area_lavoro',
      ["Il bacino non deve toccare il bordo del ritaglio: se lo tocca è troncato. In quel caso raddoppiare la distanza "
       "del buffer e ripetere i passi A1-A5.",
       "Per i bacini molto grandi (es. ponte 6, circa 1.600 km²) usare in r.watershed anche l'opzione -m."],
      "per il ponte 100 il bacino (verde) è ben dentro l'area di lavoro (cerchio rosso).",
      [('NA1d_mappa_area_lavoro.png', 'bacino del ponte 100 dentro l\'area di lavoro di 3 km', 11)], SN)

# ============================================================ PARTE B
a_capo_pagina()
doc.add_heading('Parte B – Misure in QGIS', 1)
par("Ogni valore misurato si scrive nella cella gialla del foglio \"Calcolo\" indicata dalla sigla.")
passo('B1', 'Coordinate del ponte', 'Strumenti di Processing › Tabella vettore › Aggiungi campi X/Y al layer',
      ["Su p100_ponte.gpkg: SR EPSG:32633, prefisso utm_ → X e Y (ponte 100: 622645,25; 4469207,10).",
       "Sul risultato: SR EPSG:4326, prefisso wgs_ → LON e LAT (16,444488348; 40,364421474)."],
      None,
      [('NB1a_campi_xy_utm.png', 'Aggiungi campi X/Y in UTM 33N', 13.5),
       ('NB1b_campi_xy_wgs84.png', 'Aggiungi campi X/Y in WGS84', 13.5),
       ('NB1c_tabella_coordinate.png', 'tabella attributi: utm_x, utm_y, wgs_x, wgs_y', 16)], SN)
passo('B2', 'Area e perimetro', 'Strumenti di Processing › Tabella vettore › Calcolatore di campi',
      ["Su p100_bacino.gpkg: area_km2 =  $area / 1000000 ; perim_km =  $perimeter / 1000",
       "Ponte 100: A = 0,4986 km²; P = 5,17 km."], None,
      [('08a_calcolatore_area.png', 'Calcolatore di campi: area', 13.5),
       ('08b_calcolatore_perimetro.png', 'Calcolatore di campi: perimetro', 13.5)], SA)
passo('B3', 'Quote e Curve Number', 'Strumenti di Processing › Analisi raster › Statistiche zonali',
      ["Raster p100_dem_m.tif (NON riempito), poligono p100_bacino; statistiche Media, Minimo, Massimo → AE, ZMIN, "
       "ZMAX (ponte 100: 231,22; 120,25; 372,36 m).",
       "Raster p100_cn.tif, statistica Media → CN (ponte 100: 84,0)."], None,
      [('09a_statistiche_zonali_dem.png', 'Statistiche zonali sul DEM in metri', 13.5),
       ('09b_statistiche_zonali_cn.png', 'Statistiche zonali sul Curve Number', 13.5)], SA)
passo('B4', 'Pendenza media di bacino S (D8)', 'GRASS › r.fill.dir; GRASS › r.mapcalc.simple; Statistiche zonali',
      ["Definizione: per ogni cella, massima pendenza in discesa verso una delle 8 celle vicine (dislivello / "
       "distanza: 5 m in orizzontale e verticale, 7,0711 m in diagonale) sul DEM con le depressioni riempite; le "
       "celle senza discesa valgono 0. S è la media sul bacino.",
       "r.fill.dir: Elevation = p100_dem_m.tif → p100_dem_riempito.tif.",
       "r.mapcalc.simple: A = p100_dem_riempito.tif; Formula = espressione qui sotto; celle 5 → p100_pendenza_D8.tif "
       "(l'avviso \"SetColorTable() only supported...\" si può ignorare).",
       "Statistiche zonali (Media) di p100_pendenza_D8.tif sul bacino → S (ponte 100: 0,36119)."], None)
codice('max(0, (A-A[-1,0])/5, (A-A[1,0])/5, (A-A[0,-1])/5, (A-A[0,1])/5, (A-A[-1,-1])/7.0711, (A-A[-1,1])/7.0711, '
       '(A-A[1,-1])/7.0711, (A-A[1,1])/7.0711)')
tabella(['Termine', 'Cella vicina', 'Distanza (m)'],
        [['A[-1,0] / A[1,0]', 'nord / sud', '5'], ['A[0,-1] / A[0,1]', 'ovest / est', '5'],
         ['A[-1,-1] / A[-1,1]', 'nord-ovest / nord-est', '7,0711 = √(5² + 5²)'],
         ['A[1,-1] / A[1,1]', 'sud-ovest / sud-est', '7,0711'], ['0', 'nessuna discesa', '-']], [4.5, 5.5, 6.0])
for fg in [('B4a_r_fill_dir.png', 'r.fill.dir: DEM senza depressioni', 13.5),
           ('B4b_r_mapcalc_pendenza_D8.png', 'r.mapcalc.simple con la formula della pendenza D8', 13.5),
           ('B4c_statistiche_zonali_D8.png', 'Statistiche zonali: media della pendenza D8 sul bacino', 13.5)]:
    figura(SB, *fg)
passo('B5', 'Pendenza della cella di chiusura', 'Strumenti di Processing › Analisi raster › Campiona valori raster',
      ["Creare un punto nella cella di chiusura (XS, YS) e campionare p100_pendenza_D8.tif → CS (ponte 100: 0,0297)."],
      None, [('B5a_campiona_pendenza_cella.png', 'Campiona valori raster sulla cella di chiusura', 13.5)], SB)
passo('B6', 'Percorso di flusso più lungo',
      'Analisi raster › Calcolatore raster; Creazione vettore › Pixel raster in punti; GRASS › r.path; '
      'Calcolatore di campi; Estrai per espressione',
      ["Il percorso più lungo parte sempre da una cella \"sorgente\", cioè senza celle a monte (accumulo = 1): se "
       "avesse una cella a monte, quella sarebbe più lontana. Si calcolano quindi i percorsi da tutte le sorgenti.",
       "1) Calcolatore raster:  if ( \"p100_accumulo@1\" = 1 AND \"p100_bacino@1\" = 1, 1, 0/0 )  → "
       "p100_sorgenti.tif (1 sulle sorgenti del bacino, nessun dato altrove).",
       "2) Pixel raster in punti su p100_sorgenti.tif → p100_sorgenti_punti.gpkg (ponte 100: 4.873 punti).",
       "3) r.path: direzioni = p100_direzioni.tif, formato 45degree, punti di partenza = p100_sorgenti_punti → "
       "p100_percorsi_sorgenti.gpkg. Ripetere con punto di partenza la cella di chiusura → p100_percorso_sezione.gpkg.",
       "4) Calcolatore di campi su entrambi: lung_m = $length. Estrai per espressione  \"lung_m\" = maximum(\"lung_m\")  "
       "→ p100_percorso_piu_lungo.gpkg. LMAX = sua lunghezza; LSEZ = lunghezza del percorso dalla sezione.",
       "5) r.path non si ferma alla sezione ma prosegue fino al bordo del ritaglio, lungo lo stesso percorso per tutti: "
       "per questo L = (LMAX − LSEZ) / 1000. Ponte 100: (5575,23 − 3782,91) / 1000 = 1,7923 km."],
      "il percorso più lungo deve partire dallo spartiacque, nella testata del bacino opposta alla sezione.",
      [('NB6a_calcolatore_sorgenti.png', 'Calcolatore raster: celle sorgenti del bacino', 13.5),
       ('NB6b_pixel_in_punti.png', 'Pixel raster in punti', 13.5),
       ('NB6c_r_path_sorgenti.png', 'r.path da tutte le sorgenti (formato 45degree)', 13.5),
       ('NB6d_r_path_sezione.png', 'r.path dalla cella di chiusura', 13.5),
       ('NB6e_lunghezza_percorsi.png', 'Calcolatore di campi: lunghezza dei percorsi', 13.5),
       ('NB6f_estrai_massimo.png', 'Estrai per espressione: il percorso più lungo', 13.5),
       ('NB6g_mappa_sorgenti.png', 'celle sorgenti (arancio), percorso più lungo (rosso) e percorso dalla sezione '
                                   '(nero tratteggiato): a valle della sezione coincidono', 11)], SN)
passo('B7', 'Tratto di canale centrato sulla sezione',
      'Geometria vettore › Interpola punto sulla linea; Analisi raster › Campiona valori raster',
      ["Il tratto va da 250 m a monte (lungo il canale principale) a 250 m a valle della sezione.",
       "Punto a valle: Interpola punto sulla linea su p100_percorso_sezione.gpkg, distanza 250.",
       "Punto a monte: Interpola punto sulla linea su p100_percorso_piu_lungo.gpkg, distanza (L × 1000) − 250 = "
       "1542,32. Se vicino alla sezione il percorso più lungo non segue il canale principale (quello con accumulo "
       "maggiore), lanciare r.path da una cella del canale principale più a monte e usare quella linea.",
       "Campiona valori raster dei due punti su p100_dem_m.tif → ZUP e ZDN (ponte 100: 130,06 e 110,70 m); DUP = DDN = 250.",
       "FB = si solo se il tratto non si può tracciare (sezione in testa al reticolo): in quel caso la pendenza di "
       "tratto è S."], None,
      [('NB7a_interpola_monte.png', 'Interpola punto sulla linea: punto a monte', 13.5),
       ('NB7b_interpola_valle.png', 'Interpola punto sulla linea: punto a valle', 13.5)], SN)
for fg in [('B7c_campiona_quote.png', 'Campiona valori raster: quote dei due punti sul DEM in metri', 13.5),
           ('B7d_mappa_tratto.png', 'il tratto di canale: punti a monte e a valle con le quote', 11)]:
    figura(SB, *fg)

# ============================================================ PARTE C
a_capo_pagina()
doc.add_heading('Parte C – Calcoli a mano', 1)
par("Con le misure della Parte B si calcolano le variabili rimanenti. Ogni formula va prima scritta con i numeri e "
    "poi svolta, come nella tabella (esempio del ponte 100); il foglio \"Calcolo\" fa lo stesso conto con le formule "
    "(celle verdi) e permette di controllare i calcoli fatti a mano (colonna \"Calcolo a mano\").")
C = [
    ['Snap_Distance_m', '√((XS − X)² + (YS − Y)²)', '√(1,25² + 1,25²) = √3,1250', '1,77 m'],
    ['Longest_flow_length_km', '(LMAX − LSEZ) / 1000', '(5575,23 − 3782,91) / 1000', '1,7923 km'],
    ['Relief_m', 'ZMAX − ZMIN', '372,36 − 120,25', '252,11 m'],
    ['Form_factor_FF', 'A / L²', '0,4986 / 1,7923² = 0,4986 / 3,2124', '0,1552'],
    ['Melton_relative_relief', '(REL/1000) / √A', '0,25211 / √0,4986 = 0,25211 / 0,7061', '0,3570'],
    ['Hypsometric_integral', '(AE − ZMIN) / REL', '(231,22 − 120,25) / 252,11 = 110,97 / 252,11', '0,4402'],
    ['Elongation_ratio', '2·√(A/π) / L', '2·√(0,4986 / 3,1416) / 1,7923 = 2·0,3984 / 1,7923', '0,4445'],
    ['Shape_factor', 'L / √A', '1,7923 / 0,7061', '2,5383'],
    ['Compactness', 'P / (2·√(π·A))', '5,17 / (2·√1,5664) = 5,17 / 2,5032', '2,0654'],
    ['Circularity', '4·π·A / P²', '6,2656 / 26,7289', '0,2344'],
    ['Relief_Ratio', '(REL/1000) / L', '0,25211 / 1,7923', '0,1407'],
    ['Relative_relief', 'REL / (P·1000)', '252,11 / 5170', '0,0488'],
    ['Reach_Length_Centered_m', 'DUP + DDN', '250 + 250', '500 m'],
    ['Reach_Slope_Centered', '(ZUP − ZDN) / (DUP + DDN)', '(130,06 − 110,70) / 500 = 19,36 / 500', '0,0387'],
    ['Reach_Slope_Centered_is_fallback', 'FB', 'tratto tracciato', 'no'],
]
tabella(['Variabile', 'Formula', 'Sostituzione (ponte 100)', 'Risultato'], C, [4.4, 3.9, 6.3, 2.4], dim=8.5)
par("Unità: A in km², L e P in km, quote e rilievo in m, pendenze in m/m. π = 3,1416. Conviene tenere 4 cifre "
    "decimali nei passaggi intermedi.", size=10)
par("Uso del foglio: copiare \"Modello calcolo\" (tasto destro sulla linguetta › Sposta o copia › Crea una copia), "
    "rinominarlo con il numero del ponte, scrivere le misure nelle celle gialle e il proprio calcolo a mano nella "
    "colonna G; le celle verdi si calcolano da sole e devono dare lo stesso risultato del calcolo a mano.")
figura(SN, 'NC1_foglio_calcolo.png', 'foglio "Calcolo" compilato per il ponte 100: misure (giallo), formule (verde), '
                                     'calcolo a mano (azzurro)', 16.5)

# ============================================================ PARTE D
a_capo_pagina()
doc.add_heading('Parte D – Confronto a posteriori e documentazione', 1)
doc.add_heading('D1 – Confronto con i risultati del codice', 2)
par("Solo ora si apre \"parametri morfologici.csv\" e si cerca la riga del ponte (colonna ID). Nel foglio "
    "\"Confronto\" (copia di \"Modello confronto\") la colonna \"Valore verifica\" si riempie da sola con i risultati "
    "del foglio Calcolo; si copiano nella colonna \"Valore codice\" i valori del CSV; la colonna \"Differenza %\" si "
    "calcola da sola.")
figura(SN, 'ND1_foglio_confronto.png', 'foglio "Confronto" del ponte 100: tutte le variabili entro ±0,7%, tranne la '
                                       'distanza di aggancio (−1,8%, vedi D3)', 13)
par("Confronto dei poligoni: caricare bacini_afferenti.geojson, selezionare il bacino con lo stesso ID e calcolare "
    "Vettore › Strumenti di geoprocessing › Differenza simmetrica con p100_bacino.gpkg; area delle parti non comuni / "
    "area del bacino = percentuale di non sovrapposizione (ponte 100: 26 celle, 0,13%).")
figura(SA, '11a_differenza_simmetrica.png', 'Differenza simmetrica tra il bacino del codice e quello della verifica', 13)
figura(SA, '11b_mappa_confronto.png', 'bacino del codice (contorno rosso) e bacino della verifica (verde)', 11.5)
doc.add_heading('D2 – Tolleranze attese', 2)
tabella(['Variabili', 'Differenza attesa', 'Se è maggiore'],
        [['coordinate', 'nessuna', 'controllare il SR (EPSG:32633 / 4326)'],
         ['area, perimetro e variabili che li usano', 'entro 1-2%', 'cella di chiusura (A4), bordo (A6), soglia (A3)'],
         ['quote, rilievo, CN', 'centimetri / decimali', 'conversione in metri (A2); DEM non riempito per AE'],
         ['S, Cell_Slope', 'qualche millesimo', 'DEM riempito e formula esatta (B4)'],
         ['Longest_flow_length_km', 'un passo di cella (5-7 m)', 'percorsi da tutte le sorgenti (B6)'],
         ['pendenza e lunghezza di tratto', 'pochi millesimi / pochi metri', 'punto a monte sul canale principale (B7)']],
        [5.0, 4.0, 8.0])
doc.add_heading('D3 – Differenze normali da spiegare nella relazione', 2)
punti([('Distanza di aggancio: ', "la verifica misura dal ponte al centro della cella (1,77 m); il codice riporta "
                                  "1,8 m perché usa come punto agganciato un angolo della cella."),
       ('Lunghezza del tratto: ', "la verifica usa esattamente 250 + 250 m; il codice avanza cella per cella finché "
                                  "supera 250 m (ponte 100: 503 m), quindi la pendenza di tratto differisce di "
                                  "pochi millesimi."),
       ('Area: ', "GRASS (r.watershed) e il codice instradano il flusso in modo leggermente diverso nelle aree "
                  "piatte: poche celle di differenza sul bordo del bacino.")])
doc.add_heading('D4 – Problemi frequenti', 2)
punti([('GRASS non compare: ', 'Plugin › Gestisci e installa plugin › Installati › "GRASS GIS provider".'),
       ('r.path: "No path": ', 'formato delle direzioni 45degree.'),
       ('accumulo negativo vicino ai bordi: ', 'manca -a in r.watershed.'),
       ('quote 100 volte troppo grandi: ', 'manca -unscale (A2).'),
       ('Calcolatore raster: errore di formula: ', 'scrivere i nomi dei layer come compaiono nell\'elenco, tra '
                                                  'virgolette, con @1.'),
       ('bacino troncato: ', 'allargare il buffer (A6).')])
doc.add_heading('D5 – Documentazione della verifica', 2)
punti([('Cronologia di Processing: ', 'Processing › Cronologia › selezionare tutto › Salva.'),
       ('Progetto QGIS: ', 'un .qgz per ponte con i layer intermedi.'),
       ('Foglio di calcolo: ', 'fogli Calcolo e Confronto di ogni ponte, con il calcolo a mano.'),
       ('Schermate: ', 'p_ID_passo.png (es. p100_B6.png), con ID, scala e legenda visibili.'),
       ('Impronte dei tre input: ', 'nel registro, con data e operatore.'),
       ('Relazione: ', "scritta con parole proprie: metodo, ponti verificati, risultati, differenze spiegate, "
                       "conclusioni e dichiarazione degli strumenti usati, compresa l'eventuale assistenza di "
                       "strumenti di intelligenza artificiale e ciò che è stato verificato in modo indipendente.")])
doc.save(out)
print('ok', out, 'figure', NFIG[0])
