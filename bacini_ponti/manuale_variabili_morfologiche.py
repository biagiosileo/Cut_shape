"""
Manuale illustrato (Word + PDF) per verificare in autonomia, passo per passo, TUTTE le variabili morfologiche
calcolate da pysheds_bridges_5m.py, partendo da DEM, punto del ponte e Curve Number (QGIS 3.34 + GRASS).
Figure: schermate reali della prova sul ponte 100. Times New Roman 11 pt, testo giustificato, A4.

Uso: python manuale_variabili_morfologiche.py <cartella schermate parte A> <cartella schermate parte B> <out.docx>
"""
import os
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

SA, SB, out = sys.argv[1:4]
CROP = {'03a_menu_raster_estrazione.png': (300, 50, 1000, 330), '04a_menu_raster_conversione.png': (300, 50, 1000, 330),
        '05a_strumenti_processing_rwatershed.png': (0, 0, 311, 230), '10d_tabella_attributi.png': (0, 0, 1460, 95),
        'B1d_tabella_ponte.png': (0, 0, 640, 60)}
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
r = t.add_run('Verifica manuale delle variabili morfologiche dei bacini dei ponti')
r.bold, r.font.size = True, Pt(18)
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
t.add_run('Manuale operativo illustrato: dal DEM, dal punto del ponte e dal Curve Number a tutte le 25 variabili '
          'del file "parametri morfologici.csv", con QGIS 3.34 LTR e GRASS').italic = True

doc.add_heading('Come è organizzato il manuale', 1)
par("Il manuale permette di ricalcolare in autonomia, per un ponte qualsiasi, tutte le variabili prodotte dal codice "
    "pysheds_bridges_5m.py e di confrontarle con i suoi risultati. Si parte da tre soli dati: il DEM a 5 m, le "
    "coordinate del ponte e il raster del Curve Number. Il lavoro è diviso in quattro parti:")
punti([('Parte A – Dal DEM al bacino: ', 'ritaglio e conversione del DEM, direzioni di flusso, reticolo, sezione di '
                                        'chiusura e poligono del bacino (passi A1-A5).'),
       ('Parte B – Le misure in QGIS: ', 'coordinate, area, perimetro, quote, Curve Number, pendenze, percorso di '
                                        'flusso più lungo e tratto di canale (passi B1-B7).'),
       ('Parte C – I calcoli: ', 'le 13 variabili derivate si ottengono dalle misure con le formule del codice, nel '
                                 'foglio Excel allegato (Foglio_calcolo_variabili_morfologiche.xlsx).'),
       ('Parte D – Confronto e documentazione: ', 'tolleranze attese, problemi frequenti, registro e prove della verifica.')])
par("Tutte le figure sono schermate reali di QGIS 3.34 LTR in italiano, prese durante la verifica completa del "
    "ponte 100 (bacino di circa 0,5 km², porzione_07), e tutti i numeri di esempio sono quelli ottenuti in quella "
    "prova. Nelle finestre si vedono i percorsi dei file della macchina su cui è stata fatta la prova: sul proprio PC "
    "saranno del tipo C:\\PONTI\\verifica_manuale\\ponte_100. Le figure servono da guida: le prove della propria "
    "verifica sono le proprie schermate e la cronologia di Processing del proprio QGIS (Parte D).", italic=True)

# ============================================================ materiale
doc.add_heading('1. Materiale necessario', 1)
tabella(['Cosa', 'Dettaglio'],
        [['QGIS 3.34 LTR (o successivo) con GRASS', 'su Windows: installatore OSGeo4W o pacchetto standalone. In '
          'Processing › Strumenti deve comparire il gruppo GRASS (se manca: Plugin › Gestisci e installa plugin › '
          'Installati › attivare "GRASS GIS provider").'],
         ['dem5m_unico.tif', 'DEM definitivo (ricomposto con lo script R), EPSG:32633, celle 5 m. Quote salvate in '
          'centimetri interi con scala 0,01 (vedi passo A2).'],
         ['cn5m_unico.tif', 'Curve Number sulla stessa griglia del DEM.'],
         ['ponti.csv', 'colonne id, X (longitudine), Y (latitudine) in WGS84, porzione, xmin, ymax, xmax, ymin '
          '(UTM 33N) e soglia (facoltativa).'],
         ['parametri morfologici.csv, bacini_afferenti.geojson', 'risultati del codice da verificare.'],
         ['Foglio_calcolo_variabili_morfologiche.xlsx', 'foglio allegato: si inseriscono le misure della Parte B e '
          'calcola le variabili derivate e le differenze con il codice.']],
        [5.2, 11.8])

