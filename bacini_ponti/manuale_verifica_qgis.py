"""
Manuale (Word + PDF) per la verifica manuale e indipendente in QGIS dei bacini e dei parametri calcolati dal codice.
Times New Roman 11 pt, testo giustificato, A4.

Uso: python manuale_verifica_qgis.py <out.docx>
"""
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm, Pt, RGBColor

out = sys.argv[1]
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
for liv, dim in ((1, 14), (2, 12)):
    h = doc.styles[f'Heading {liv}']
    h.font.name, h.font.size, h.font.bold = 'Times New Roman', Pt(dim), True
    h.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
    h.paragraph_format.space_before = Pt(12)
    h.paragraph_format.keep_with_next = True


def par(t, bold=False, italic=False):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(t)
    r.bold, r.italic = bold, italic
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


def passo(n, titolo, menu, testo, controlli=None):
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    p.add_run(f'Passo {n} – {titolo}').bold = True
    if menu:
        q = doc.add_paragraph()
        q.paragraph_format.keep_with_next = True
        r = q.add_run('Dove: ')
        r.bold = True
        q.add_run(menu).italic = True
    for t in testo:
        punti([t])
    if controlli:
        q = doc.add_paragraph()
        q.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        q.add_run('Controllo: ').bold = True
        q.add_run(controlli)


def tabella(cols, righe, larghezze, dim=9):
    t = doc.add_table(rows=1, cols=len(cols))
    t.style = 'Table Grid'
    for j, c in enumerate(cols):
        t.rows[0].cells[j].text = c
    for riga in righe:
        cells = t.add_row().cells
        for j, v in enumerate(riga):
            cells[j].text = str(v)
    for i, r_ in enumerate(t.rows):
        for c in r_.cells:
            for p in c.paragraphs:
                p.paragraph_format.keep_with_next = i == 0
                for r in p.runs:
                    r.font.size = Pt(dim)
                    r.font.name = 'Times New Roman'
                    r.bold = i == 0
    t.autofit = False
    for j, wd in enumerate(larghezze):
        t.columns[j].width = Cm(wd)
        for r_ in t.rows:
            r_.cells[j].width = Cm(wd)
    doc.add_paragraph()


# ---------------------------------------------------------------- frontespizio
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run('Verifica manuale in QGIS dei bacini dei ponti')
r.bold, r.font.size = True, Pt(18)
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
t.add_run('Manuale operativo per una verifica indipendente, ripetibile e documentata dei risultati del codice '
          'pysheds_bridges_5m.py').italic = True

doc.add_heading('1. Scopo e principio della verifica', 1)
par("Il manuale descrive come ricalcolare in QGIS, in modo autonomo, il bacino di un ponte e i suoi parametri "
    "principali, e come confrontarli con quelli prodotti dal codice. La verifica è valida se rispetta tre principi:")
punti([('Indipendenza: ', "si usano algoritmi diversi da pysheds (GRASS r.watershed e r.water.outlet), e la sezione "
                         "di chiusura si individua a vista sul reticolo; se due metodi diversi danno lo stesso "
                         "bacino, il risultato è confermato."),
       ('Ripetibilità: ', "ogni passo è registrato nella cronologia di Processing e salvato in un progetto QGIS; "
                          "chiunque, con gli stessi file, deve ottenere gli stessi numeri."),
       ('Tracciabilità: ', "file di input identificati dalla loro impronta (hash), registro di verifica compilato "
                           "a mano, screenshot e commenti scritti da chi esegue la verifica.")])
par("La verifica non ha lo scopo di riprodurre i valori al decimale: algoritmi diversi danno differenze piccole "
    "(vedi capitolo 6). Ha lo scopo di confermare che il bacino è quello giusto e che i parametri sono coerenti, e "
    "di spiegare le eventuali differenze.")

