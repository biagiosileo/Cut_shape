// Documento di sintesi della cartella condivisa (Word). Uso: node sintesi_cartella_condivisa.js <file.docx>
const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType,
        HeadingLevel, LevelFormat, BorderStyle, Footer, PageNumber } = require('docx');

const FONT = 'Arial';
const W = 9638; // larghezza utile A4 con margini di 2 cm (DXA)
const bordo = { style: BorderStyle.SINGLE, size: 4, color: 'A6A6A6' };
const bordi = { top: bordo, bottom: bordo, left: bordo, right: bordo };

const p = (t, o = {}) => new Paragraph({ spacing: { after: 120 }, ...o, children: runs(t) });
function runs(t) {
  // **grassetto** nel testo
  return t.split(/(\*\*[^*]+\*\*)/).filter(s => s).map(s => s.startsWith('**')
    ? new TextRun({ text: s.slice(2, -2), bold: true, font: FONT }) : new TextRun({ text: s, font: FONT }));
}
const h1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const h2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const li = t => new Paragraph({ numbering: { reference: 'punti', level: 0 }, spacing: { after: 60 }, children: runs(t) });

function tabella(intest, righe, larg, colori) {
  const tot = larg.reduce((a, b) => a + b, 0);
  const cella = (t, k, head, fill) => new TableCell({
    borders: bordi, width: { size: larg[k], type: WidthType.DXA },
    shading: head ? { fill: 'D9D9D9', type: ShadingType.CLEAR, color: 'auto' }
                  : (fill ? { fill, type: ShadingType.CLEAR, color: 'auto' } : undefined),
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: [new TextRun({ text: String(t), bold: head, font: FONT, size: 18 })] })],
  });
  return new Table({
    width: { size: tot, type: WidthType.DXA }, columnWidths: larg,
    rows: [new TableRow({ tableHeader: true, children: intest.map((t, k) => cella(t, k, true)) }),
           ...righe.map((r, i) => new TableRow({ children: r.map((t, k) => cella(t, k, false, colori ? colori[i] : null)) }))],
  });
}
const vuoto = () => new Paragraph({ spacing: { after: 60 }, children: [] });

const C = { multi: 'E8DDF2', pian: 'DDE6F6', nonr: 'F6D5D5', quasi: 'FCE5CC', lont: 'FFF7C7', coord: 'D9F0F0' };
const casi = [
  ['107', 'multi-asta', '0.72', '0.744', 'Sotto il ponte passa un canale da 7.16 km2; la sezione e l\'area della relazione sono sul ramo piccolo della confluenza, a 32 m.', C.multi],
  ['108', 'multi-asta', '0.27', '0.270', 'Sotto il ponte passa un canale da 9.18 km2; sezione e relazione sul ramo accanto, a 38 m.', C.multi],
  ['109', 'multi-asta', '0.31', '0.262', 'Sotto il ponte passa un canale da 6.64 km2; sezione sul fosso laterale, a 18 m.', C.multi],
  ['111', 'multi-asta', '14.5', '15.79', 'Sezione sul torrente a 81 m; nel punto del database c\'è un fosso minore da 0.14 km2.', C.multi],
  ['196', 'multi-asta', '0.83', '0.834', 'Sotto il ponte passa l\'asta principale da 87.0 km2; sezione e relazione sull\'affluente, a 130 m.', C.multi],
  ['13', 'pianura e canali', '18.06', '4.092', 'La relazione descrive un bacino collinare; il calcolo segue un canale rettilineo in pianura: bacino forse incompleto.', C.pian],
  ['154', 'pianura e canali', '18.6', '4.091', 'Stessa relazione del 13; sul tracciato del ponte c\'è anche un fosso da 0.51 km2.', C.pian],
  ['19', 'area relazione non riproducibile', '0.63', '0.131', 'Un bacino di 0.63 km2 si chiude a circa 925 m dal ponte.', C.nonr],
  ['58', 'area relazione non riproducibile', '2.63', '58.10', 'Nessuna sezione entro 1 km dal ponte riproduce la relazione.', C.nonr],
  ['72', 'area relazione non riproducibile', '116.1', '95.04', 'Differenza -18%; nessuna asta alternativa vicino al ponte.', C.nonr],
  ['117', 'area relazione non riproducibile', '0.38', '0.081', 'Un bacino di 0.38 km2 si chiude a circa 460 m dal ponte.', C.nonr],
  ['118', 'area relazione non riproducibile', '0.45', '0.751', 'Un bacino di 0.45 km2 si chiude a circa 900 m dal ponte.', C.nonr],
  ['164', 'area relazione non riproducibile', '0.75', '215.6', 'Il ponte scavalca un corso d\'acqua da 215.6 km2: probabile fosso minore o refuso nella relazione.', C.nonr],
  ['174', 'area relazione non riproducibile', '6.83', '22.25', 'Nessuna sezione entro 2 km dal ponte riproduce la relazione.', C.nonr],
  ['14', 'sezione lontana dal ponte', '-', '0.213', 'Sezione a 204 m dal ponte del database; area della relazione assente.', C.lont],
  ['82', 'sezione lontana dal ponte', '6.4', '6.56', 'Viadotto di 1.2 km; sezione a 110 m dall\'asse del database.', C.lont],
  ['98', 'sezione lontana dal ponte', '0.1', '0.107', 'Sezione a 165 m dal ponte del database.', C.lont],
  ['155', 'sezione lontana dal ponte', '21.17', '23.98', 'Sezione a 127 m dal ponte del database (zona con buco del DEM riempito).', C.lont],
  ['73', 'coordinate database errate', '119.74', '119.3', 'Coordinata finale a 1.0 km dal ponte; sezione a 7 m dal tracciato KML.', C.coord],
  ['83', 'coordinate database errate', '121.0', '120.5', 'Coordinata iniziale a 1.6 km dal ponte; sezione a 8 m dal tracciato KML.', C.coord],
  ['90', 'coordinate database errate', '191.5', '195.7', 'Coordinata finale a 20 km dal ponte; sezione a 12 m dal tracciato KML.', C.coord],
  ['143', 'coordinate database errate', '0.36', '0.333', 'Coordinata finale a 3.0 km dal ponte; sezione a 8 m dal tracciato KML.', C.coord],
];

