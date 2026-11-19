"""
Manuale GENERICO (Word + PDF) per la verifica autonoma, ponte per ponte, di tutte le variabili morfologiche con
QGIS 3.34 + GRASS. Input: shape ponti_analisi, DEM unito, Curve Number. Il ponte si indica con NNN (ID del database);
i file hanno il prefisso pNNN_. Le figure sono schermate reali con i file rinominati pNNN_ (dati del ponte 100).
Numeri con il punto decimale.

Uso: python manuale_verifica_generico.py <cartella schermate> <out.docx>
"""
import os
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

SN, out = sys.argv[1:3]
CROP = {'A2a_menu_conversione.png': (300, 50, 1000, 330), '03a_menu_raster_estrazione.png': (300, 50, 1000, 330), '04a_menu_raster_conversione.png': (300, 50, 1000, 330),
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


F = lambda *figs: [(n, d, w) for n, d, w in figs]

# ============================================================ frontespizio
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run('Verifica autonoma delle variabili morfologiche di un ponte')
r.bold, r.font.size = True, Pt(18)
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
t.add_run('Manuale operativo generico, da ripetere per ciascun ponte, con QGIS 3.34 LTR e GRASS. '
          'Dati di partenza: shape dei ponti, DEM unito, Curve Number').italic = True

doc.add_heading('Come usare il manuale', 1)
par("Il manuale descrive la verifica di un ponte qualsiasi. Il ponte si indica con NNN, cioè il suo ID nel database "
    "(da 1 a 212); tutti i file prodotti hanno il prefisso pNNN_ (per il ponte 104: p104_dem_m.tif, p104_bacino.gpkg, "
    "ecc.). Si parte solo dai tre file di input; il confronto con i risultati del codice si fa soltanto alla fine "
    "(Parte D), così non influenza il calcolo.")
tabella(['Parte', 'Contenuto', 'Risultato'],
        [['A - Dal DEM al bacino', 'scelta del ponte, area di lavoro, DEM in metri, direzioni di flusso, reticolo, '
          'sezione di chiusura, bacino, controllo del bordo', 'pNNN_bacino.gpkg'],
         ['B - Misure in QGIS', 'coordinate, area, perimetro, quote, Curve Number, pendenze, percorso di flusso più '
          'lungo, tratto di canale', '17 valori da scrivere nel foglio Calcolo'],
         ['C - Calcoli a mano', 'variabili derivate con le formule, svolte passo per passo', '15 variabili'],
         ['D - Confronto a posteriori', 'confronto con parametri morfologici.csv, tolleranze, errori frequenti, '
          'documentazione', 'foglio Confronto, registro']],
        [4.0, 9.5, 3.5])
par("Le figure sono schermate reali di QGIS 3.34 in italiano. Sono state prese con i file del ponte 100 rinominati "
    "con il prefisso pNNN_: i numeri che si vedono nelle finestre (coordinate, estensioni, distanze) sono quelli del "
    "ponte 100 e vanno sostituiti con quelli del proprio ponte. I valori del ponte 100 sono riportati come esempio "
    "nelle tabelle (colonna \"Esempio ponte 100\"), per controllare di aver capito il procedimento.", italic=True)

doc.add_heading('Scheda del ponte (da compilare durante il lavoro)', 2)
tabella(['Voce', 'Dove si trova', 'Ponte NNN', 'Esempio ponte 100'],
        [['ID', 'campo ID di ponti_analisi', '', '100'],
         ['Soglia del reticolo (celle)', 'campo soglia di ponti_analisi; se vuoto: 4000', '', '4000'],
         ['Distanza del buffer (m)', 'passo A1 (3000 di partenza, raddoppiare se serve)', '', '3000'],
         ['XS, YS (centro della cella di chiusura)', 'passo A4', '', '622646.50, 4469205.85'],
         ['Accumulo nella cella di chiusura', 'passo A4', '', '19942'],
         ['Il bacino tocca il bordo? (si/no)', 'passo A6', '', 'no']],
        [5.0, 5.8, 2.6, 3.6])

# ============================================================ input
doc.add_heading('1. Input, strumenti e impostazioni', 1)
tabella(['File / strumento', 'Contenuto', 'Note'],
        [['ponti_analisi.shp', '212 ponti, EPSG:32633, campi ID e soglia', 'stessi punti usati nel codice'],
         ['DEM unito (dem5m_unico_v4.tif)', 'DEM a 5 m, EPSG:32633', 'quote in centimetri interi con scala 0.01: '
          'vanno convertite in metri (passo A2)'],
         ['Curve Number (cn5m_unico.tif)', 'stessa griglia del DEM', ''],
         ['QGIS 3.34 LTR con GRASS', 'in Processing deve comparire il gruppo GRASS', 'se manca: Plugin | Gestisci e '
          'installa plugin | Installati | GRASS GIS provider'],
         ['Foglio_calcolo_verifica_generico.xlsx', 'fogli Modello calcolo e Modello confronto', 'una copia per ponte']],
        [4.6, 6.0, 6.4])
doc.add_heading('Impostazioni del progetto (una volta sola)', 2)
punti([('Sistema di riferimento: ', 'Progetto | Proprietà | SR: EPSG:32633 (WGS 84 / UTM zone 33N).'),
       ('Misure planimetriche: ', 'Progetto | Proprietà | Generale | Misure | Ellissoide: "Nessuno / Planimetrico". '
                                 'In ogni caso nei calcoli si usano le funzioni area(@geometry), perimeter(@geometry) '
                                 'e length(@geometry), che misurano sul piano come il codice; $area, $perimeter e '
                                 '$length invece misurano sull\'ellissoide e danno valori leggermente diversi.'),
       ('Cartella: ', 'una per ponte, es. C:\\PONTI\\verifica\\ponte_NNN.'),
       ('Impronte dei tre input: ', 'PowerShell: Get-FileHash su ponti_analisi.shp, dem5m_unico_v4.tif, '
                                    'cn5m_unico.tif; copiarle nel registro.'),
       ('Cronologia: ', 'Processing | Cronologia registra ogni algoritmo con parametri, data e ora: non cancellarla.')])

doc.add_heading('2. Le variabili da calcolare', 1)
tabella(['Variabile del CSV', 'Definizione', 'Passo'],
        [['Longitude, Latitude', 'coordinate WGS84 del ponte', 'B1'],
         ['X_UTM33N, Y_UTM33N', 'coordinate UTM 33N del ponte', 'B1'],
         ['Snap_Distance_m', 'distanza tra il ponte e il centro della cella di chiusura', 'A4 + C'],
         ['A_km2, Basin_Perimeter_km', 'area e perimetro del bacino', 'B2'],
         ['AE_m, Relief_m', 'quota media; quota massima - quota minima', 'B3 + C'],
         ['Curve_Number_mean', 'Curve Number medio', 'B3'],
         ['S', 'media della massima pendenza in discesa verso le 8 celle vicine (D8), DEM riempito (m/m)', 'B4'],
         ['Cell_Slope', 'pendenza D8 della cella di chiusura (m/m)', 'B5'],
         ['Longest_flow_length_km', 'percorso di flusso più lungo fino alla sezione', 'B6 + C'],
         ['Reach_Slope_Centered, Reach_Length_Centered_m, Reach_Slope_Centered_is_fallback',
          'pendenza e lunghezza del tratto da 250 m a monte a 250 m a valle; si/no se il tratto non è tracciabile', 'B7 + C'],
         ['Form_factor_FF, Melton_relative_relief, Hypsometric_integral, Elongation_ratio, Shape_factor, '
          'Compactness, Circularity, Relief_Ratio, Relative_relief', 'variabili derivate (formule nella Parte C)', 'C']],
        [6.2, 9.2, 1.6], dim=9)

# ============================================================ PARTE A
a_capo_pagina()
doc.add_heading('Parte A - Dal DEM al bacino', 1)
passo('A0', 'Scelta del ponte', 'Processing | Selezione del vettore | Estrai per attributo',
      ['Layer ponti_analisi; attributo ID; operatore "="; valore NNN. Uscita pNNN_ponte.gpkg.',
       'Annotare nella scheda il campo soglia: se è vuoto la soglia è 4000 celle (0.1 km²).'],
      'pNNN_ponte deve contenere 1 punto.', F(('A0_estrai_per_attributo.png', 'Estrai per attributo: il ponte NNN', 13)), SN)
passo('A1', 'Area di lavoro e ritaglio di DEM e Curve Number',
      'Vettore | Strumenti di geoprocessing | Buffer; Raster | Estrazione | Ritaglia raster da estensione',
      ['Buffer di pNNN_ponte con distanza 3000 m, uscita pNNN_area_lavoro.gpkg. Per corsi d\'acqua grandi la '
       'distanza deve essere maggiore del bacino atteso (decine di km): se al passo A6 il bacino tocca il bordo, '
       'si raddoppia la distanza e si ripetono i passi A1-A5.',
       'Ritaglia raster da estensione: layer = DEM unito; Estensione del ritaglio = pulsante a destra, "Calcola da '
       'layer", pNNN_area_lavoro. Uscita pNNN_dem_ritaglio.tif.',
       'Stessa operazione e stessa estensione sul Curve Number: uscita pNNN_cn.tif.'],
      'il ritaglio è un quadrato centrato sul ponte (ponte 100: 6 x 6 km, 1200 x 1200 celle).',
      F(('A1a_buffer.png', 'Buffer attorno al ponte', 13), ('A1b_ritaglia_dem.png', 'Ritaglio del DEM unito', 13),
        ('A1c_ritaglia_cn.png', 'Ritaglio del Curve Number con la stessa estensione', 13)), SN)
passo('A2', 'Conversione delle quote in metri', 'Raster | Conversione | Trasforma (converti formato)',
      ['Raster in ingresso pNNN_dem_ritaglio; in Parametri avanzati, riga di comando aggiuntiva:  -unscale -ot Float32',
       'Uscita pNNN_dem_m.tif. Da qui in avanti si usa SEMPRE pNNN_dem_m (anche per r.fill.dir al passo B4): il '
       'ritaglio è in centimetri e porterebbe a pendenze 100 volte più grandi.'],
      'con lo strumento Informazioni la quota di una cella deve essere in metri (centinaia), non in centimetri.',
      F(('A2a_menu_conversione.png', 'menu Raster | Conversione', 10),
        ('A2b_trasforma.png', 'Trasforma (converti formato): la Console GDAL/OGR mostra -unscale -ot Float32', 13)), SN)
passo('A3', 'Direzioni di flusso, accumulo e reticolo', 'Processing | GRASS | Raster | r.watershed',
      ['Elevation = pNNN_dem_m; Minimum size of exterior watershed basin = soglia del ponte (4000 se vuota).',
       'Spuntare -s (Single Flow Direction, D8) e -a (positive flow accumulation); dimensione celle della regione 5.',
       'Uscite: accumulo pNNN_accumulo.tif; Drainage direction pNNN_direzioni.tif; Stream segments pNNN_reticolo.tif.'],
      'il reticolo deve seguire i corsi d\'acqua e passare sotto il ponte.',
      F(('A3_r_watershed.png', 'r.watershed: soglia, -s e -a', 13), ('A3_r_watershed_uscite.png', 'r.watershed: uscite', 13),
        ('M1_reticolo.png', 'reticolo (blu) e ponte (triangolo rosso)', 12)), SN)
passo('A4', 'Sezione di chiusura',
      'strumento Informazioni; Processing | Creazione vettore | Crea layer di punti da tabella',
      ['Con lo strumento Informazioni cliccare la cella del reticolo che passa sotto il ponte, la più vicina al punto: '
       'leggere l\'accumulo e le coordinate del CENTRO della cella (XS, YS); scriverle nella scheda.',
       'Creare con il Blocco note pNNN_sezione.csv con due righe:  id,X,Y  e  NNN,XS,YS  (punto come separatore '
       'decimale, es. 100,622646.50,4469205.85).',
       'Crea layer di punti da tabella: tabella pNNN_sezione.csv, campo X = X, campo Y = Y, SR di destinazione '
       'EPSG:32633. Uscita pNNN_sezione.gpkg. (In alternativa: Layer | Aggiungi layer | Testo delimitato, '
       'ricordando di impostare SR della geometria = EPSG:32633, altrimenti il pulsante Aggiungi resta grigio.)'],
      'Informazioni su pNNN_accumulo nel punto creato: deve dare lo stesso accumulo letto prima; accumulo x 25 / '
      '1000000 è già una stima dell\'area in km².',
      F(('M2_sezione_zoom.png', 'cella di chiusura (quadrato giallo) vicino al ponte; accumulo del ponte 100: 19942 celle', 10.5),
        ('A4b_punti_da_tabella.png', 'Crea layer di punti da tabella dal file pNNN_sezione.csv', 13)), SN)
passo('A5', 'Delineazione del bacino',
      'Processing | GRASS | Raster | r.water.outlet; Raster | Conversione | Poligonizzazione; Processing | '
      'Selezione del vettore | Estrai per espressione',
      ['r.water.outlet: direzioni pNNN_direzioni; coordinate XS,YS; dimensione celle 5. Uscita pNNN_bacino.tif.',
       'Poligonizzazione di pNNN_bacino.tif (campo DN): uscita pNNN_bacino_tutti.gpkg.',
       'Estrai per espressione "DN" = 1: salvare SOLO l\'uscita "Elementi corrispondenti" (pNNN_bacino.gpkg) e '
       'lasciare "Mancata corrispondenza" su "Salta risultato".'],
      'pNNN_bacino contiene un solo poligono.',
      F(('A5a_r_water_outlet.png', 'r.water.outlet con le coordinate della cella di chiusura', 13),
        ('A5b_poligonizza.png', 'Poligonizzazione del bacino', 13),
        ('A5c_estrai_dn1.png', 'Estrai per espressione: si salva solo "Elementi corrispondenti"', 13)), SN)
passo('A6', 'Controllo del bordo', 'mappa con pNNN_bacino e pNNN_area_lavoro',
      ['Il bacino non deve toccare il bordo del ritaglio. Se lo tocca, raddoppiare la distanza del buffer e '
       'ripetere A1-A5. Per bacini molto grandi usare in r.watershed anche l\'opzione -m.'],
      None, F(('M3_area_lavoro.png', 'bacino (verde) ben dentro l\'area di lavoro (cerchio rosso)', 10)), SN)

# ============================================================ PARTE B
a_capo_pagina()
doc.add_heading('Parte B - Misure in QGIS', 1)
par('Ogni valore si scrive nella cella gialla del foglio "Calcolo" con la stessa sigla. Tutte le statistiche si '
    'fanno su pNNN_bacino.gpkg (o sulla sua versione con i campi aggiunti).')
passo('B1', 'Coordinate del ponte', 'Processing | Tabella vettore | Aggiungi campi X/Y al layer',
      ['Su pNNN_ponte: SR EPSG:32633, prefisso utm_ (X e Y).',
       'Sul risultato: SR EPSG:4326, prefisso wgs_ (LON e LAT). Uscita pNNN_ponte_coordinate.gpkg.'],
      None, F(('B1a_campi_xy_utm.png', 'campi X/Y in UTM 33N', 13), ('B1b_campi_xy_wgs84.png', 'campi X/Y in WGS84', 13)), SN)
passo('B2', 'Area e perimetro', 'Processing | Tabella vettore | Calcolatore di campi',
      ['Campo area_km2: tipo Decimale (doppia precisione), lunghezza 12, precisione 4, formula  area(@geometry) / 1000000',
       'Campo perim_km: stesso tipo, formula  perimeter(@geometry) / 1000',
       'Non usare $area e $perimeter (misure sull\'ellissoide: es. 0.4988 invece di 0.4986 km² per il ponte 100).'],
      'A deve valere numero di celle del bacino x 25 / 1000000.',
      F(('B2a_calcolatore_area.png', 'Calcolatore di campi: area planimetrica', 13),
        ('B2b_calcolatore_perimetro.png', 'Calcolatore di campi: perimetro planimetrico', 13)), SN)
passo('B3', 'Quote e Curve Number', 'Processing | Analisi raster | Statistiche zonali',
      ['Raster pNNN_dem_m (non riempito), prefisso dem_, statistiche Media, Minimo, Massimo: AE, ZMIN, ZMAX.',
       'Raster pNNN_cn, prefisso cn_, statistica Media: CN.'],
      None, F(('B3a_statistiche_dem.png', 'Statistiche zonali sul DEM: Media, Minimo, Massimo', 13),
              ('B3b_statistiche_cn.png', 'Statistiche zonali sul Curve Number', 13)), SN)
passo('B4', 'Pendenza media di bacino S (metodo D8)',
      'Processing | GRASS | Raster | r.fill.dir; r.mapcalc.simple; Analisi raster | Statistiche zonali',
      ['r.fill.dir: Elevation = pNNN_dem_m (NON pNNN_dem_ritaglio); uscita Depressionless DEM pNNN_dem_riempito.tif.',
       'r.mapcalc.simple: Raster layer A = pNNN_dem_riempito; Formula = espressione qui sotto; dimensione celle 5; '
       'uscita pNNN_pendenza_D8.tif. L\'avviso "SetColorTable() only supported..." si ignora.',
       'Statistiche zonali (Media) di pNNN_pendenza_D8 sul bacino, prefisso S_: S in m/m.'],
      'S è dell\'ordine di 0.1-0.5 m/m in collina; un valore di decine (es. 35.9) significa che è stato usato il DEM '
      'in centimetri.')
codice('max(0, (A-A[-1,0])/5, (A-A[1,0])/5, (A-A[0,-1])/5, (A-A[0,1])/5, (A-A[-1,-1])/7.0711, (A-A[-1,1])/7.0711, '
       '(A-A[1,-1])/7.0711, (A-A[1,1])/7.0711)')
for fg in F(('B4a_r_fill_dir.png', 'r.fill.dir sul DEM in metri', 13), ('B4b_r_mapcalc.png', 'r.mapcalc.simple: parametri avanzati (dimensione celle 5)', 13),
            ('B4c_statistiche_pendenza.png', 'Statistiche zonali della pendenza D8', 13)):
    figura(SN, *fg)
passo('B5', 'Pendenza della cella di chiusura', 'Processing | Analisi raster | Campiona valori raster',
      ['Punti = pNNN_sezione (la cella di chiusura, non il punto del ponte); raster = pNNN_pendenza_D8; prefisso CS_.'],
      'CS è una pendenza in m/m; anche qui un valore 100 volte più grande indica il DEM in centimetri.',
      F(('B5_campiona_cella.png', 'Campiona valori raster sulla cella di chiusura', 13)), SN)
passo('B6', 'Percorso di flusso più lungo',
      'Analisi raster | Calcolatore raster; Creazione vettore | Pixel raster in punti; GRASS | r.path; '
      'Calcolatore di campi; Estrai per espressione',
      ['Idea: il percorso più lungo parte da una cella "sorgente" (accumulo = 1): si tracciano i percorsi da tutte le '
       'sorgenti del bacino e si prende il più lungo. r.path non si ferma alla sezione ma prosegue fino al bordo del '
       'ritaglio lungo la stessa strada per tutti: per questo si sottrae la lunghezza del percorso che parte dalla '
       'sezione.',
       '1) Calcolatore raster (layer pNNN_accumulo e pNNN_bacino):  if ( "pNNN_accumulo@1" = 1 AND "pNNN_bacino@1" = 1, 1, 0/0 )  '
       'con i nomi dei propri layer. Uscita pNNN_sorgenti.tif.',
       '2) Pixel raster in punti: raster in ingresso = pNNN_sorgenti (controllare il menu a tendina: con un raster '
       'sbagliato si ottengono milioni di punti). Uscita pNNN_sorgenti_punti.gpkg; contare gli elementi.',
       '3) r.path: direzioni pNNN_direzioni, formato 45degree, punti di partenza pNNN_sorgenti_punti; uscita '
       'vettoriale pNNN_percorsi_sorgenti.gpkg. Poi r.path con punto di partenza pNNN_sezione: pNNN_percorso_sezione.gpkg.',
       '4) Calcolatore di campi su entrambi: campo lung_m, decimale, lunghezza 12, precisione 2, formula '
       'length(@geometry). Uscite pNNN_percorsi_lung.gpkg e pNNN_percorso_sezione_lung.gpkg.',
       '5) Estrai per espressione  "lung_m" = maximum("lung_m")  su pNNN_percorsi_lung: salvare solo "Elementi '
       'corrispondenti" (pNNN_percorso_piu_lungo.gpkg, 1 linea).',
       '6) LMAX = lung_m di pNNN_percorso_piu_lungo; LSEZ = lung_m di pNNN_percorso_sezione_lung.'],
      'pNNN_percorso_piu_lungo parte sullo spartiacque, in testa al bacino, e a valle della sezione si sovrappone al '
      'percorso dalla sezione.',
      F(('B6a_calcolatore_sorgenti.png', 'Calcolatore raster: celle sorgenti del bacino', 13),
        ('B6b_pixel_in_punti.png', 'Pixel raster in punti (ingresso: pNNN_sorgenti)', 13),
        ('B6c_r_path_sorgenti.png', 'r.path dalle sorgenti, formato 45degree', 13),
        ('B6d_r_path_sezione.png', 'r.path dalla cella di chiusura', 13),
        ('B6e_lunghezza.png', 'Calcolatore di campi: length(@geometry)', 13),
        ('B6f_estrai_massimo.png', 'Estrai per espressione: il percorso più lungo', 13),
        ('M4_percorsi.png', 'sorgenti (arancio), percorso più lungo (rosso), percorso dalla sezione (nero tratteggiato)', 10)), SN)
passo('B7', 'Tratto di canale centrato sulla sezione',
      'Geometria vettore | Interpola punto sulla linea; Analisi raster | Campiona valori raster',
      ['Punto a valle: Interpola punto sulla linea su pNNN_percorso_sezione_lung, distanza 250 (la linea parte dalla '
       'sezione). Uscita pNNN_punto_valle.gpkg.',
       'Punto a monte: Interpola punto sulla linea su pNNN_percorso_piu_lungo, distanza = L x 1000 - 250 = '
       '(LMAX - LSEZ) - 250 (la linea arriva alla sezione dopo L x 1000 metri). Uscita pNNN_punto_monte.gpkg.',
       'Controllo del canale principale: negli ultimi 250 m prima della sezione il percorso deve stare sul ramo con '
       'accumulo maggiore. Se a una confluenza segue un ramo minore, lanciare r.path da una cella del ramo principale '
       'almeno 300 m a monte e usare quella linea (distanza = sua lunghezza - LSEZ - 250).',
       'Campiona valori raster dei due punti su pNNN_dem_m (non riempito), prefisso quota_: ZUP e ZDN; DUP = DDN = 250.',
       'FB (fallback) = si solo se il tratto non si può tracciare (nessuna cella di reticolo a monte e a valle della '
       'sezione): in quel caso la pendenza di tratto è S.'],
      None, F(('B7a_interpola_valle.png', 'Interpola punto sulla linea: 250 m a valle', 13),
              ('B7b_interpola_monte.png', 'Interpola punto sulla linea: L x 1000 - 250 dall\'inizio del percorso più lungo', 13),
              ('B7c_campiona_quota.png', 'Campiona valori raster sul DEM in metri', 13),
              ('M5_tratto.png', 'punti a monte e a valle con le loro quote', 10)), SN)

doc.add_heading('Riepilogo delle misure', 2)
tabella(['Sigla', 'Misura', 'File', 'Campo', 'Esempio ponte 100'],
        [['X, Y', 'coordinate UTM del ponte', 'pNNN_ponte_coordinate', 'utm_x, utm_y', '622645.25, 4469207.10'],
         ['LON, LAT', 'coordinate WGS84 del ponte', 'pNNN_ponte_coordinate', 'wgs_x, wgs_y', '16.444488, 40.364421'],
         ['XS, YS', 'centro della cella di chiusura', 'pNNN_sezione', 'X, Y', '622646.50, 4469205.85'],
         ['A', 'area (km²)', 'pNNN_bacino (campi aggiunti)', 'area_km2', '0.4986'],
         ['P', 'perimetro (km)', 'pNNN_bacino', 'perim_km', '5.170'],
         ['AE, ZMIN, ZMAX', 'quote (m)', 'pNNN_bacino', 'dem_mean, dem_min, dem_max', '231.22, 120.25, 372.36'],
         ['CN', 'Curve Number medio', 'pNNN_bacino', 'cn_mean', '84.0'],
         ['S', 'pendenza media D8 (m/m)', 'pNNN_bacino', 'S_mean', '0.36119'],
         ['CS', 'pendenza della cella (m/m)', 'pNNN_sezione_pendenza', 'CS_1', '0.0297'],
         ['LMAX', 'percorso più lungo (m)', 'pNNN_percorso_piu_lungo', 'lung_m', '5575.23'],
         ['LSEZ', 'percorso dalla sezione (m)', 'pNNN_percorso_sezione_lung', 'lung_m', '3782.91'],
         ['ZUP, ZDN', 'quote a monte e a valle (m)', 'pNNN_punto_monte_quota, pNNN_punto_valle_quota', 'quota_1', '130.06, 110.70'],
         ['DUP, DDN', 'distanze (m)', '-', '-', '250, 250'],
         ['FB', 'tratto non tracciabile', '-', '-', 'no']],
        [2.2, 3.8, 4.6, 3.2, 3.2], dim=8.5)

# ============================================================ PARTE C
a_capo_pagina()
doc.add_heading('Parte C - Calcoli a mano', 1)
par('Ogni formula si scrive prima con i simboli, poi con i numeri del proprio ponte, e si svolge con la '
    'calcolatrice. Il foglio "Calcolo" fa lo stesso conto (celle verdi) e permette di controllarlo. pi = 3.1416; '
    'A in km², P e L in km, quote in m; tenere 4 decimali nei passaggi intermedi.')
tabella(['Variabile', 'Formula', 'Esempio ponte 100: sostituzione', 'Risultato'],
        [['Snap_Distance_m', 'sqrt((XS - X)² + (YS - Y)²)', 'sqrt(1.25² + 1.25²) = sqrt(3.1250)', '1.77 m'],
         ['Longest_flow_length_km (L)', '(LMAX - LSEZ) / 1000', '(5575.23 - 3782.91) / 1000', '1.7923 km'],
         ['Relief_m (REL)', 'ZMAX - ZMIN', '372.36 - 120.25', '252.11 m'],
         ['Form_factor_FF', 'A / L²', '0.4986 / 1.7923² = 0.4986 / 3.2124', '0.1552'],
         ['Melton_relative_relief', '(REL / 1000) / sqrt(A)', '0.25211 / sqrt(0.4986) = 0.25211 / 0.7061', '0.3570'],
         ['Hypsometric_integral', '(AE - ZMIN) / REL', '(231.22 - 120.25) / 252.11 = 110.97 / 252.11', '0.4402'],
         ['Elongation_ratio', '2 x sqrt(A / pi) / L', '2 x sqrt(0.4986 / 3.1416) / 1.7923 = 2 x 0.3984 / 1.7923', '0.4445'],
         ['Shape_factor', 'L / sqrt(A)', '1.7923 / 0.7061', '2.5383'],
         ['Compactness', 'P / (2 x sqrt(pi x A))', '5.170 / (2 x sqrt(1.5664)) = 5.170 / 2.5032', '2.0654'],
         ['Circularity', '4 x pi x A / P²', '4 x 3.1416 x 0.4986 / 5.170² = 6.2656 / 26.7289', '0.2344'],
         ['Relief_Ratio', '(REL / 1000) / L', '0.25211 / 1.7923', '0.1407'],
         ['Relative_relief', 'REL / (P x 1000)', '252.11 / 5170', '0.0488'],
         ['Reach_Length_Centered_m', 'DUP + DDN', '250 + 250', '500 m'],
         ['Reach_Slope_Centered', '(ZUP - ZDN) / (DUP + DDN); se FB = si: S', '(130.06 - 110.70) / 500 = 19.36 / 500', '0.0387'],
         ['Reach_Slope_Centered_is_fallback', 'FB', 'tratto tracciato', 'no']],
        [4.3, 4.2, 6.2, 2.3], dim=8.5)
par('Uso del foglio: copiare "Modello calcolo" e "Modello confronto" (tasto destro sulla linguetta, Sposta o copia, '
    'Crea una copia), rinominarli con il numero del ponte, scrivere le misure nelle celle gialle e il proprio calcolo '
    'a mano nella colonna "Calcolo a mano".')

# ============================================================ PARTE D
a_capo_pagina()
doc.add_heading('Parte D - Confronto a posteriori, errori frequenti, documentazione', 1)
doc.add_heading('D1 - Confronto con il codice', 2)
par('Solo ora si apre parametri morfologici.csv (o il database con le variabili) e si copia la riga del ponte NNN '
    'nella colonna "Valore codice" del foglio Confronto. Attenzione: nel database le pendenze sono in percentuale '
    '(m/m x 100). Per un controllo grafico si può caricare bacini_afferenti.geojson, selezionare il bacino con ID = NNN '
    'e calcolare la Differenza simmetrica con pNNN_bacino.')
doc.add_heading('D2 - Differenze attese', 2)
tabella(['Variabili', 'Differenza attesa', 'Motivo'],
        [['coordinate', 'nessuna', 'stesso punto'],
         ['Snap_Distance_m', 'qualche decimetro', 'la verifica misura al centro della cella, il codice a un suo angolo'],
         ['area, perimetro e derivate', 'entro 1-2%', 'GRASS e il codice instradano il flusso in modo leggermente diverso nelle aree piatte'],
         ['quote, rilievo, CN', 'centimetri / decimali', 'stesso DEM non riempito'],
         ['S, Cell_Slope', 'qualche millesimo', 'riempimento delle depressioni di GRASS diverso da quello del codice'],
         ['Longest_flow_length_km', 'un passo di cella (5-7 m)', 'stesso metodo D8'],
         ['Reach_Length / Reach_Slope', '500 contro circa 500-510 m; pochi millesimi', 'il codice avanza cella per cella fino a superare 250 m']],
        [4.2, 3.8, 9.0])
par('Esempio ponte 100: tutte le 25 variabili entro lo 0.7%, tranne la distanza di aggancio (1.77 contro 1.8 m, per il motivo indicato sopra).')
doc.add_heading('D3 - Errori frequenti (emersi durante le verifiche)', 2)
tabella(['Sintomo', 'Causa', 'Rimedio'],
        [['S circa 35 invece di 0.35; CS circa 3 invece di 0.03', 'r.fill.dir lanciato su pNNN_dem_ritaglio (centimetri)',
          'rifare B4 partendo da pNNN_dem_m'],
         ['area 0.4988 invece di 0.4986, perimetro 5.1711 invece di 5.170', '$area / $perimeter misurano sull\'ellissoide',
          'usare area(@geometry) e perimeter(@geometry)'],
         ['Pixel raster in punti produce milioni di punti con valori 1-8', 'scelto il raster delle direzioni invece di pNNN_sorgenti',
          'rilanciare con pNNN_sorgenti'],
         ['il "percorso più lungo" contiene migliaia di linee', 'salvata l\'uscita "Mancata corrispondenza"',
          'salvare solo "Elementi corrispondenti"'],
         ['testo delimitato: "IL SR deve essere selezionato", Aggiungi grigio', 'SR della geometria non impostato',
          'scegliere EPSG:32633'],
         ['r.path: "No path"', 'formato delle direzioni non impostato', 'formato 45degree'],
         ['accumulo negativo vicino ai bordi', 'manca -a in r.watershed', 'rilanciare A3 con -a'],
         ['il bacino tocca il bordo del ritaglio', 'buffer troppo piccolo', 'raddoppiare il buffer e ripetere A1-A5'],
         ['ZMIN e ZMAX mancanti', 'statistica zonale solo con Media', 'aggiungere Minimo e Massimo (B3)'],
         ['CS diverso dal previsto', 'campionato sul punto del ponte invece che sulla cella di chiusura', 'usare pNNN_sezione']],
        [5.6, 5.6, 5.8], dim=8.5)
doc.add_heading('D4 - Documentazione della verifica', 2)
punti([('Cronologia di Processing: ', 'Processing | Cronologia, selezionare tutto, Salva.'),
       ('Progetto QGIS: ', 'un .qgz per ponte con tutti i layer pNNN_.'),
       ('Foglio di calcolo: ', 'fogli Calcolo e Confronto del ponte, con il calcolo a mano.'),
       ('Schermate: ', 'pNNN_passo.png, con ID, scala e legenda visibili.'),
       ('Registro: ', 'impronte dei tre input, data, operatore, scheda del ponte compilata.'),
       ('Relazione: ', 'scritta con parole proprie: metodo, ponti verificati, risultati, differenze spiegate, '
                       'conclusioni e dichiarazione degli strumenti usati, compresa l\'eventuale assistenza di '
                       'strumenti di intelligenza artificiale e ciò che è stato verificato in modo indipendente.')])

doc.add_heading('Appendice - Elenco dei file di un ponte', 2)
tabella(['File', 'Passo', 'Contenuto'],
        [['pNNN_ponte.gpkg / pNNN_ponte_coordinate.gpkg', 'A0 / B1', 'punto del ponte, con coordinate'],
         ['pNNN_area_lavoro.gpkg', 'A1', 'buffer'],
         ['pNNN_dem_ritaglio.tif / pNNN_dem_m.tif / pNNN_cn.tif', 'A1-A2', 'DEM in cm, DEM in m, CN'],
         ['pNNN_accumulo.tif / pNNN_direzioni.tif / pNNN_reticolo.tif', 'A3', 'uscite di r.watershed'],
         ['pNNN_sezione.csv / pNNN_sezione.gpkg', 'A4', 'cella di chiusura'],
         ['pNNN_bacino.tif / pNNN_bacino_tutti.gpkg / pNNN_bacino.gpkg', 'A5', 'bacino raster e poligono'],
         ['pNNN_dem_riempito.tif / pNNN_pendenza_D8.tif', 'B4', 'DEM riempito e pendenza D8'],
         ['pNNN_sezione_pendenza.gpkg', 'B5', 'pendenza della cella'],
         ['pNNN_sorgenti.tif / pNNN_sorgenti_punti.gpkg', 'B6', 'celle sorgenti'],
         ['pNNN_percorsi_sorgenti / _lung, pNNN_percorso_sezione / _lung, pNNN_percorso_piu_lungo', 'B6', 'percorsi di flusso'],
         ['pNNN_punto_monte / _quota, pNNN_punto_valle / _quota', 'B7', 'punti del tratto e quote']],
        [8.0, 1.8, 7.2], dim=8.5)
doc.save(out)
print('ok', out, 'figure', NFIG[0])