# ---------------------------------------------------------------- materiale
doc.add_heading('2. Materiale necessario', 1)
punti([('Software: ', "QGIS 3.34 LTR o successivo, installato con GRASS (su Windows: installatore OSGeo4W o "
                      "pacchetto standalone, che includono GRASS). Controllare in Processing › Strumenti che "
                      "compaia il gruppo GRASS."),
       ('DEM: ', "dem5m_unico.tif definitivo (quello ottenuto dalle due parti con lo script R), EPSG:32633, celle "
                 "da 5 m. Attenzione: le quote sono salvate in centimetri interi con fattore di scala 0,01 (vedi "
                 "Passo 2)."),
       ('Curve Number: ', 'cn5m_unico.tif, sulla stessa griglia del DEM.'),
       ('Ponti: ', "ponti_analisi.shp (punti usati nel calcolo) e ponti_iniziali.shp (punti di partenza), con "
                   "spostamenti.shp; ponti.csv (colonne porzione, xmin, ymax, xmax, ymin e soglia)."),
       ('Risultati del codice da verificare: ', "parametri morfologici.csv e bacini_afferenti.geojson dell'ultimo run."),
       ('Database: ', 'colonna SUPERFICIE BACINO e pendenza del database finale.')])

# ---------------------------------------------------------------- preparazione
doc.add_heading('3. Preparazione (una volta sola)', 1)
passo(1, 'Cartella di lavoro e impronte dei file', 'PowerShell',
      ["Creare una cartella nuova, ad esempio C:\\PONTI\\verifica_manuale, con una sottocartella per ogni ponte "
       "(ponte_001, ponte_006, ...).",
       "Calcolare l'impronta dei file di input e copiarla nel registro di verifica:  "
       "Get-FileHash C:\\PONTI\\run_v4\\dem5m_unico.tif  (ripetere per cn5m_unico.tif, ponti.csv, "
       "parametri morfologici.csv). L'impronta dimostra senza ambiguità su quali file è stata fatta la verifica."])
passo(2, 'Progetto QGIS e cronologia', 'Progetto › Proprietà; Processing › Cronologia',
      ["Nuovo progetto, SR del progetto EPSG:32633 (WGS 84 / UTM zone 33N); salvarlo nella cartella di lavoro.",
       "Caricare DEM, CN, ponti_analisi.shp, ponti_iniziali.shp, spostamenti.shp e bacini_afferenti.geojson.",
       "Aprire Processing › Cronologia: QGIS registra da solo ogni algoritmo eseguito, con parametri, data e ora. "
       "Non va cancellata: a fine verifica si esporta (capitolo 7)."])

# ---------------------------------------------------------------- campione
doc.add_heading('4. Scelta del campione', 1)
par("Non è necessario verificare tutti i 212 ponti: basta un campione ragionato che copra tutte le situazioni. "
    "Il campione va deciso e motivato da chi fa la verifica; quella che segue è solo una proposta di partenza.")
tabella(['ID', 'Porzione', 'Perché è nel campione'],
        [['1, 2, 27, 36', 'varie', 'compatibili di dimensioni diverse (da 5 a 830 km²)'],
         ['100', 'porzione_07', 'compatibile, bacino piccolo (0,5 km²)'],
         ['6', 'porzione_69', 'bacino molto grande; effetto del buco del DEM chiuso nella versione definitiva'],
         ['21', 'porzione_01', 'refuso nel database (1333 invece di 13,33 km²)'],
         ['44, 200', 'porzione_01, _19', 'quasi compatibili'],
         ['13, 58, 164', 'porzione_54, _26, _17', 'non compatibili, con cause diverse'],
         ['90, 143', 'porzione_64, _08', 'punto spostato sul tracciato del ponte di 10 km e di 1,5 km'],
         ['196', 'porzione_19', 'sezione spostata dopo il confronto con la relazione'],
         ['105', 'porzione_02', 'tombino aperto nel DEM'],
         ['129', 'porzione_26', 'fosso piccolo con soglia di aggancio ridotta (230 celle)']],
        [2.6, 3.6, 10.8])

# ---------------------------------------------------------------- procedura
doc.add_heading('5. Procedura per ciascun ponte', 1)
par("I passi seguenti si ripetono per ogni ponte del campione. Salvare ogni file prodotto nella cartella del "
    "ponte, con un nome che lo identifichi (es. p006_dem_m.tif, p006_bacino.gpkg).")