# ============================================================ variabili
doc.add_heading('2. Le 25 variabili e come si ottengono', 1)
par("La tabella elenca le colonne di \"parametri morfologici.csv\" (oltre a ID, Longitude e Latitude, che sono i "
    "dati di ingresso) e dice da quale passo del manuale si ottiene ciascuna. Le definizioni sono quelle del codice.")
V = [
    ['X_UTM33N, Y_UTM33N', 'coordinate del ponte in UTM 33N', 'riproiezione del punto WGS84', 'B1'],
    ['Snap_Distance_m', 'distanza tra il punto del ponte e la cella di chiusura sul reticolo', 'misura in QGIS', 'B1'],
    ['A_km2', 'area del bacino', 'n. celle × 25 m² (= area del poligono)', 'B2'],
    ['Basin_Perimeter_km', 'perimetro del bacino (lati delle celle di confine)', 'perimetro del poligono', 'B2'],
    ['AE_m', 'quota media del bacino sul DEM originale', 'statistiche zonali (media)', 'B3'],
    ['Relief_m', 'rilievo = quota massima − quota minima', 'statistiche zonali (min, max)', 'B3 + C'],
    ['Curve_Number_mean', 'Curve Number medio del bacino', 'statistiche zonali (media) sul CN', 'B3'],
    ['S', 'pendenza media di bacino: media della massima pendenza D8 verso le 8 celle vicine, sul DEM condizionato (m/m)',
     'r.fill.dir + r.mapcalc + statistiche zonali', 'B4'],
    ['Cell_Slope', 'pendenza D8 nella cella di chiusura (m/m)', 'campionamento del raster di pendenza D8', 'B5'],
    ['Longest_flow_length_km', 'lunghezza del percorso di flusso più lungo fino alla sezione', 'r.path', 'B6'],
    ['Reach_Slope_Centered', 'pendenza del canale su ~500 m centrati sulla sezione (250 m a monte e 250 a valle)',
     'r.path + punti interpolati + quote', 'B7 + C'],
    ['Reach_Length_Centered_m', 'lunghezza effettiva del tratto usato', 'somma delle due distanze', 'B7 + C'],
    ['Reach_Slope_Centered_is_fallback', 'True se il tratto non si può tracciare e si usa S al suo posto', 'regola', 'B7'],
    ['Form_factor_FF', 'A / L²', 'calcolo', 'C'],
    ['Melton_relative_relief', '(rilievo/1000) / √A', 'calcolo', 'C'],
    ['Hypsometric_integral', '(AE − quota minima) / rilievo', 'calcolo', 'C'],
    ['Elongation_ratio', '2·√(A/π) / L', 'calcolo', 'C'],
    ['Shape_factor', 'L / √A', 'calcolo', 'C'],
    ['Compactness', 'P / (2·√(π·A))', 'calcolo', 'C'],
    ['Circularity', '4·π·A / P²', 'calcolo', 'C'],
    ['Relief_Ratio', '(rilievo/1000) / L', 'calcolo', 'C'],
    ['Relative_relief', 'rilievo / (P in metri)', 'calcolo', 'C'],
]
tabella(['Colonna del CSV', 'Significato (come nel codice)', 'Come si ottiene', 'Passo'], V, [4.6, 6.6, 4.3, 1.5], dim=8.5)
par("Unità: A in km², L e P in km, quote e rilievo in m, pendenze in m/m (moltiplicare per 100 per avere la "
    "percentuale). Le formule derivate sono riportate per esteso nella Parte C.", size=10)