const doc = new Document({
  creator: 'Biagio',
  title: 'Bacini sottesi ai 212 attraversamenti',
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: 'Title', name: 'Title', basedOn: 'Normal', run: { font: FONT, size: 34, bold: true },
        paragraph: { spacing: { before: 0, after: 120 }, keepNext: true } },
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 26, bold: true, color: '1F3864' },
        paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 22, bold: true, color: '1F3864' },
        paragraph: { spacing: { before: 200, after: 100 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: 'punti', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•',
    alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ children: ['Pagina ', PageNumber.CURRENT], font: FONT, size: 16, color: '808080' })] })] }) },
    children: [
      new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun('Bacini sottesi ai 212 attraversamenti')] }),
      p('Sintesi del calcolo, della soglia del reticolo e dei casi dubbi. Gli identificativi dei ponti (ID 1-212) sono quelli del database.', { spacing: { after: 200 } }),

      h1('1. Contenuto della cartella'),
      tabella(['File', 'Contenuto'], [
        ['1_reticolo_idrografico.gpkg', 'Reticolo idrografico calcolato dal codice su tutta l\'area (62 416 tratti, circa 25 600 km).'],
        ['2_bacini_codice.gpkg', 'Un poligono per ogni ponte (212), selezionabile per ID, con area calcolata, area della relazione, classe, caso dubbio e parametri principali.'],
        ['3_punti_attraversamenti.gpkg', 'Le 212 sezioni di chiusura su cui è stato lanciato il codice, con coordinate, soglia di aggancio e distanza di aggancio.'],
        ['4_casi_dubbi/', 'Database_casi_dubbi.xlsx (database con le colonne dei casi dubbi, righe colorate) e casi_dubbi.gpkg (33 ponti, tracciato del ponte nel KML e nel database, distanza della sezione dal ponte).'],
        ['5_documento_sintesi.docx', 'Questo documento.'],
        ['progetto_ponti.qgs', 'Progetto QGIS che apre tutti i file con gli stili e i segnalibri per ogni ponte (Visualizza, Segnalibri spaziali).'],
      ], [2900, 6738]),
      vuoto(),
      p('Sistema di riferimento: UTM 33N (EPSG:32633). Tenere i file nella stessa cartella: il progetto usa percorsi relativi.'),

      h1('2. Codice di calcolo'),
      p('Il bacino di ogni ponte è calcolato con il codice pysheds_bridges_5m.py sul DEM unico a 5 m. Per ogni ponte la sequenza è la stessa: riempimento delle depressioni, risoluzione delle aree piatte, direzioni di flusso D8, accumulo, bacino sotteso alla sezione di chiusura, parametri morfologici con le stesse formule.'),
      p('**Il codice è unico e uguale per tutti i 212 ponti.** Rispetto al codice iniziale le modifiche sono generali e non riguardano singoli ponti: DEM a 5 m, soglia del reticolo riportata alla stessa area di 0.1 km2, parametri della risoluzione delle aree piatte, lettura del DEM a porzioni per la memoria, compatibilità con le versioni recenti delle librerie. Nessuna modifica è stata fatta per far tornare l\'area di un ponte.'),
      p('Il DEM è stato preparato una sola volta per tutta l\'area: unione delle tavole a 5 m, riempimento dei buchi senza dato, incisione del reticolo di riferimento, tombino nel rilevato del ponte 198.'),

      h1('3. Soglia del reticolo'),
      p('Una cella del DEM fa parte del reticolo quando drena almeno **4000 celle**. Con celle di 5 x 5 m (25 m2) la soglia corrisponde a **0.1 km2** di bacino. La soglia serve solo a decidere su quale cella del reticolo si chiude il bacino: il bacino è poi tutta l\'area che drena in quella cella, qualunque sia la soglia.'),
      p('La soglia è unica per tutta l\'area. È stata scelta tra valori da 0.005 a 1 km2 con una validazione incrociata: scelta su metà dei ponti e verifica sull\'altra metà, ripetuta 500 volte, con la regola di posizionamento delle sezioni descritta al punto 4.'),
      p('**Fossi con bacino inferiore a 0.1 km2.** In 10 ponti il corso d\'acqua attraversato drena meno di 0.1 km2 e con la soglia generale non farebbe parte del reticolo. Per questi la soglia di aggancio è ridotta al 90% dell\'area del fosso (colonna Soglia_aggancio_celle del file 3); il bacino resta quello che drena nella cella della sezione.'),
      tabella(['ID', '64', '103', '116', '117', '129', '151', '153', '168', '177', '202'],
        [['Soglia (celle)', '2612', '2351', '931', '2918', '230', '303', '2793', '1020', '2906', '2891'],
         ['Area calcolata (km2)', '0.073', '0.065', '0.026', '0.081', '0.006', '0.008', '0.078', '0.028', '0.081', '0.080']],
        [1838, 780, 780, 780, 780, 780, 780, 780, 780, 780, 780]),
      vuoto(),

      h1('4. Sezione di chiusura (punti del file 3)'),
      p('Ciò che è definito ponte per ponte è la sezione di chiusura. La regola è la stessa per tutti: la sezione sta dove il tracciato del ponte nel KML attraversa il reticolo del DEM; se il tracciato incrocia più corsi d\'acqua si prende quello con area drenata maggiore. L\'area della relazione non entra nella scelta.'),
      p('Eccezioni, tutte segnalate tra i casi dubbi:'),
      li('**107, 108, 109, 111, 196** (multi-asta): sezione sull\'asta indicata dalla relazione di ispezione. Per questo l\'area calcolata coincide con quella della relazione, ma sotto il ponte passa anche un\'asta con bacino diverso.'),
      li('**14 e 155**: sezione spostata al massimo di 25 m, perché con il condizionamento del DEM del codice cadeva fuori dall\'alveo principale.'),
      p('**Distanza di aggancio.** Il codice aggancia il punto alla cella del reticolo più vicina. Per 210 ponti la distanza è 1.8 m: il punto cade già sul reticolo e la sezione è quella cella (spostamento nullo; 1.8 m è la distanza dall\'angolo della cella, come la misura pysheds). Per 114 (8.8 m) e 170 (4.0 m) il punto cade nella cella accanto al corso d\'acqua e l\'aggancio va sulla cella adiacente della stessa asta: verificato, aree compatibili.'),

      h1('5. Verifiche svolte'),
      li('**Ricalcolo completo:** il codice rilanciato sui 212 ponti con il DEM ricostruito ridà gli stessi valori del database (20 parametri per ponte, 4240 valori, 0 differenze).'),
      li('**Validazione manuale:** il ponte 100 è stato verificato passo per passo in QGIS; area, perimetro, quote, pendenze e indici di forma coincidono con il codice.'),
      li('**Aggancio al reticolo:** controllato per tutti i ponti (punto 4).'),

      h1('6. Confronto con le aree della relazione'),
      p('Classi (come nella legenda del database): compatibile se la differenza è entro il 15%; quasi compatibile se entro il 25%, oppure entro 0.1 km2 e il 50%; non compatibile negli altri casi. Per i ponti 21 e 190 si usa l\'area della relazione corretta per il refuso (13.33 e 2.167 km2).'),
      tabella(['Classe', 'Ponti', 'ID'], [
        ['compatibile', '186', 'tutti gli altri'],
        ['quasi compatibile', '13', '44, 72, 85, 102, 103, 104, 106, 109, 116, 124, 129, 151, 200'],
        ['non compatibile', '8', '13, 19, 58, 117, 118, 154, 164, 174'],
        ['senza area nella relazione', '5', '14, 15, 81, 152, 153'],
      ], [2600, 900, 6138], ['DFF0D8', 'FCE5CC', 'F6D5D5', 'EDEDED']),
      vuoto(),

      h1('7. Casi dubbi'),
      p('Sono segnalati 33 ponti. Ogni ponte ha una categoria principale; il database (cartella 4) riporta anche motivazione, area dell\'asta alternativa e azione proposta.'),
      tabella(['Categoria', 'Ponti', 'Significato'], [
        ['multi-asta', '5', 'Sotto il ponte passano più aste: va chiarito quale attraversa il ponte.'],
        ['pianura e canali', '2', 'Zona di pianura con canali: il bacino calcolato potrebbe essere incompleto.'],
        ['area relazione non riproducibile', '7', 'Nessuna sezione vicino al ponte riproduce l\'area della relazione.'],
        ['quasi compatibile', '11', 'Differenza di area contenuta (vedi punto 6).'],
        ['sezione lontana dal ponte', '4', 'Sezione a più di 50 m dal ponte del database.'],
        ['coordinate database errate', '4', 'Un estremo del ponte nel database è a 1-20 km dal tracciato KML; il bacino è calcolato nel punto giusto.'],
      ], [2900, 800, 5938], [C.multi, C.pian, C.nonr, C.quasi, C.lont, C.coord]),
      vuoto(),
      p('Gli 11 quasi compatibili (44, 85, 102, 103, 104, 106, 116, 124, 129, 151, 200) hanno differenze contenute e non richiedono azioni. I 2 quasi compatibili restanti della tabella al punto 6 (72 e 109) sono classificati in una categoria più specifica. Gli altri casi:'),
      tabella(['ID', 'Categoria', 'A relazione (km2)', 'A codice (km2)', 'Motivazione'],
        casi.map(r => r.slice(0, 5)), [600, 1900, 1050, 1000, 5088], casi.map(r => r[5])),
      vuoto(),

      h1('8. Osservazioni sul database'),
      li('**Coordinate:** in 4 ponti (73, 83, 90, 143) una delle due coordinate del ponte è errata (punto 7).'),
      li('**Aree:** 21 e 190 hanno un refuso nell\'area della relazione (1333 invece di 13.33 e 21.67 invece di 2.167 km2); 5 ponti non hanno l\'area (14, 15, 81, 152, 153).'),
      li('**Pendenza media del tratto:** in 37 ponti non è un numero (34 giudizi a parole, "N.D." per 152 e 153, "01:15:00" per il 109, probabilmente 1:15). Dove è un numero (175 ponti) i valori arrivano al 45% e non sono confrontabili con la pendenza di tratto calcolata dal codice: va chiarito come è stata ricavata prima di un confronto.'),

      h1('9. Punti da chiarire'),
      li('Multi-asta (107, 108, 109, 111, 196): quale asta attraversa il ponte; se l\'asta principale, l\'area di riferimento cambia.'),
      li('Pianura e canali (13, 154): percorso del canale e collegamento con il bacino collinare indicato dalla relazione.'),
      li('Area non riproducibile (19, 58, 72, 117, 118, 164, 174): sezione di chiusura o dato usato nella relazione.'),
      li('Sezione lontana (14, 82, 98, 155) e coordinate errate (73, 83, 90, 143): posizione del ponte.'),
    ],
  }],
});
Packer.toBuffer(doc).then(b => fs.writeFileSync(process.argv[2], b));