passo(3, 'Ritaglio del DEM sulla porzione del ponte',
      'Raster › Estrazione › Ritaglia raster per estensione',
      ["Estensione: digitare i limiti della porzione del ponte presi da ponti.csv, nell'ordine xmin, xmax, ymin, "
       "ymax (attenzione: nel CSV l'ordine delle colonne è xmin, ymax, xmax, ymin).",
       "Per i bacini piccoli si può usare un rettangolo più stretto attorno al ponte, purché contenga per intero "
       "il bacino del codice (controllare con bacini_afferenti.geojson)."],
      "il raster ritagliato deve avere celle di 5 m e coprire tutto il bacino del codice.")
passo(4, 'Conversione delle quote in metri',
      'Raster › Conversione › Converti (traduci formato)',
      ["Nei parametri aggiuntivi di creazione scrivere:  -unscale -ot Float32",
       "Il DEM è salvato in centimetri interi con fattore di scala 0,01. QGIS lo applica nella visualizzazione, "
       "ma alcuni strumenti (ad esempio GRASS) leggono i valori grezzi: senza questo passo le quote risulterebbero "
       "100 volte più grandi."],
      "con lo strumento Informazioni cliccare su una cella: la quota deve essere in metri (decine o centinaia, non "
      "decine di migliaia). Controllare anche che le zone senza dato (mare) restino trasparenti; se così non è, "
      "impostare il valore nessun dato nelle proprietà del layer.")
passo(5, 'Direzioni di flusso, accumulo e reticolo',
      'Strumenti di Processing › GRASS › Raster › r.watershed',
      ["Elevation: il DEM in metri del Passo 4.",
       "Minimum size of exterior watershed basin (threshold): 4000 celle (= 0,1 km², la stessa soglia del codice). "
       "Per i ponti con la colonna soglia compilata in ponti.csv usare quel valore (es. 230 per il ponte 129).",
       "Spuntare Enable single flow direction (SFD/D8) (-s): è il metodo D8 usato dal codice.",
       "Spuntare Allow only horizontal and vertical flow? NO (deve restare disattivato).",
       "Per le porzioni grandi (ponte 6) spuntare anche Enable disk swap memory mode (-m).",
       "Regione GRASS: estensione = layer DEM del Passo 4; dimensione cella = 5.",
       "Output da salvare: Number of cells that drain through each cell (accumulo), Drainage direction "
       "(direzioni), Stream segments (reticolo)."],
      "il reticolo deve seguire i corsi d'acqua visibili sull'ortofoto e passare sotto il ponte. "
      "Nota: r.watershed non richiede di riempire prima le depressioni (le attraversa con il suo algoritmo); "
      "è una delle differenze rispetto al codice, che usa fill_pits, fill_depressions e resolve_flats.")
passo(6, 'Individuazione della sezione di chiusura',
      'Strumento Informazioni; layer ponti_analisi.shp e reticolo del Passo 5',
      ["Zoomare sul ponte. Individuare la cella del reticolo che passa sotto il ponte, la più vicina al punto di "
       "ponti_analisi.shp.",
       "Con lo strumento Informazioni sul raster di accumulo leggere il valore della cella e annotare le "
       "coordinate del suo centro (X, Y in UTM 33N) nel registro.",
       "Se il ponte è stato spostato (spostamenti.shp), guardare anche il punto iniziale e annotare nel "
       "registro se la scelta della sezione è condivisa."],
      "la cella deve avere accumulo almeno pari alla soglia; l'accumulo × 25 / 1.000.000 dà già una stima "
      "dell'area del bacino in km², da confrontare con quella del codice.")
passo(7, 'Delineazione del bacino',
      'Strumenti di Processing › GRASS › Raster › r.water.outlet; poi Raster › Conversione › Poligonizzazione',
      ["r.water.outlet: Name of input drainage direction map = direzioni del Passo 5; Coordinates of outlet "
       "point = le coordinate annotate al Passo 6 (formato X,Y). Regione: come al Passo 5.",
       "Poligonizzare il raster del bacino e tenere solo il poligono con valore 1 (selezione per espressione "
       "\"DN\" = 1, poi salvare la selezione come p_ID_bacino.gpkg)."],
      "il poligono deve essere un'unica area chiusa che termina alla sezione del ponte.")