# ============================================================ preparazione
doc.add_heading('3. Preparazione', 1)
punti([('Cartella: ', 'una cartella per ponte, es. C:\\PONTI\\verifica_manuale\\ponte_100; tutti i file prodotti '
                      'vanno salvati lì con il prefisso del ponte (p100_...).'),
       ('Impronte dei file: ', 'in PowerShell  Get-FileHash C:\\PONTI\\run_v4\\dem5m_unico.tif  (e così per '
                               'cn5m_unico.tif, ponti.csv e parametri morfologici.csv); copiarle nel registro.'),
       ('Progetto QGIS: ', 'Progetto › Nuovo; SR del progetto EPSG:32633; salvare il progetto nella cartella.'),
       ('Cronologia: ', 'Processing › Cronologia registra ogni algoritmo eseguito con parametri, data e ora: non '
                        'cancellarla, si esporta a fine lavoro.'),
       ('Dati del ponte: ', 'da ponti.csv annotare id, X, Y, porzione, xmin, ymax, xmax, ymin e soglia. Per il ponte '
                            '100: X = 16,444488348, Y = 40,364421474, porzione_07, xmin 603339,0001, ymax '
                            '4473458,3481, xmax 627669,0001, ymin 4464253,3481, soglia vuota (= 4000 celle).')])

# ============================================================ PARTE A
a_capo_pagina()
doc.add_heading('Parte A – Dal DEM al bacino', 1)
passo('A1', 'Ritaglio del DEM sulla porzione del ponte', 'Raster › Estrazione › Ritaglia raster da estensione',
      ["Layer in ingresso: dem5m_unico.tif.",
       "Estensione del ritaglio: digitare xmin, xmax, ymin, ymax della porzione (nel CSV l'ordine delle colonne è "
       "xmin, ymax, xmax, ymin). Per il ponte 100: 603339.0001, 627669.0001, 4464253.3481, 4473458.3481.",
       "Salvare come p100_dem_ritaglio.tif."],
      "il ritaglio deve contenere tutto il bacino del codice (bacini_afferenti.geojson).",
      [('03a_menu_raster_estrazione.png', 'menu Raster › Estrazione', 10),
       ('03b_ritaglia_raster.png', 'Ritaglia raster da estensione con i limiti della porzione_07', 13.5)], SA)
passo('A2', 'Conversione delle quote in metri', 'Raster › Conversione › Trasforma (converti formato)',
      ["Raster in ingresso: p100_dem_ritaglio.tif. In Parametri avanzati, riga di comando aggiuntiva:  -unscale -ot Float32",
       "Salvare come p100_dem_m.tif. Da qui in avanti si usa sempre questo DEM in metri.",
       "Perché: il DEM è salvato in centimetri interi con scala 0,01; GRASS legge i valori grezzi e senza questo passo "
       "quote, rilievo e pendenze risulterebbero 100 volte più grandi."],
      "con lo strumento Informazioni la quota di una cella deve essere in metri (per il ponte 100: tra 47 e 994 m "
      "nel ritaglio).",
      [('04a_menu_raster_conversione.png', 'menu Raster › Conversione', 10),
       ('04b_converti.png', 'Trasforma (converti formato): la Console GDAL/OGR mostra il comando con -unscale -ot Float32', 13.5)], SA)
passo('A3', 'Direzioni di flusso, accumulo e reticolo', 'Strumenti di Processing › GRASS › Raster › r.watershed',
      ["Elevation: p100_dem_m.tif.",
       "Minimum size of exterior watershed basin: 4000 (celle, = 0,1 km², la soglia del codice); se in ponti.csv la "
       "colonna soglia è compilata usare quel valore.",
       "Spuntare Enable Single Flow Direction (D8) (-s) e Use positive flow accumulation even for likely "
       "underestimates (-a). Lasciare spenti gli altri.",
       "Dimensione delle celle della regione: 5. Uscite: Number of cells that drain through each cell → "
       "p100_accumulo.tif; Drainage direction → p100_direzioni.tif; Stream segments → p100_reticolo.tif."],
      "il reticolo deve seguire i corsi d'acqua e passare sotto il ponte.",
      [('05a_strumenti_processing_rwatershed.png', 'r.watershed negli Strumenti di Processing', 5.5),
       ('05b_r_watershed.png', 'r.watershed: soglia 4000, opzioni -s e -a', 13.5),
       ('05b_r_watershed_uscite.png', 'r.watershed, parte bassa: file di uscita', 13.5),
       ('05c_mappa_reticolo.png', 'reticolo GRASS (blu) e ponte 100 (triangolo rosso)', 13.5)], SA)
