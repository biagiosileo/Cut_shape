// Relazione di verifica del codice pysheds_bridges_5m.py (Word).
// Uso: node relazione_docx.js <relazione.json> <cartella figure> <out.docx>
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, AlignmentType,
  HeadingLevel, ShadingType, BorderStyle, Footer, Header, PageNumber, LevelFormat, PageBreak,
  Math: OMath, MathRun, MathFraction, MathRadical, MathSuperScript, MathSubScript,
} = require('docx');

const [jsonPath, figDir, outPath] = process.argv.slice(2);
const D = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
const FONT = 'Times New Roman';
const W = 9638; // larghezza utile A4 con margini 2 cm (DXA)

// ---------- helper ----------
const t = (text, o = {}) => new TextRun({ text, font: FONT, size: 22, ...o });
const P = (runs, o = {}) => new Paragraph({ children: Array.isArray(runs) ? runs : [t(runs)], spacing: { after: 200, line: 276 }, alignment: AlignmentType.JUSTIFIED, ...o });
const H1 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_1, keepNext: true, children: [new TextRun({ text: s, font: FONT, size: 22, bold: true })], spacing: { before: 360, after: 200 } });
const H2 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true, children: [new TextRun({ text: s, font: FONT, size: 22, bold: true })], spacing: { before: 240, after: 160 } });
const B = (s) => t(s, { bold: true });
const I = (s) => t(s, { italics: true });
const punto = (runs) => new Paragraph({ children: Array.isArray(runs) ? runs : [t(runs)], numbering: { reference: 'punti', level: 0 }, spacing: { after: 100, line: 276 }, alignment: AlignmentType.JUSTIFIED });
const numero = (runs, ref = 'num') => new Paragraph({ children: Array.isArray(runs) ? runs : [t(runs)], numbering: { reference: ref, level: 0 }, spacing: { after: 100, line: 276 }, alignment: AlignmentType.JUSTIFIED });

function pngSize(file) {
  const b = fs.readFileSync(file);
  return [b.readUInt32BE(16), b.readUInt32BE(20)];
}
function figura(nome, didascalia, larghezzaCm = 16) {
  const file = path.join(figDir, nome);
  if (!fs.existsSync(file)) return [P([I(`[figura mancante: ${nome}]`)])];
  const [w, h] = pngSize(file);
  const wpx = Math.round(larghezzaCm / 2.54 * 96);
  const hpx = Math.round(wpx * h / w);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: 'png', data: fs.readFileSync(file), transformation: { width: wpx, height: hpx } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [t(didascalia, { italics: true, size: 20 })] }),
  ];
}
const NESSUNO = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const SPESSO = { style: BorderStyle.SINGLE, size: 12, color: '000000' };
const SOTTILE = { style: BorderStyle.SINGLE, size: 6, color: '000000' };
// tabelle in bianco e nero: filetto spesso sopra e sotto, filetto sottile sotto l'intestazione,
// intestazione in grassetto corsivo, nessuna linea verticale
function tabella(intest, righe, larghezze, opts = {}) {
  const tot = larghezze.reduce((a, b) => a + b, 0);
  const cols = larghezze.map((x) => Math.round(x * W / tot));
  cols[cols.length - 1] += W - cols.reduce((a, b) => a + b, 0);
  const n = righe.length;
  const cella = (txt, k, head, ultima) => new TableCell({
    width: { size: cols[k], type: WidthType.DXA },
    borders: { top: head ? SPESSO : NESSUNO, bottom: head ? SOTTILE : (ultima ? SPESSO : NESSUNO), left: NESSUNO, right: NESSUNO },
    margins: { top: 50, bottom: 50, left: 80, right: 80 },
    verticalAlign: 'center',
    children: [new Paragraph({ alignment: (opts.left && opts.left.includes(k) && !head) ? AlignmentType.LEFT : AlignmentType.CENTER,
      children: [t(String(txt), { size: 20, bold: !!head, italics: !!head })] })],
  });
  return new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: cols,
    borders: { top: NESSUNO, bottom: NESSUNO, left: NESSUNO, right: NESSUNO, insideHorizontal: NESSUNO, insideVertical: NESSUNO },
    rows: [new TableRow({ tableHeader: true, children: intest.map((x, k) => cella(x, k, true, false)) }),
      ...righe.map((r, j) => new TableRow({ cantSplit: true, children: r.map((x, k) => cella(x, k, false, j === n - 1)) }))],
  });
}
const didTab = (s) => new Paragraph({ spacing: { before: 120, after: 280 }, alignment: AlignmentType.CENTER, children: [t(s, { italics: true, size: 20 })] });
// equazioni Word (OMML)
const mr = (s) => new MathRun(s);
const frac = (n, d) => new MathFraction({ numerator: n, denominator: d });
const rad = (c) => new MathRadical({ children: c });
const sup = (c, s) => new MathSuperScript({ children: c, superScript: s });
const sub = (c, s) => new MathSubScript({ children: c, subScript: s });
const eq = (children, nota) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 80, after: nota ? 20 : 140 },
  children: [new OMath({ children })] });