passo(8, 'Area e perimetro',
      'Calcolatore di campi sul layer del bacino',
      ["Nuovo campo area_km2 (decimale): espressione  $area / 1000000",
       "Nuovo campo perim_km (decimale): espressione  $perimeter / 1000"],
      "l'area si confronta con A_km2 del codice e con SUPERFICIE BACINO del database; il perimetro con "
      "Basin_Perimeter_km (il codice conta i lati delle celle, come il poligono ottenuto dal raster).")
passo(9, 'Quota media, rilievo e Curve Number',
      'Strumenti di Processing › Analisi raster › Statistiche zonali',
      ["Layer raster: DEM in metri del Passo 4; layer poligonale: bacino del Passo 7; statistiche: media, minimo, "
       "massimo. La media si confronta con AE_m; massimo − minimo con Relief_m.",
       "Ripetere con cn5m_unico.tif (statistica: media) e confrontare con Curve_Number_mean."],
      "la quota media del codice è calcolata sul DEM originale (non riempito), come in QGIS: le differenze "
      "devono essere piccole.")
passo(10, 'Pendenza media di bacino',
      'Raster › Analisi › Pendenza; Calcolatore raster; Statistiche zonali',
      ["Pendenza in gradi sul DEM in metri; poi con il Calcolatore raster convertirla in percentuale: "
       "tan(\"pendenza@1\" * pi() / 180) * 100",
       "Statistiche zonali (media) sul bacino; confrontare con S del codice × 100 e con la pendenza del database."],
      "il codice calcola la pendenza come massima pendenza D8 verso le 8 celle vicine, QGIS con il metodo di Horn: "
      "i due valori non coincidono, ma devono avere lo stesso ordine di grandezza. Scrivere nel registro la "
      "differenza osservata.")
passo(11, 'Confronto con il bacino del codice',
      'Vettore › Strumenti di geoprocessing › Differenza simmetrica',
      ["Selezionare in bacini_afferenti.geojson il poligono con lo stesso ID e calcolare la differenza simmetrica "
       "con il bacino QGIS.",
       "Area delle parti non comuni / area del bacino del codice = percentuale di non sovrapposizione.",
       "Salvare uno screenshot dei due contorni sovrapposti, con ID, scala e legenda visibili "
       "(Progetto › Importa/Esporta › Esporta mappa come immagine, oppure layout di stampa)."],
      "contorni quasi coincidenti confermano il bacino; parti mancanti o in più indicano una sezione o una "
      "direzione di flusso diversa, da descrivere nel registro.")
passo(12, 'Lunghezza del percorso di flusso (facoltativo)', 'Strumento Misura linea',
      ["Misurare a mano, lungo il reticolo, la distanza tra la sezione e il punto più lontano del bacino: è "
       "un controllo dell'ordine di grandezza di Longest_flow_length_km."])

# ---------------------------------------------------------------- interpretazione
doc.add_heading('6. Come leggere i risultati', 1)
tabella(['Parametro', 'Codice (CSV)', 'QGIS', 'Differenza attesa'],
        [['Area', 'A_km2', 'Passo 8', 'entro 1-2% (stesso DEM e stesso D8); di più solo per sezione o piatti diversi'],
         ['Perimetro', 'Basin_Perimeter_km', 'Passo 8', 'entro qualche %'],
         ['Quota media', 'AE_m', 'Passo 9', 'pochi metri'],
         ['Rilievo', 'Relief_m', 'Passo 9', 'pochi metri'],
         ['Curve Number medio', 'Curve_Number_mean', 'Passo 9', 'decimali'],
         ['Pendenza media', 'S (× 100)', 'Passo 10', 'qualche punto %: metodi diversi (D8 / Horn)'],
         ['Percorso più lungo', 'Longest_flow_length_km', 'Passo 12', 'solo ordine di grandezza']],
        [3.2, 3.6, 2.2, 8.0])