passo('A4', 'Sezione di chiusura', 'strumento Informazioni sui layer p100_reticolo e p100_accumulo',
      ["Zoomare sul ponte e cliccare la cella del reticolo che passa sotto il ponte, la più vicina al punto.",
       "Annotare le coordinate del centro della cella e l'accumulo. Ponte 100: X = 622646,50; Y = 4469205,85; "
       "accumulo 19.942 celle."],
      "accumulo × 25 / 1.000.000 = stima dell'area (19.942 × 25 / 10⁶ = 0,499 km²).",
      [('06a_mappa_sezione_zoom.png', 'sezione scelta (quadrato giallo) a 1,8 m dal punto del ponte', 11)], SA)
passo('A5', 'Delineazione del bacino',
      'GRASS › Raster › r.water.outlet; Raster › Conversione › Poligonizzazione (da raster a vettore); '
      'Selezione del vettore › Estrai per espressione',
      ["r.water.outlet: direzioni = p100_direzioni.tif; Coordinates of outlet point = coordinate del passo A4; "
       "dimensione celle 5 → p100_bacino.tif.",
       "Poligonizzazione di p100_bacino.tif (campo DN) → p100_bacino_tutti.gpkg.",
       "Estrai per espressione  \"DN\" = 1  → p100_bacino.gpkg (il poligono del bacino)."],
      "un solo poligono chiuso che termina alla sezione.",
      [('07a_r_water_outlet.png', 'r.water.outlet con le coordinate della sezione', 13.5),
       ('07b_poligonizza.png', 'Poligonizzazione del raster del bacino', 13.5),
       ('07c_estrai_dn1.png', 'Estrai per espressione: DN = 1', 13.5),
       ('07d_mappa_bacino.png', 'bacino del ponte 100 delineato con GRASS', 13)], SA)

# ============================================================ PARTE B
a_capo_pagina()
doc.add_heading('Parte B – Le misure in QGIS', 1)
par("Ogni misura va riportata nella cella gialla corrispondente del foglio di calcolo (colonna \"Passo\").")
passo('B1', 'Coordinate UTM del ponte e distanza di aggancio',
      'Strumenti di Processing › Creazione vettore › Crea layer di punti da tabella; Generale vettore › Riproietta '
      'layer; Tabella vettore › Aggiungi campi X/Y al layer',
      ["Crea layer di punti da tabella: tabella = ponti.csv (o un CSV con la sola riga del ponte), campo X = X, campo "
       "Y = Y, SR = EPSG:4326 (le coordinate di ponti.csv sono longitudine e latitudine WGS84).",
       "Riproietta layer in EPSG:32633; poi Aggiungi campi X/Y al layer (SR EPSG:32633, prefisso utm_).",
       "X_UTM33N e Y_UTM33N = campi utm_x e utm_y (ponte 100: 622645,25; 4469207,10).",
       "Snap_Distance_m: distanza tra il punto del ponte e il centro della cella del passo A4, con lo strumento Misura "
       "linea oppure √((Xcella − X)² + (Ycella − Y)²) = √(1,25² + 1,25²) ≈ 1,77 m."],
      "il codice riporta 1,8 m: usa come punto agganciato l'angolo della cella e non il centro; differenze di "
      "qualche decimetro sono normali, valori oltre 10 m indicano un aggancio da controllare.",
      [('B1a_punti_da_tabella.png', 'Crea layer di punti da tabella (WGS84)', 13.5),
       ('B1b_riproietta.png', 'Riproietta layer in EPSG:32633', 13.5),
       ('B1c_campi_xy.png', 'Aggiungi campi X/Y al layer', 13.5),
       ('B1d_tabella_ponte.png', 'tabella attributi: utm_x e utm_y del ponte 100', 12)], SB)
passo('B2', 'Area e perimetro', 'Strumenti di Processing › Tabella vettore › Calcolatore di campi',
      ["Sul layer p100_bacino.gpkg: campo area_km2 (decimale) =  $area / 1000000",
       "Campo perim_km (decimale) =  $perimeter / 1000",
       "Ponte 100: A = 0,4986 km²; P = 5,17 km."],
      "il poligono ottenuto dal raster segue i lati delle celle, come il perimetro del codice.",
      [('08a_calcolatore_area.png', 'Calcolatore di campi: area in km²', 13.5),
       ('08b_calcolatore_perimetro.png', 'Calcolatore di campi: perimetro in km', 13.5)], SA)