function formula(nome) {
  const file = path.join(figDir, nome + '.png');
  const [w, h] = pngSize(file);
  const scala = 96 / 300 * 0.72; // formule rese a 300 dpi, riportate a ~11 pt
  return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 80, after: 140 },
    children: [new ImageRun({ type: 'png', data: fs.readFileSync(file), transformation: { width: Math.round(w * scala), height: Math.round(h * scala) } })] })];
}
const notaEq = (s) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 140 }, children: [t(s, { size: 18, color: '555555' })] });

const S = D.es;
const sec = [];

// ---------- frontespizio ----------
sec.push(
  new Paragraph({ spacing: { before: 2200, after: 200 }, alignment: AlignmentType.CENTER, children: [t('Verifica del codice pysheds_bridges_5m.py', { bold: true, size: 40 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [t('Bacini idrografici e parametri morfologici dei ponti: verifica su un campione, metodo indipendente e replicabilità', { size: 26, color: '444444' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [t(`Campione: ${D.ids.length} ponti (ID del database ${D.ids.join(', ')})`, { size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [t('DEM 5 m ibrido con reticolo di riferimento inciso · EPSG:32633 · soglia del reticolo 0,1 km²', { size: 20, color: '555555' })] }),
  new Paragraph({ children: [new PageBreak()] }),
);

// ---------- 1. Scopo ----------
sec.push(H1('1. Scopo e campione'));
sec.push(P('La relazione documenta la verifica del codice pysheds_bridges_5m.py, che per ogni ponte delimita il bacino idrografico a monte della sezione di attraversamento e ne calcola i parametri morfologici. La verifica segue il flusso di lavoro del codice, un passo per volta: per ciascun passo riporta le formule implementate, una figura e il confronto sul campione.'));
sec.push(P('La verifica è condotta su due livelli:'));
sec.push(punto([B('Estrazione del bacino. '), t('Il bacino del codice (metodo A, pysheds) è confrontato con un bacino ricavato in modo indipendente (metodo B), con un software, un trattamento delle depressioni e una determinazione della sezione diversi (capitolo 5).')]));
sec.push(punto([B('Calcolo dei parametri. '), t('Sul bacino del codice tutti i parametri sono ricalcolati con codice scritto da zero, che non riusa le funzioni del codice verificato. I parametri derivati sono ricalcolati anche in un foglio Excel con le formule in chiaro (allegato).')]));
sec.push(P('Il campione copre i casi tipici e i casi critici emersi dal confronto con il database:'));
sec.push(tabella(['ID', 'Nome opera', 'Caso', 'Area DB (km²)', 'Area codice (km²)', 'Esito (±15%)'], D.campione, [6, 30, 34, 12, 12, 16], { left: [1, 2] }));
sec.push(didTab('Tab.1 - Campione di verifica. Area codice: risultati del lancio del codice (NEW_parametri_morfologici.csv).'));

// ---------- 2. Flusso ----------
sec.push(H1('2. Modifiche apportate al codice'));
sec.push(P('Il codice verificato è pysheds_bridges_5m.py, ottenuto dal codice originale pysheds_bridges.py. Ogni riga modificata è marcata nel file con il commento [MODIFICA 5 m]. La tabella 2 elenca le modifiche, la sezione del codice in cui si trovano (con il numero di riga nel file modificato) e il motivo.'));
sec.push(tabella(['Modifica', 'Dove (sezione del codice, righe)', 'Motivo'], [
  ['Lettura a porzioni del DEM unico e del CN (GeoTIFF, quote in centimetri riportate in metri) al posto di from_ascii / read_ascii / read_raster', 'Caricamento raster, righe 101–163; descrizione nell\'intestazione, righe 17–26', 'Il DEM unico ha 487 milioni di celle: caricato per intero richiederebbe circa 55 GB di RAM. Ogni porzione contiene per intero i bacini dei suoi ponti'],
  ['Ciclo sulle porzioni (un processo per porzione) e unione finale dei risultati', 'Caricamento raster, righe 101–124', 'Memoria liberata tra una porzione e l\'altra; elaborazione ripartibile'],
  ['Percorsi dei file di ingresso: dem5m_unico.tif, cn5m_unico.tif, ponti.csv', 'CONFIGURAZIONE, righe 56–58', 'Nuovi dati di ingresso'],
  ['ACC_THRESHOLD da 500 a 4000 celle', 'CONFIGURAZIONE, riga 75', 'Soglia del reticolo di 0,1 km² a 5 m, scelta con validazione incrociata sui ponti del database'],
  ['SNAP_DISTANCE_WARNING_M da 50 a 10 m', 'CONFIGURAZIONE, riga 89', 'Le sezioni del CSV sono già sul reticolo: uno snap oltre 10 m va controllato'],
  ['resolve_flats con eps = 1·10⁻⁶ e max_iter = 10 000', 'Condizionamento del DEM, righe 168–170', 'Con i valori predefiniti, sulle grandi aree piatte si creavano pozzi artificiali che interrompevano il bacino (ponti 24 e 25 perdevano 22 km²)'],
  ['Solo i ponti della porzione in elaborazione', 'Coordinate dei ponti, riga 399', 'Conseguenza della lettura a porzioni'],
  ['File di uscita per porzione (parametri, reticolo, bacini) nella cartella porzioni/', 'Righe 245, 540 e 552', 'I file di una porzione non sovrascrivono quelli delle altre'],
  ['Compatibilità con numpy 2: np.in1d = np.isin; np.asarray(basin) nel calcolo del perimetro', 'Righe 44–46 e 496', 'Necessarie con numpy 2; non cambiano i risultati'],
], [34, 28, 38], { left: [0, 1, 2] }));
sec.push(didTab('Tab.2 - Modifiche apportate al codice originale.'));
sec.push(P('Il calcolo dei parametri morfologici (righe 403–537: area, pendenze, quote, CN, percorso di flusso più lungo, perimetro e indici derivati) è invariato rispetto al codice originale, a parte la riga di compatibilità 496. Le formule riportate nei capitoli seguenti sono quindi quelle del codice originale.'));
sec.push(H1('3. Flusso di lavoro'));
sec.push(P('Il codice lavora su un DEM a 5 m (DTM a 5 m, completato con il DEM a 30 m ricampionato dove il 5 m non è disponibile) in cui il reticolo di riferimento è inciso di 5 m, così che l\'acqua segua l\'alveo anche nelle zone pianeggianti. Il DEM è unico ma viene letto a porzioni, ciascuna contenente per intero i bacini dei suoi ponti. Il codice (metodo A) e il metodo indipendente di verifica (metodo B) seguono gli stessi passi: individuazione della sezione, delimitazione del bacino, calcolo dei parametri.'));

// ---------- 3. Passo 1: posizione ----------
sec.push(H1('4. Passo 1 – Posizione dell\'attraversamento e intersezione con il reticolo'));
sec.push(P('Il database riporta per ogni ponte le coordinate di inizio e di fine dell\'attraversamento; il file KML ne riporta il tracciato. La sezione di chiusura è il punto in cui il tracciato del ponte interseca il reticolo idrografico ricavato dal DEM. Se il tracciato interseca più corsi si prende quello con l\'area maggiore; se non ne interseca nessuno, il punto del reticolo più vicino al tracciato.'));
sec.push(P('Il reticolo è l\'insieme delle celle con accumulo di flusso superiore alla soglia:'));
sec.push(...formula('f_reticolo'));
sec.push(P([t('Nel codice la sezione è letta dal CSV (coordinate WGS84) e agganciata alla cella del reticolo più vicina con '), I('snap_to_mask'), t('. Poiché pysheds misura la distanza dagli angoli in alto a sinistra delle celle, il punto del CSV è spostato di 1,25 m verso quell\'angolo: l\'aggancio è così univoco e la distanza di snap riportata dal codice è di circa 1,8 m.')]));
sec.push(...figura(`id${String(S.id).padStart(3, '0')}_posizione.png`, `Fig.1 - Ponte ${S.id} (${S.nome}): punti di inizio e fine del database, tracciato KML, reticolo A (codice) e B (metodo indipendente), sezioni di chiusura A e B.`, 13));
sec.push(P('Nel metodo indipendente la sezione non è presa dal codice ma ricavata di nuovo, con la stessa regola, sul reticolo B. La tabella 3 confronta le due sezioni.'));
sec.push(tabella(['ID', 'Snap del codice (m)', 'Regola della sezione B', 'Distanza sezione A – B (m)'], D.posizione, [8, 18, 50, 20], { left: [2] }));
sec.push(didTab('Tab.3 - Posizione della sezione: codice (A) e metodo indipendente (B).'));
sec.push(P('Nei casi normali le due sezioni distano meno di 10 m (una o due celle). Distanze maggiori si hanno dove il passaggio dell\'acqua attraverso il rilevato stradale dipende dal trattamento delle depressioni (ponte 2), dove il tracciato non tocca il reticolo (129, 106, 107), dove le coordinate del database sono errate (90) e nella piana di bonifica (154).'));

// ---------- 4. Passo 2: area e metodo indipendente ----------
sec.push(H1('5. Passo 2 – Determinazione dell\'area del bacino'));
sec.push(H2('5.1 Metodo del codice (A)'));
sec.push(P('Il codice condiziona il DEM con tre operazioni pysheds: riempimento delle celle isolate (fill_pits), riempimento delle depressioni (fill_depressions) e risoluzione delle aree piatte (resolve_flats, con eps = 1·10⁻⁶ e max_iter = 10 000). Su ogni cella assegna poi la direzione di flusso D8, verso la cella vicina con la pendenza discendente massima:'));
sec.push(...formula('f_d8'));
sec.push(P('Il bacino è l\'insieme delle celle il cui percorso D8 passa per la cella di sezione (catchment). L\'area è il numero di celle per l\'area della cella:'));
sec.push(...formula('f_area'));
sec.push(P(`Per il ponte ${S.id}: ${S.celle} celle × 25 m² = ${S.A} km² (database: ${S.adb} km²).`));
sec.push(H2('5.2 Metodo indipendente (B)'));
sec.push(P('Per una verifica integrale il bacino è ricavato di nuovo, partendo solo dal DEM e dal tracciato del ponte, con scelte diverse in ogni passaggio in cui il risultato potrebbe dipendere dal metodo:'));
sec.push(punto([B('Software diverso: '), t('WhiteboxTools invece di pysheds. Nessuna funzione del codice viene usata.')]));
sec.push(punto([B('Depressioni scavate invece che riempite: '), t('breaching a costo minimo (breach_depressions_least_cost). Le depressioni sono svuotate aprendo un varco lungo il percorso di minimo costo, e solo quelle residue vengono riempite. Il codice invece le riempie fino alla soglia di sfioro. Dove l\'acqua deve superare un rilevato stradale i due metodi possono quindi scegliere varchi diversi.')]));
sec.push(punto([B('Reticolo e sezione ricavati di nuovo: '), t('il reticolo B è dato dalle celle con accumulo superiore a 4000 celle. La sezione B è la cella del reticolo B attraversata dal tracciato KML con l\'accumulo massimo (o, se il tracciato non tocca il reticolo, la cella del reticolo più vicina al tracciato). La sezione del codice non viene usata.')]));
sec.push(punto([B('Bacino: '), t('delimitato a monte della sezione B.')]));
sec.push(P('Il confronto usa l\'area e la sovrapposizione dei due bacini, misurata con l\'indice IoU (Intersection over Union): 100% significa bacini identici, 0% bacini disgiunti. I bacini si considerano concordanti con IoU di almeno il 90%.'));
sec.push(...formula('f_iou'));
sec.push(tabella(['ID', 'A codice (km²)', 'A ricalcolo celle (km²)', 'A poligono (km²)', 'B indipendente (km²)', 'Diff. B/A', 'IoU', 'Area DB (km²)'], D.area, [6, 12, 13, 12, 13, 9, 9, 11]));
sec.push(didTab('Tab.4 - Area del bacino: codice, ricalcolo indipendente sul bacino del codice (conteggio delle celle e area del poligono) e metodo indipendente B.'));
sec.push(...figura(`id${String(S.id).padStart(3, '0')}_bacino.png`, `Fig.2 - Ponte ${S.id}: bacino A (codice, campitura) e bacino B (metodo indipendente, tratteggio), reticolo e percorso di flusso più lungo.`, 13));
sec.push(...figura('sintesi_aree_A_B.png', 'Fig.3 - Area del bacino calcolata dal codice (A) e con il metodo indipendente (B). Fascia grigia: ±15%.', 12));
sec.push(H2('5.3 Esito'));
sec.push(P([t(`In ${D.sintesi.n_ok} ponti su ${D.sintesi.n} (ID ${D.sintesi.id_ok.join(', ')}) i due metodi danno lo stesso bacino: sovrapposizione almeno del 90% e differenza di area al massimo del ${D.sintesi.max_diff_ok}. Nei bacini fino a 250 km² la differenza resta entro l\'1% (3% per il ponte 107); la differenza massima riguarda il ponte 167 (Bradano, circa 2.085 km²), dove una parte delle aree piatte di pianura viene attribuita al bacino da un metodo e non dall\'altro, e il codice resta il più vicino al database. `), t('Il ricalcolo dell\'area sul bacino del codice coincide con il valore del codice sia contando le celle sia misurando il poligono. L\'estrazione del bacino è quindi verificata.')]));
sec.push(P([t(`Nei ponti ${D.sintesi.id_ko.join(', ')} i due metodi danno bacini diversi. Sono i casi critici: tracciato che non tocca il reticolo, coordinate del database errate, piana di bonifica, bacino molto piccolo. Qui il bacino dipende dalle scelte del metodo e `), B('non è determinabile in modo affidabile dal DEM'), t('. È la conferma indipendente di quanto attribuito a questi ponti nell\'analisi delle incompatibilità: errore nel database o bacino non ricostruibile dal DEM.')]));
sec.push(...figura('id154_scheda.png', 'Fig.4 - Ponte 154 (piana di bonifica, Via Idrovora): i due metodi danno bacini disgiunti, il percorso dell\'acqua nelle aree piatte dipende dal metodo.', 16));

// ---------- 5. CN ----------
sec.push(H1('6. Passo 3 – Curve Number'));
sec.push(P('Il Curve Number (CN, metodo SCS-CN) riassume in un numero da 30 a 100 la propensione del bacino a produrre deflusso, in funzione del tipo di suolo e dell\'uso del suolo: valori alti indicano suoli poco permeabili o impermeabilizzati. Il codice ne calcola la media sulle celle del bacino.'));
sec.push(...formula('f_cn'));
sec.push(P('Il CN serve a stimare il deflusso diretto Q prodotto da una pioggia P (in mm):'));
sec.push(...formula('f_scs'));
sec.push(P([t(`Esempio, ponte ${D.scs.id}: CN = ${D.scs.CN}, quindi S = ${D.scs.S} mm e Iₐ = ${D.scs.Ia} mm. Con una pioggia di ${D.scs.P} mm il deflusso diretto è Q = ${D.scs.Q} mm (coefficiente di deflusso ${D.scs.C}), pari a circa ${D.scs.V} m³ sull\'area di ${D.scs.A} km². È l\'ingresso tipico di un idrogramma di piena per la verifica idraulica del ponte.`)]));
sec.push(tabella(['ID', 'CN codice', 'CN ricalcolo', 'CN bacino B'], D.cn.map((r) => [r[0], r[1], r[2], r[4]]), [10, 20, 20, 20]));
sec.push(didTab('Tab.5 - CN medio: codice, ricalcolo indipendente (statistica zonale sul bacino A) e bacino del metodo indipendente.'));

// ---------- 6. Lunghezze ----------
sec.push(H1('7. Passo 4 – Percorso di flusso più lungo e perimetro'));
sec.push(P('Il percorso di flusso più lungo L è la massima distanza, misurata lungo le direzioni D8, tra una cella del bacino e la sezione di chiusura. Ogni passo vale 5 m in direzione ortogonale e 5√2 m in diagonale:'));
sec.push(...formula('f_L'));
sec.push(P('Il codice esplora il bacino a ritroso, dalla sezione verso monte. Il ricalcolo usa un algoritmo diverso: propaga le distanze verso valle, sommando per ogni cella il passo e la distanza della cella di valle (pointer jumping).'));
sec.push(P('Il perimetro P è il contorno del bacino lungo i lati delle celle, compresi eventuali buchi interni:'));
sec.push(...formula('f_P'));
sec.push(P('Il ricalcolo misura invece la lunghezza del poligono del bacino.'));
sec.push(tabella(['ID', 'L codice (km)', 'L ricalcolo (km)', 'L metodo B (km)', 'P codice (km)', 'P ricalcolo (km)', 'P metodo B (km)'], D.lunghezze, [8, 13, 13, 13, 13, 13, 13]));
sec.push(didTab('Tab.6 - Percorso di flusso più lungo e perimetro.'));
sec.push(P('Il perimetro misurato sul contorno a gradini delle celle è più lungo del contorno reale (circa del 4–5% rispetto a un poligono semplificato). È una scelta di definizione del codice, da tenere presente se si confrontano P, Kc e Rc con valori di letteratura.'));

// ---------- 7. Quote e pendenze ----------
sec.push(H1('8. Passo 5 – Quote, ipsometria e pendenze'));
sec.push(P('Le quote sono lette sul DEM in input (quote reali, non condizionate), sulle celle del bacino:'));
sec.push(...formula('f_quote'));
sec.push(P(`Per il ponte ${S.id}: AE = ${S.AE} m, R = ${S.R} m, z_min = ${S.hmin} m, quindi HI = ${S.HI}. L'integrale ipsometrico HI è l'area sottesa alla curva ipsometrica, cioè alla distribuzione delle quote nel bacino.`));
sec.push(P('La pendenza locale di ogni cella è la massima pendenza discendente verso le 8 celle vicine, calcolata sul DEM condizionato; la pendenza media del bacino S è la media sulle celle del bacino:'));
sec.push(...formula('f_s'));
sec.push(P('La pendenza del tratto è calcolata su 500 m di alveo centrati sulla sezione: 250 m a monte lungo il ramo con accumulo maggiore e 250 m a valle lungo la direzione di flusso.'));
sec.push(...formula('f_tratto'));
sec.push(tabella(['ID', 'AE codice (m)', 'AE ricalcolo (m)', 'R codice (m)', 'R ricalcolo (m)', 'S codice', 'S ricalcolo', 'Tratto codice', 'Tratto ricalcolo'], D.quote, [6, 11, 11, 11, 11, 11, 11, 12, 12]));
sec.push(didTab('Tab.7 - Quote e pendenze: codice e ricalcolo indipendente.'));
sec.push(P('Nel DEM in input il reticolo è inciso di 5 m. Per questo la quota minima del bacino, il rilievo e la pendenza del tratto risentono dell\'incisione. Nelle zone pianeggianti la pendenza del tratto può risultare negativa: il punto di valle cade fuori dall\'alveo inciso ed è più alto di quello di monte. Per usi idraulici conviene calcolare quote e pendenze su un DEM non inciso.'));

// ---------- 8. Indici ----------
sec.push(H1('9. Passo 6 – Indici di forma e di rilievo'));
sec.push(P('Gli indici derivati sono calcolati dal codice a partire dalle grandezze primarie (A in km², L e P in km, R, AE e z_min in m). La tabella 8 riporta le formule, verificate ricalcolando ogni indice dalle grandezze primarie del codice. Nell\'Excel di verifica (allegato) le grandezze primarie si possono modificare a mano, una a una, e gli indici si ricalcolano con le stesse formule.'));
sec.push(tabella(['Indice', 'Formula', 'Massima differenza sul campione', 'Esito'], D.derivati, [30, 26, 22, 18], { left: [0, 1] }));
sec.push(didTab('Tab.8 - Indici derivati: formule del codice e verifica (il codice arrotonda gli indici a 4 decimali).'));

// ---------- 9. Esito ----------
sec.push(H1('10. Esito della verifica'));
sec.push(tabella(['Grandezza', 'Massima differenza codice – ricalcolo', 'Tolleranza (arrotondamento del codice)', 'Esito'], D.verifica, [30, 22, 22, 26], { left: [0, 3] }));
sec.push(didTab('Tab.9 - Grandezze primarie: confronto tra il codice e il ricalcolo indipendente sullo stesso bacino.'));
sec.push(punto([B('Calcolo dei parametri: verificato. '), t('Tutte le grandezze primarie e tutti gli indici coincidono con il ricalcolo indipendente entro l\'arrotondamento con cui il codice scrive i risultati.')]));
sec.push(punto([B('Estrazione del bacino: verificata nei casi normali. '), t(`Il metodo indipendente B dà lo stesso bacino in ${D.sintesi.n_ok} ponti su ${D.sintesi.n}.`)]));
sec.push(punto([B('Casi critici: '), t('dove il tracciato non tocca il reticolo, le coordinate del database sono errate o il terreno è piatto, il bacino dipende dal metodo e non va considerato affidabile. Questi ponti vanno verificati su ortofoto o in sopralluogo, non corretti spostando la sezione.')]));
sec.push(punto([B('Avvertenze: '), t('il perimetro a gradini sovrastima P, e le quote e pendenze risentono dell\'incisione del reticolo nel DEM. Entrambe sono scelte di definizione, documentate sopra.')]));

// ---------- 10. Replicabilità ----------
sec.push(H1('11. Replicabilità'));
sec.push(P('Il procedimento è deterministico: a parità di dati in ingresso, versione del codice e impostazioni, i risultati sono identici. Lo dimostra un confronto già eseguito. Il lancio del codice fatto dall\'utente sul proprio computer e quello fatto in modo indipendente su un altro sistema hanno dato, sui 206 ponti confrontabili, gli stessi valori in tutti i 26 parametri, senza differenze nemmeno all\'ultima cifra. Sui 6 ponti restanti coincidono le aree.'));
sec.push(H2('11.1 Dati in ingresso'));
sec.push(punto([B('dem5m_unico.tif: '), t('DEM 5 m unico (25.050 × 19.429 celle), EPSG:32633, quote in centimetri interi con fattore di scala 0,01, reticolo di riferimento inciso di 5 m.')]));
sec.push(punto([B('cn5m_unico.tif: '), t('Curve Number sulla stessa griglia del DEM.')]));
sec.push(punto([B('ponti.csv: '), t('212 ponti con ID del database, coordinate WGS84 della sezione (spostate di 1,25 m verso l\'angolo della cella) e limiti della porzione di DEM.')]));
sec.push(punto([B('controllo_coordinate.gpkg: '), t('tracciati KML e punti di inizio e fine del database, usati dal metodo indipendente.')]));
sec.push(H2('11.2 Impostazioni fisse'));
sec.push(tabella(['Impostazione', 'Valore', 'Dove'], [
  ['Soglia del reticolo', '4000 celle = 0,1 km²', 'codice (ACC_THRESHOLD) e metodo B'],
  ['Risoluzione aree piatte', 'eps = 1·10⁻⁶, max_iter = 10 000', 'codice (resolve_flats)'],
  ['Tratto per la pendenza locale', '500 m (250 a monte, 250 a valle)', 'codice (REACH_LENGTH_CENTERED_M)'],
  ['Avviso di snap', '10 m', 'codice (SNAP_DISTANCE_WARNING_M)'],
  ['Margine delle porzioni', '500 m oltre l\'ingombro del bacino', 'ponti.csv'],
  ['Depressioni nel metodo B', 'breaching a costo minimo, residue riempite', 'relazione_dati_campione.py'],
], [32, 34, 34], { left: [0, 1, 2] }));
sec.push(didTab('Tab.10 - Impostazioni che determinano i risultati.'));
sec.push(H2('11.3 Software'));
sec.push(P('Python 3.13; pysheds 0.5; numpy 2.5; rasterio 1.5 (GDAL 3.12); geopandas 1.2; shapely 2.2; pyproj 3.8; whitebox-workflows 2.0.6. Con numpy 2 il codice include due righe di compatibilità, che non cambiano i risultati.'));
sec.push(H2('11.4 Come ripetere la verifica'));
sec.push(numero([t('Calcolo dei 212 ponti: '), B('python pysheds_bridges_5m.py'), t(' nella cartella con DEM, CN e ponti.csv. Produce parametri morfologici.csv e bacini_afferenti.geojson.')]));
sec.push(numero([t('Metodo indipendente e ricalcolo dei parametri sul campione: '), B('python relazione_dati_campione.py dem5m_unico.tif cn5m_unico.tif ponti.csv controllo_coordinate.gpkg dati 2 1 24 72 106 90 174 129 154 107 167')]));
sec.push(numero([t('Figure: '), B('python relazione_figure.py dati controllo_coordinate.gpkg figure')]));
sec.push(numero([t('Excel di verifica: '), B('python relazione_excel_verifica.py dati "NEW_parametri_morfologici.csv" Database.xlsx Verifica_codice_campione.xlsx')]));
sec.push(P('Gli script sono nel repository di progetto, cartella bacini_ponti (branch claude/validate-watershed-areas-44fj5a). Il campione si può estendere a qualunque ponte passando altri ID allo script del punto 2.'));
sec.push(H2('11.5 Limiti'));
sec.push(punto('La memoria richiesta cresce con la porzione: circa 1 GB ogni 10 milioni di celle. Per il ponte 167 (porzione da 162 milioni di celle) il ricalcolo è stato eseguito in precisione singola e, per il bacino B, il percorso di flusso più lungo non è stato calcolato.'));
sec.push(punto('Il risultato dipende dal DEM in ingresso: un DEM diverso (non inciso, o a risoluzione diversa) dà bacini e parametri diversi, anche se calcolati con lo stesso codice.'));

// ---------- Allegato B ----------
sec.push(H1('Allegato – Excel di verifica e schede dei ponti'));
sec.push(P('Il file Verifica_codice_campione.xlsx accompagna la relazione. Dove possibile le celle contengono formule e non valori: testo nero per le formule, blu per i valori inseriti (dal codice o dal ricalcolo), verde per i collegamenti tra fogli. Contiene quattro fogli:'));
sec.push(punto([B('Legenda: '), t('istruzioni, colori e formule.')]));
sec.push(punto([B('Grandezze primarie: '), t('valori del codice e del ricalcolo indipendente. Area (n. celle × 25 m²) e rilievo (z_max − z_min) del ricalcolo sono formule sui dati di base; differenze e numero di ponti entro tolleranza sono formule.')]));
sec.push(punto([B('Parametri derivati: '), t('le grandezze in ingresso, in celle gialle, sono collegate al foglio precedente e si possono sovrascrivere a mano una alla volta. Gli indici sono formule identiche a quelle del codice, confrontate con il valore scritto dal codice.')]));
sec.push(punto([B('Metodo indipendente: '), t('bacino A e bacino B a confronto: area comune, IoU, aree esclusive e scarti rispetto al database sono formule.')]));
sec.push(P('Le schede illustrate di ciascuno degli 11 ponti del campione (posizione dell\'attraversamento, bacino A e bacino B) sono fornite a parte, insieme alle altre figure, nel file Figure_relazione.zip.'));

const doc = new Document({
  creator: 'Verifica codice pysheds_bridges_5m.py',
  title: 'Verifica del codice pysheds_bridges_5m.py',
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 22, bold: true, color: '000000', font: FONT }, paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 22, bold: true, color: '000000', font: FONT }, paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: 'punti', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: 'num', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [t('Verifica del codice pysheds_bridges_5m.py', { size: 16, color: '888888' })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [t('Pagina ', { size: 16, color: '888888' }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: '888888' })] })] }) },
    children: sec,
  }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(outPath, buf); console.log('salvato', outPath); });