par("Se l'area QGIS differisce da quella del codice più del 2%, controllare nell'ordine: (1) la cella di chiusura "
    "scelta al Passo 6; (2) che il ritaglio contenga tutto il bacino; (3) le aree piatte (piane, invasi), dove "
    "r.watershed e pysheds instradano il flusso in modo diverso; (4) la soglia usata. Il confronto con il "
    "database segue le stesse classi del lavoro: compatibile entro ±15%, quasi compatibile entro ±25% o con "
    "differenza assoluta ≤ 0,1 km² per i bacini piccoli.")

# ---------------------------------------------------------------- documentazione
doc.add_heading('7. Documentazione della verifica', 1)
punti([('Cronologia di Processing: ', "a fine verifica, Processing › Cronologia, selezionare tutto e salvare "
                                      "il registro (pulsante Salva). È l'elenco di tutti gli algoritmi eseguiti, "
                                      "con parametri, data e ora."),
       ('Modello grafico (consigliato): ', "Processing › Modellatore grafico: costruire la catena Passi 3-5 e "
                                         "7 e salvarla come verifica_bacino.model3; permette a chiunque di "
                                         "ripetere la stessa procedura."),
       ('Progetto QGIS: ', 'un .qgz per ponte (o uno unico con un gruppo per ponte) con tutti i layer intermedi.'),
       ('Screenshot: ', 'nominati p_ID_confronto.png, con ID, scala e legenda visibili.'),
       ('Registro di verifica: ', 'una riga per ponte, compilata durante il lavoro (schema qui sotto).')])
tabella(['Colonna del registro', 'Contenuto'],
        [['ID, data, operatore', 'chi ha eseguito la verifica e quando'],
         ['Porzione / ritaglio', 'limiti usati al Passo 3'],
         ['Soglia (celle)', '4000 o valore della colonna soglia'],
         ['Sezione (X, Y)', 'coordinate della cella di chiusura del Passo 6'],
         ['Area QGIS / codice / DB', 'tre valori in km² e differenze %'],
         ['Non sovrapposizione %', 'risultato del Passo 11'],
         ['AE, rilievo, CN, pendenza', 'valori QGIS e del codice'],
         ['Esito', 'confermato / confermato con differenze spiegate / non confermato'],
         ['Commento', 'osservazioni con parole proprie (cosa si vede, perché le differenze)']],
        [5.0, 12.0])

doc.add_heading('8. Casi particolari', 1)
punti([('Ponte 6 (porzione molto grande): ', "r.watershed con l'opzione -m; se il PC non regge, ritagliare il DEM "
                                            "al rettangolo del bacino del codice più un margine di 1-2 km."),
       ('Bacino che tocca il bordo del ritaglio: ', 'allargare il ritaglio: il bacino potrebbe essere troncato.'),
       ('Ponti spostati (90, 143, 196, ...): ', "eseguire i Passi 6-8 anche dal punto iniziale e riportare nel "
                                               "registro le due aree: mostra l'effetto dello spostamento."),
       ('Ponti non compatibili: ', "la verifica non deve rendere compatibile il ponte, ma confermare (o "
                                   "smentire) la causa indicata nel report dei non compatibili.")])

doc.add_heading('9. Il documento finale', 1)
par("Il documento di verifica va scritto da chi ha eseguito la verifica, con parole proprie. Struttura suggerita:")
punti(['Scopo e metodo (riassunto di questo manuale e strumenti usati, con le versioni di QGIS e GRASS).',
       'File verificati e loro impronte.',
       'Campione scelto e motivazione.',
       'Tabella dei risultati (dal registro) e figure di confronto.',
       'Discussione delle differenze e conclusioni: cosa la verifica conferma e cosa no.',
       "Dichiarazione sugli strumenti usati, compresa l'eventuale assistenza di strumenti di intelligenza "
       "artificiale, distinguendo cosa è stato prodotto con il loro aiuto e cosa è stato verificato in modo "
       "indipendente."],
      'List Number')
doc.save(out)
print('ok', out)