passo('B3', 'Quota media, quota minima e massima, Curve Number medio',
      'Strumenti di Processing › Analisi raster › Statistiche zonali',
      ["Layer raster p100_dem_m.tif (DEM originale in metri, NON riempito), layer poligono = bacino; statistiche "
       "Media, Minimo, Massimo; prefisso dem_. Ponte 100: media 231,22; minimo 120,25; massimo 372,36 m.",
       "Ritagliare cn5m_unico.tif come al passo A1 (p100_cn.tif) e ripetere con statistica Media, prefisso cn_. "
       "Ponte 100: 84,0."],
      "AE_m del codice è la media sul DEM originale, come qui: la differenza deve essere di pochi centimetri.",
      [('09a_statistiche_zonali_dem.png', 'Statistiche zonali sul DEM: media, minimo, massimo', 13.5),
       ('09b_statistiche_zonali_cn.png', 'Statistiche zonali sul Curve Number', 13.5),
       ('10d_tabella_attributi.png', 'tabella attributi del bacino con area, perimetro, quote e CN (le colonne '
                                     'pend_ derivano dalla versione precedente del manuale e non servono)', 16)], SA)

passo('B4', 'Pendenza media di bacino S (metodo D8 del codice)',
      'GRASS › Raster › r.fill.dir; GRASS › Raster › r.mapcalc.simple; Analisi raster › Statistiche zonali',
      ["Il codice calcola, per ogni cella, la massima pendenza in discesa verso una delle 8 celle vicine "
       "(dislivello / distanza: 5 m in orizzontale e verticale, 7,0711 m in diagonale), sul DEM condizionato "
       "(depressioni riempite), e ne fa la media sul bacino. Le celle senza discesa valgono 0.",
       "r.fill.dir: Elevation = p100_dem_m.tif; uscita Depressionless DEM → p100_dem_riempito.tif (dimensione celle 5).",
       "r.mapcalc.simple: Raster layer A = p100_dem_riempito.tif; Formula = l'espressione qui sotto (copiarla "
       "esattamente); dimensione celle 5; uscita p100_pendenza_D8.tif. Un messaggio \"SetColorTable() only "
       "supported for Byte or UInt16\" è solo un avviso e si può ignorare.",
       "Statistiche zonali (Media) di p100_pendenza_D8.tif sul bacino: è S in m/m. Ponte 100: 0,36119."],
      "differenza con S del codice entro qualche millesimo (il riempimento di GRASS e quello di pysheds trattano le "
      "aree piatte in modo leggermente diverso).")
codice('max(0, (A-A[-1,0])/5, (A-A[1,0])/5, (A-A[0,-1])/5, (A-A[0,1])/5, (A-A[-1,-1])/7.0711, (A-A[-1,1])/7.0711, '
       '(A-A[1,-1])/7.0711, (A-A[1,1])/7.0711)')
tabella(['Termine', 'Cella vicina', 'Distanza (m)'],
        [['A[-1,0] / A[1,0]', 'nord / sud', '5'], ['A[0,-1] / A[0,1]', 'ovest / est', '5'],
         ['A[-1,-1] / A[-1,1]', 'nord-ovest / nord-est', '7,0711 = √(5² + 5²)'],
         ['A[1,-1] / A[1,1]', 'sud-ovest / sud-est', '7,0711'], ['0', 'nessuna discesa', '-']], [4.5, 5.5, 6.0])
for fg in [('B4a_r_fill_dir.png', 'r.fill.dir: DEM senza depressioni', 13.5),
           ('B4b_r_mapcalc_pendenza_D8.png', 'r.mapcalc.simple con l\'espressione della pendenza D8 (a destra si vede '
                                             'la parte finale della formula; la dimensione delle celle è 5)', 13.5),
           ('B4c_statistiche_zonali_D8.png', 'Statistiche zonali (media) della pendenza D8 sul bacino', 13.5)]:
    figura(SB, *fg)
