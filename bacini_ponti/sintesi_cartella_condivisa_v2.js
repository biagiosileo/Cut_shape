// Documento di sintesi della cartella condivisa v2 (Word), organizzato per fasi 0-5. Uso: node sintesi_cartella_condivisa_v2.js <file.docx> <dati_sintesi_v2.json>
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

const D = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')); // dati da dati_sintesi_v2.py

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
      p('Sintesi del lavoro svolto, nell\'ordine in cui è stato fatto: modifiche al codice, prima analisi, modifica delle posizioni, confronto delle aree, casi dubbi, verifica manuale. Gli identificativi dei ponti (ID 1-212) sono quelli del database.', { spacing: { after: 200 } }),

      h1('Contenuto della cartella'),
      tabella(['Cartella o file', 'Contenuto'], [
        ['0_modifiche_codice/', 'Codice usato (pysheds_bridges_5m.py) ed elenco delle modifiche.'],
        ['1_prima_analisi/', 'Punti nella posizione iniziale con area e classe della prima analisi (212 ponti); bacini della prima analisi per i 23 ponti poi spostati.'],
        ['2_spostamento_punti/', 'Ponti modificati con posizione iniziale e finale, motivo, area e classe prima e dopo; riepilogo delle classi; verifica con i punti al centro della cella.'],
        ['3_confronto_aree/', 'Risultato finale: reticolo, bacini (uno per ponte, selezionabile per ID), punti di calcolo e tabella di confronto con le aree della relazione.'],
        ['4_casi_dubbi/', 'Database dei casi dubbi su tutto il campione (righe colorate per categoria) e GeoPackage dei 33 ponti segnalati.'],
        ['5_verifica_manuale_ID100/', 'Foglio di verifica del ponte 100, manuale della procedura e file QGIS della verifica.'],
        ['progetto_ponti.qgs', 'Progetto QGIS con un gruppo per fase e i segnalibri (Visualizza, Segnalibri spaziali) per ogni ponte, per i ponti modificati e per i casi dubbi.'],
      ], [2900, 6738]),
      vuoto(),
      p('Sistema di riferimento: UTM 33N (EPSG:32633). Tenere i file nella stessa cartella: il progetto usa percorsi relativi.'),

      h1('0. Modifiche al codice'),
      p('Il codice pysheds_bridges.py è stato adattato per leggere i dati in formato tif e per elaborare tutti i ponti con un solo lancio. Le modifiche sono marcate nel codice con [MODIFICA 5 m] e riguardano solo la lettura dei dati e l\'organizzazione del calcolo:'),
      li('DEM e Curve Number letti da un unico file tif (mosaico delle tavole a 5 m) invece dei file .asc per finestra.'),
      li('Un solo lancio per i 212 ponti: il codice elabora una porzione del DEM alla volta (limiti indicati in ponti.csv) e alla fine unisce parametri, bacini e reticolo. Le porzioni già elaborate vengono saltate, così il calcolo si può riprendere.'),
      li('Soglia del reticolo riportata a 0.1 km2 (4000 celle da 25 m2) per il DEM a 5 m; parametri della risoluzione delle aree piatte aumentati (eps 1e-6, 10000 iterazioni), perché con i valori di default le grandi aree piatte restavano senza direzione di deflusso.'),
      li('Colonna facoltativa "soglia" in ponti.csv per agganciare i fossi più piccoli di 0.1 km2 (10 ponti, punto 2); avviso se un bacino tocca il bordo della porzione; compatibilità con numpy 2.'),
      p('**Le formule dei parametri morfologici e la sequenza di calcolo non sono cambiate** (riempimento delle depressioni, aree piatte, direzioni D8, accumulo, aggancio al reticolo, bacino). Il codice è unico per tutti i ponti e nessuna modifica è stata fatta per un ponte particolare. Il codice rilanciato sui 212 ponti riproduce esattamente i valori del database (20 parametri per ponte, 4240 valori, nessuna differenza).'),

      h1('1. Prima analisi'),
      p('La prima analisi è stata fatta con i punti nella posizione iniziale (file 1_prima_analisi). Per i 23 ponti poi spostati il codice è stato rilanciato, invariato, sulla posizione iniziale, così il confronto misura solo l\'effetto dello spostamento.'),
      tabella(['Classe', 'Prima analisi', 'Analisi finale'], D.riep.map(r => [r[0], String(r[1]), String(r[2])]),
        [3600, 3000, 3038], ['DFF0D8', 'FCE5CC', 'F6D5D5', 'EDEDED']),
      vuoto(),
      p('Nella prima analisi 22 ponti risultavano non compatibili. L\'esame di questi casi ha mostrato che in gran parte il punto non stava sul corso d\'acqua attraversato dal ponte: era sull\'asta principale invece che sul fosso, su un affluente vicino, o lontano dal ponte per coordinate errate.'),

      h1('2. Modifica delle posizioni e perché'),
      p('**Regola.** La sezione di chiusura sta dove il tracciato del ponte nel KML attraversa il reticolo del DEM; se il tracciato incrocia più corsi d\'acqua si prende quello con area drenata maggiore. La regola usa solo la geometria del ponte: **l\'area della relazione non entra nella scelta.** Il codice non è stato modificato per adattarlo ai ponti: sono i punti a essere stati portati sul corso d\'acqua attraversato.'),
      p('Ponti modificati: 23 con il punto spostato e 8 con la sola porzione di calcolo allargata (punto fermo).'),
      tabella(['Tipo di modifica', 'Ponti', 'ID'], D.tipi.map(r => [r[0], String(r[1]), r[2]]), [3900, 700, 5038]),
      vuoto(),
      li('**Tracciato KML:** il punto iniziale non era sul corso d\'acqua attraversato dal tracciato del ponte. Lo spostamento va da 5 m a 1.5 km; per il 90 è di 10 km perché la coordinata del database era errata.'),
      li('**Fossi piccoli:** il corso d\'acqua sotto il ponte drena meno di 0.1 km2 e non fa parte del reticolo generale; il punto è sul fosso e la soglia di aggancio è ridotta al 90% dell\'area del fosso. Senza questa soglia il codice aggancerebbe il corso d\'acqua più grande vicino (per esempio il 103 passa da 27.46 km2 a 0.065 km2).'),
      li('**Relazione di ispezione (107, 108, 109, 111, 196):** sotto il ponte passano più aste; la sezione è sull\'asta indicata dalla relazione. Sono le sole eccezioni alla regola e restano tra i casi dubbi (multi-asta).'),
      li('**Tombino (105):** sezione sul taglio del tombino nel rilevato.'),
      li('**Porzione allargata:** il bacino toccava il bordo della porzione di DEM e risultava troncato; la porzione è stata ingrandita senza spostare il punto.'),
      h2('Effetto sui 23 ponti spostati'),
      tabella(['ID', 'Tipo', 'Spost. (m)', 'A rel. (km2)', 'A prima (km2)', 'Classe prima', 'A finale (km2)', 'Classe finale'],
        D.mossi.map(r => r.slice(0, 8)), [550, 1350, 850, 950, 1000, 1700, 1000, 2238], D.mossi.map(r => r[8])),
      vuoto(),
      p('Sui 23 ponti spostati i non compatibili passano da 17 a 3 (13, 117, 118). I tre restano tra i casi dubbi: il 13 è in pianura lungo un canale, 117 e 118 hanno un\'area della relazione che non si ritrova vicino al ponte.'),
      h2('Posizione del punto nella cella e aggancio'),
      p('Il codice aggancia il punto alla cella del reticolo con la funzione snap_to_mask di pysheds, che misura la distanza dall\'angolo in alto a sinistra della cella. Per questo i punti sono posti a 1.25 m dall\'angolo, dentro la cella del reticolo: la distanza di aggancio è 1.8 m per 210 ponti e la cella agganciata è quella che contiene il punto. Per 114 (8.8 m) e 170 (4.0 m) l\'aggancio va sulla cella adiacente della stessa asta; verificato, aree compatibili.'),
      p('**Verifica:** il codice è stato rilanciato con i punti al centro della cella. Al centro il punto è alla stessa distanza (3.5 m) da quattro angoli e la scelta della cella diventa arbitraria: ' + D.centri + '. La posizione usata è quindi quella stabile.'),
      p('Il reticolo è tracciato dal codice lungo gli angoli delle celle. Nel progetto QGIS è disegnato spostato di mezza cella (2.5 m verso Est e 2.5 m verso Sud), così passa per i centri delle celle e sui punti: lo spostamento è solo grafico e i dati del file non cambiano.'),

      h1('3. Confronto delle aree e classi'),
      p('Classi (come nella legenda del database): compatibile se la differenza con l\'area della relazione è entro il 15%; quasi compatibile se entro il 25%, oppure entro 0.1 km2 e il 50%; non compatibile negli altri casi. Per i ponti 21 e 190 si usa l\'area della relazione corretta per il refuso (13.33 e 2.167 km2).'),
      tabella(['Classe', 'Ponti', 'ID'], [
        ['compatibile', '186', 'tutti gli altri'],
        ['quasi compatibile', '13', '44, 72, 85, 102, 103, 104, 106, 109, 116, 124, 129, 151, 200'],
        ['non compatibile', '8', '13, 19, 58, 117, 118, 154, 164, 174'],
        ['senza area nella relazione', '5', '14, 15, 81, 152, 153'],
      ], [2600, 900, 6138], ['DFF0D8', 'FCE5CC', 'F6D5D5', 'EDEDED']),
      vuoto(),
      p('**Soglia del reticolo.** Una cella fa parte del reticolo quando drena almeno 4000 celle, cioè 0.1 km2. La soglia serve solo a decidere su quale cella si chiude il bacino: il bacino è poi tutta l\'area che drena in quella cella. È unica per tutta l\'area ed è stata scelta tra valori da 0.005 a 1 km2 con una validazione incrociata (scelta su metà dei ponti e verifica sull\'altra metà, ripetuta 500 volte). Fanno eccezione i 10 fossi piccoli del punto 2:'),
      tabella(['ID', '64', '103', '116', '117', '129', '151', '153', '168', '177', '202'],
        [['Soglia (celle)', '2612', '2351', '931', '2918', '230', '303', '2793', '1020', '2906', '2891'],
         ['Area calcolata (km2)', '0.073', '0.065', '0.026', '0.081', '0.006', '0.008', '0.078', '0.028', '0.081', '0.080']],
        [1838, 780, 780, 780, 780, 780, 780, 780, 780, 780, 780]),
      vuoto(),

      h1('4. Casi dubbi su tutto il campione'),
      p('Sui 212 ponti sono segnalati 33 casi, tra cui quelli rispetto ai canali di bonifica (pianura e canali) e alle interferenze multi-asta. Ogni ponte ha una categoria principale; il database (cartella 4) riporta anche motivazione, area dell\'asta alternativa e azione proposta.'),
      tabella(['Categoria', 'Ponti', 'Significato'], [
        ['multi-asta', '5', 'Sotto il ponte passano più aste: va chiarito quale attraversa il ponte.'],
        ['pianura e canali', '2', 'Zona di pianura con canali: il bacino calcolato potrebbe essere incompleto.'],
        ['area relazione non riproducibile', '7', 'Nessuna sezione vicino al ponte riproduce l\'area della relazione.'],
        ['quasi compatibile', '11', 'Differenza di area contenuta (punto 3).'],
        ['sezione lontana dal ponte', '4', 'Sezione a più di 50 m dal ponte del database.'],
        ['coordinate database errate', '4', 'Un estremo del ponte nel database è a 1-20 km dal tracciato KML; il bacino è calcolato nel punto giusto.'],
      ], [2900, 800, 5938], [C.multi, C.pian, C.nonr, C.quasi, C.lont, C.coord]),
      vuoto(),
      p('Gli 11 quasi compatibili (44, 85, 102, 103, 104, 106, 116, 124, 129, 151, 200) hanno differenze contenute e non richiedono azioni (72 e 109 sono in una categoria più specifica). Gli altri casi:'),
      tabella(['ID', 'Categoria', 'A relazione (km2)', 'A codice (km2)', 'Motivazione'],
        casi.map(r => r.slice(0, 5)), [600, 1900, 1050, 1000, 5088], casi.map(r => r[5])),
      vuoto(),
      p('**Osservazioni sul database.** In 4 ponti (73, 83, 90, 143) una delle due coordinate è errata; 21 e 190 hanno un refuso nell\'area della relazione; 5 ponti non hanno l\'area (14, 15, 81, 152, 153). La pendenza media del tratto in 37 ponti non è un numero e dove lo è non è confrontabile con la pendenza calcolata dal codice: va chiarito come è stata ricavata.'),

      h1('5. Verifica manuale (ponte 100)'),
      p('Il ponte 100 è stato verificato passo per passo in QGIS, ricavando in modo indipendente dal codice le grandezze di base (area, perimetro, quote, lunghezze, pendenze, Curve Number) e calcolando da queste gli indici con le formule del codice. I valori coincidono con quelli del codice:'),
      tabella(['Parametro', 'QGIS', 'Codice'], D.v100, [4600, 2500, 2538]),
      vuoto(),
      p('La procedura è descritta nel manuale (cartella 5) in forma valida per qualsiasi ponte: è stato laborioso ricavare alcuni parametri, ma ora la verifica si può ripetere in modo più spedito su altri attraversamenti, in giornata.'),

      h1('Punti da chiarire'),
      li('Multi-asta (107, 108, 109, 111, 196): quale asta attraversa il ponte; se l\'asta principale, l\'area di riferimento cambia.'),
      li('Pianura e canali (13, 154): percorso del canale e collegamento con il bacino collinare indicato dalla relazione.'),
      li('Area non riproducibile (19, 58, 72, 117, 118, 164, 174): sezione di chiusura o dato usato nella relazione.'),
      li('Sezione lontana (14, 82, 98, 155) e coordinate errate (73, 83, 90, 143): posizione del ponte.'),
    ],
  }],
});
Packer.toBuffer(doc).then(b => fs.writeFileSync(process.argv[2], b));