passo('B5', 'Pendenza della cella di chiusura (Cell_Slope)', 'Analisi raster › Campiona valori raster',
      ["Creare un layer punto con la cella di chiusura del passo A4 (o usare lo strumento Informazioni).",
       "Campiona valori raster: punti = cella di chiusura, raster = p100_pendenza_D8.tif. Ponte 100: 0,0297."],
      "deve coincidere con Cell_Slope del codice.",
      [('B5a_campiona_pendenza_cella.png', 'Campiona valori raster sulla cella di chiusura', 13.5)], SB)
passo('B6', 'Percorso di flusso più lungo (Longest_flow_length_km)', 'GRASS › Raster › r.path',
      ["Il codice misura, seguendo le direzioni D8 dentro il bacino, la distanza dalla sezione alla cella più "
       "lontana (5 m per passo orizzontale o verticale, 7,0711 m per passo diagonale).",
       "1) Individuare il punto più lontano: è sullo spartiacque all'estremità del bacino opposta alla sezione, "
       "in testa alla valle principale. Creare un layer punti con 3-5 celle candidate in quella zona.",
       "2) r.path: Name of input direction = p100_direzioni.tif; Format = 45degree; Vector layer containing "
       "starting point(s) = i punti candidati; uscita vettoriale = p100_percorso_lungo.gpkg. Ripetere con punto di "
       "partenza la cella di chiusura → p100_percorso_valle.gpkg.",
       "3) r.path non si ferma alla sezione ma prosegue fino al bordo del ritaglio. Per questo: L = lunghezza del "
       "percorso dal punto lontano − lunghezza del percorso dalla sezione (i due percorsi coincidono a valle della "
       "sezione). Le lunghezze si leggono con il Calcolatore di campi ($length).",
       "4) Tra i candidati vale il massimo. Ponte 100: 8099,23 − 6306,92 = 1792,31 m = 1,7923 km."],
      "deve coincidere con il codice (1,792 km) a meno di un passo di cella.",
      [('B6a_r_path.png', 'r.path dal punto più lontano (formato delle direzioni: 45degree)', 13.5),
       ('B6b_mappa_percorso_lungo.png', 'percorso dal punto più lontano (rosso) e dalla sezione (nero tratteggiato): '
                                        'dalla sezione in giù coincidono', 13.5),
       ('B6c_mappa_percorsi_valle.png', 'i due percorsi proseguono insieme fino al bordo del ritaglio: per questo si '
                                         'sottraggono le lunghezze', 15)], SB)
passo('B7', 'Pendenza di tratto centrata sulla sezione (Reach_Slope_Centered)',
      'Geometria vettore › Interpola punto sulla linea; Analisi raster › Campiona valori raster',
      ["Il codice risale il canale principale per 250 m (alle confluenze segue il ramo con accumulo maggiore) e "
       "scende lungo il flusso per altri 250 m; pendenza = (quota a monte − quota a valle) / distanza percorsa, con "
       "le quote del DEM originale.",
       "Punto a valle: Interpola punto sulla linea su p100_percorso_valle.gpkg alla distanza 250.",
       "Punto a monte: sul percorso che arriva alla sezione lungo il canale principale (per il ponte 100 è "
       "p100_percorso_lungo.gpkg), alla distanza L − 250 dall'inizio della linea (1792,31 − 250 = 1542,31). Se il "
       "percorso più lungo non segue il canale principale vicino alla sezione, lanciare r.path da una cella del "
       "canale principale qualche centinaio di metri a monte.",
       "Campiona valori raster dei due punti su p100_dem_m.tif (DEM originale). Ponte 100: monte 130,06 m; "
       "valle 110,70 m.",
       "Nel foglio: pendenza = (130,06 − 110,70) / (250 + 250) = 0,0387.",
       "Reach_Slope_Centered_is_fallback: se il tratto non si può percorrere (sezione in testa al reticolo, "
       "nessuna discesa) il codice scrive True e usa S al posto della pendenza di tratto; altrimenti False."],
      "il codice percorre cella per cella fino a superare 250 m (per il ponte 100: 503 m in tutto), quindi la "
      "pendenza differisce di pochi millesimi.",
      [('B7a_interpola_valle.png', 'Interpola punto sulla linea: 250 m a valle della sezione', 13.5),
       ('B7b_interpola_monte.png', 'Interpola punto sulla linea: 250 m a monte (distanza L − 250 dal punto lontano)', 13.5),
       ('B7c_campiona_quote.png', 'Campiona valori raster: quote dei due punti sul DEM originale', 13.5),
       ('B7d_mappa_tratto.png', 'il tratto di canale usato per la pendenza: punti a monte e a valle con le loro quote', 11.5)], SB)

# ============================================================ PARTE C
a_capo_pagina()
doc.add_heading('Parte C – I calcoli delle variabili derivate', 1)
par("Le 13 variabili seguenti non si misurano: si calcolano dalle misure della Parte B con le formule del codice. "
    "Il foglio Excel allegato le calcola da solo; la tabella mostra le formule e il calcolo per esteso del ponte 100, "
    "così si può rifare anche a mano.")
C = [
    ['Relief_m', 'zmax − zmin', '372,36 − 120,25', '252,11', '252,11'],
    ['Form_factor_FF', 'A / L²', '0,4986 / 1,7923²', '0,1552', '0,1551'],
    ['Melton_relative_relief', '(rilievo/1000) / √A', '0,25211 / √0,4986', '0,3570', '0,3571'],
    ['Hypsometric_integral', '(AE − zmin) / rilievo', '(231,22 − 120,25) / 252,11', '0,4402', '0,4400'],
    ['Elongation_ratio', '2·√(A/π) / L', '2·√(0,4986/π) / 1,7923', '0,4445', '0,4444'],
    ['Shape_factor', 'L / √A', '1,7923 / √0,4986', '2,5383', '2,5389'],
    ['Compactness', 'P / (2·√(π·A))', '5,17 / (2·√(π·0,4986))', '2,0654', '2,0580'],
    ['Circularity', '4·π·A / P²', '4·π·0,4986 / 5,17²', '0,2344', '0,2361'],
    ['Relief_Ratio', '(rilievo/1000) / L', '0,25211 / 1,7923', '0,1407', '0,1407'],
    ['Relative_relief', 'rilievo / (P·1000)', '252,11 / 5170', '0,0488', '0,0490'],
    ['Reach_Length_Centered_m', 'd monte + d valle', '250 + 250', '500', '503'],
    ['Reach_Slope_Centered', '(z monte − z valle) / lunghezza', '(130,06 − 110,70) / 500', '0,0387', '0,0389'],
    ['Reach_Slope_Centered_is_fallback', 'True solo se il tratto non esiste', 'tratto tracciato', 'False', 'False'],
]
tabella(['Variabile', 'Formula', 'Calcolo (ponte 100)', 'Verifica', 'Codice'], C, [4.4, 3.8, 4.4, 2.0, 2.0], dim=8.5)
par("Uso del foglio: aprire Foglio_calcolo_variabili_morfologiche.xlsx, copiare il foglio \"Modello\" (tasto destro "
    "sulla linguetta › Sposta o copia › Crea una copia) e rinominarlo con il numero del ponte; inserire le misure "
    "nelle celle gialle e i valori del codice (da parametri morfologici.csv) nella colonna G. Le celle verdi e la "
    "colonna delle differenze si calcolano da sole. Il foglio \"Esempio ponte 100\" è già compilato con la prova.")
figura(SB, 'C1_foglio_calcolo.png', 'foglio di calcolo compilato per il ponte 100: misure (giallo), variabili calcolate '
                                    '(verde), valori del codice e differenze', 16.5)

# ============================================================ PARTE D
a_capo_pagina()
doc.add_heading('Parte D – Confronto, problemi frequenti e documentazione', 1)
doc.add_heading('D1 – Risultato completo della verifica del ponte 100', 2)
R = [['X_UTM33N / Y_UTM33N', '622645,25 / 4469207,10', '622645,25 / 4469207,10', '0'],
     ['Snap_Distance_m', '1,77', '1,8', 'convenzione centro / angolo della cella'],
     ['A_km2', '0,4986', '0,498', '+0,1%'], ['Basin_Perimeter_km', '5,17', '5,15', '+0,4%'],
     ['AE_m', '231,22', '231,18', '+0,02%'], ['Relief_m', '252,11', '252,11', '0'],
     ['Curve_Number_mean', '84,0', '84,0', '0'], ['S', '0,36119', '0,36128', '−0,02%'],
     ['Cell_Slope', '0,0297', '0,0297', '0'], ['Longest_flow_length_km', '1,7923', '1,792', '+0,02%'],
     ['Reach_Slope_Centered', '0,0387', '0,0389', '−0,3%'], ['Reach_Length_Centered_m', '500', '503', '−0,6%'],
     ['Form_factor_FF … Relative_relief', 'vedi Parte C', '', 'entro ±0,7%']]
tabella(['Variabile', 'Verifica QGIS', 'Codice', 'Differenza'], R, [5.2, 4.2, 3.6, 4.0])
par("Il bacino delineato con GRASS e quello del codice differiscono per 26 celle (0,13% dell'area): le parti non "
    "comuni si vedono con Vettore › Strumenti di geoprocessing › Differenza simmetrica.")
figura(SA, '11b_mappa_confronto.png', 'bacino del codice (contorno rosso) e bacino QGIS (verde)', 12)
doc.add_heading('D2 – Tolleranze attese', 2)
tabella(['Gruppo di variabili', 'Differenza attesa', 'Se è maggiore'],
        [['Area, perimetro', 'entro 1-2%', 'controllare la cella di chiusura (A4), il ritaglio (A1), la soglia (A3)'],
         ['Quote, rilievo, CN', 'centimetri / decimali', 'controllare la conversione in metri (A2)'],
         ['S, Cell_Slope', 'qualche millesimo', 'usare il DEM riempito (B4) e la formula esatta'],
         ['Longest_flow_length_km', 'un passo di cella (5-7 m)', 'provare altri punti candidati (B6)'],
         ['Pendenza di tratto', 'pochi millesimi', 'controllare che il punto a monte sia sul canale principale (B7)'],
         ['Variabili derivate', 'come le misure da cui derivano', 'ricontrollare le misure in giallo']],
        [4.3, 4.0, 8.7])
doc.add_heading('D3 – Problemi frequenti', 2)
punti([('GRASS non compare in Processing: ', 'Plugin › Gestisci e installa plugin › Installati › attivare "GRASS GIS provider".'),
       ('r.path dice "No path": ', 'il formato delle direzioni deve essere 45degree (quello di r.watershed).'),
       ('Accumulo negativo vicino ai bordi: ', 'manca l\'opzione -a in r.watershed.'),
       ('Quote 100 volte troppo grandi: ', 'manca il passo A2 (-unscale).'),
       ('Calcolatore raster: errore di formula: ', 'il calcolatore raster di QGIS non conosce pi(); in r.mapcalc '
                                                  'usare le parentesi quadre solo per le celle vicine.'),
       ('Bacino che tocca il bordo del ritaglio: ', 'allargare il ritaglio: il bacino potrebbe essere troncato.'),
       ('Ponte 6 (porzione molto grande): ', 'r.watershed con l\'opzione -m, oppure ritagliare attorno al bacino del '
                                             'codice con un margine di 1-2 km.')])
doc.add_heading('D4 – Documentazione della verifica', 2)
punti([('Cronologia di Processing: ', 'Processing › Cronologia › selezionare tutto › Salva: elenco di tutti gli '
                                      'algoritmi eseguiti con parametri, data e ora.'),
       ('Progetto QGIS: ', 'un progetto (.qgz) per ponte con tutti i layer intermedi.'),
       ('Foglio di calcolo: ', 'un foglio per ponte, compilato con le proprie misure.'),
       ('Schermate: ', 'nominate p_ID_passo.png (es. p100_B6.png), con ID, scala e legenda visibili.'),
       ('Impronte dei file di input: ', 'nel registro, con data e operatore.'),
       ('Relazione di verifica: ', "scritta con parole proprie: metodo, campione, risultati, differenze spiegate, "
                                   "conclusioni e dichiarazione degli strumenti usati (compresa l'eventuale "
                                   "assistenza di strumenti di intelligenza artificiale e ciò che è stato verificato "
                                   "in modo indipendente).")])
doc.save(out)
print('ok', out, 'figure', NFIG[0])
