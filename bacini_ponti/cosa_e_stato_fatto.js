// Documento "Cosa e' stato fatto" e risposta ai due punti del messaggio (validazione manuale; database con le
// situazioni dubbie rispetto ai canali di bonifica e alle interferenze multi-asta). Uso: node cosa_e_stato_fatto.js <file.docx>
const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType,
        HeadingLevel, LevelFormat, BorderStyle, Footer, PageNumber } = require('docx');

const FONT = 'Arial';
const bordo = { style: BorderStyle.SINGLE, size: 4, color: 'A6A6A6' };
const bordi = { top: bordo, bottom: bordo, left: bordo, right: bordo };
function runs(t) {
  return t.split(/(\*\*[^*]+\*\*)/).filter(s => s).map(s => s.startsWith('**')
    ? new TextRun({ text: s.slice(2, -2), bold: true, font: FONT }) : new TextRun({ text: s, font: FONT }));
}
const p = (t, o = {}) => new Paragraph({ spacing: { after: 120 }, ...o, children: runs(t) });
const h1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const h2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const li = t => new Paragraph({ numbering: { reference: 'punti', level: 0 }, spacing: { after: 60 }, children: runs(t) });
const vuoto = () => new Paragraph({ spacing: { after: 60 }, children: [] });
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
const C = { multi: 'E8DDF2', bon: 'DDE6F6', nonr: 'F6D5D5', quasi: 'FCE5CC', lont: 'FFF7C7', coord: 'D9F0F0',
            anag: 'EDEDED', ok: 'DFF0D8' };

const doc = new Document({
  title: 'Bacini sottesi ai 212 attraversamenti: cosa e\' stato fatto',
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: 'Title', name: 'Title', basedOn: 'Normal', run: { font: FONT, size: 34, bold: true },
        paragraph: { spacing: { before: 0, after: 120 } } },
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
      p('Cosa è stato fatto dopo la modifica del codice, validazione manuale e database delle situazioni dubbie (canali di bonifica e interferenze multi-asta). Gli identificativi dei ponti (ID 1-212) sono quelli del database.', { spacing: { after: 200 } }),

      h1('In breve'),
      li('**Codice:** modificato solo nella lettura dei dati e nell\'organizzazione del calcolo; le formule non sono cambiate. Rilanciato sui 212 ponti riproduce il database senza differenze (4240 valori).'),
      li('**Validazione manuale:** ponte 100 rifatto a mano in QGIS, tutte le variabili entro lo 0.7%. Ponte 15 (pianura costiera, canale di scolo) con la stessa procedura: bacino identico, differenze su lunghezza del percorso e pendenza dovute alle zone piatte.'),
      li('**Sezioni di calcolo:** per ogni ponte il codice invariato è stato lanciato in tutti i punti in cui il tracciato del ponte incrocia il reticolo: oltre ai 5 multi-asta già segnalati non ci sono altri ponti sotto cui passa un corso d\'acqua più grande di quello usato.'),
      li('**Situazioni dubbie:** 36 ponti segnalati nel database aggiornato e nella mappa QGIS, tra cui 3 canali di bonifica (13, 15, 154) e 5 multi-asta (107, 108, 109, 111, 196). Gli 8 non compatibili sono tutti spiegati.'),

      h1('1. Modifica del codice'),
      p('Il codice pysheds_bridges.py è stato adattato per il DEM a 5 m (righe marcate [MODIFICA 5 m]):'),
      li('DEM e Curve Number letti da un unico file tif invece dei file .asc per finestra.'),
      li('Un solo lancio per i 212 ponti: il codice elabora una porzione del DEM alla volta e alla fine unisce parametri, bacini e reticolo; le porzioni già elaborate vengono saltate.'),
      li('Soglia del reticolo 0.1 km2 (4000 celle da 25 m2); risoluzione delle aree piatte con eps 1e-6 e 10000 iterazioni (con i valori di default le grandi aree piatte restavano senza direzione di deflusso).'),
      li('Colonna facoltativa "soglia" per agganciare i fossi più piccoli di 0.1 km2 (10 ponti); avviso se un bacino tocca il bordo della porzione; compatibilità con numpy 2.'),
      p('**Le formule dei parametri e la sequenza di calcolo non sono cambiate** (riempimento delle depressioni, aree piatte, direzioni D8, accumulo, aggancio, bacino). Il codice è unico per tutti i ponti. **Verifica:** il ricalcolo dei 212 ponti riproduce esattamente i valori del database (20 parametri per ponte, 4240 valori, nessuna differenza).'),

      h1('2. Preparazione del DEM'),
      p('Il DEM è un mosaico unico a 5 m (UTM 33N, quote in centimetri con scala 0.01) con il reticolo di riferimento inciso di 5 m, così il deflusso segue gli alvei anche dove il DEM non li rappresenta. Versioni successive, ognuna in un file nuovo:'),
      tabella(['Versione', 'Intervento', 'Ponti interessati'], [
        ['v2', 'Alto Agri: celle senza dato riempite con Copernicus GLO-30 (30 m, riportato a 5 m e allineato al DEM nella fascia di sovrapposizione), reticolo inciso nelle celle riempite. Tombino nel rilevato del ponte 105.', '6, 105'],
        ['v3', 'Buchi costieri riempiti con le tavole DTM a 5 m e, dove mancano, con Copernicus; il mare resta senza dato. Tombino del ponte 198.', 'ponti costieri, 198'],
        ['v4', 'Buco senza dato di circa 2 km2 nel bacino dell\'Agri riempito con la tavola DTM a 5 m.', '6'],
      ], [1100, 6738, 1800]),
      vuoto(),
      p('Il DEM v4 è quello usato per tutti i risultati. È stato ritagliato in 29 tessere e rimontato: il mosaico coincide cella per cella con il file originale.'),

      h1('3. Scelta delle sezioni di calcolo'),
      p('**Regola.** La sezione di chiusura sta dove il tracciato del ponte nel KML attraversa il reticolo del DEM; se il tracciato incrocia più corsi d\'acqua si prende quello con area maggiore. L\'area della relazione non entra nella scelta.'),
      p('Rispetto alla prima analisi 23 ponti hanno il punto spostato e 8 la sola porzione di calcolo allargata (bacino troncato al bordo):'),
      tabella(['Motivo dello spostamento', 'Ponti', 'ID'], [
        ['punto portato sul tracciato del ponte nel KML', '7', '13, 61, 83, 90, 118, 136, 143'],
        ['fosso più piccolo di 0.1 km2, soglia di aggancio ridotta', '10', '64, 103, 116, 117, 129, 151, 153, 168, 177, 202'],
        ['asta indicata dalla relazione di ispezione (multi-asta)', '5', '107, 108, 109, 111, 196'],
        ['taglio del tombino nel rilevato', '1', '105'],
        ['solo porzione allargata (punto fermo)', '8', '6, 15, 29, 73, 79, 113, 154, 155'],
      ], [4600, 800, 4238]),
      vuoto(),
      tabella(['Classe', 'Prima analisi', 'Analisi finale'], [
        ['compatibile', '174', '186'], ['quasi compatibile', '11', '13'], ['non compatibile', '22', '8'],
        ['senza area relazione', '5', '5']], [3600, 3000, 3038], [C.ok, C.quasi, C.nonr, C.anag]),
      vuoto(),
      p('Sui 23 ponti spostati i non compatibili passano da 17 a 3. Il punto è posto dentro la cella del reticolo (1.25 m dall\'angolo, dove pysheds misura l\'aggancio): con i punti al centro della cella la scelta della cella diventa arbitraria e 4 bacini cambiano, quindi la posizione usata è quella stabile.'),
      h2('Controllo: quali corsi d\'acqua passano sotto ogni ponte'),
      p('Per giustificare la scelta della sezione anche dove non coincide con l\'incrocio tracciato-reticolo, il codice invariato è stato lanciato sul DEM a 5 m in **tutti i punti in cui il tracciato del ponte incrocia il reticolo** (278 punti; tracciato KML, o linea inizio-fine del database se manca). Due incroci con aree entro il 5% sono la stessa asta.'),
      tabella(['Esito', 'Ponti', 'Commento'], [
        ['una sola asta sotto il ponte, quella usata', '158', ''],
        ['anche un affluente più piccolo vicino, usata l\'asta principale', '31', 'l\'area della relazione conferma l\'asta principale'],
        ['un\'asta più grande di quella usata', '7', '107, 108, 109, 196: multi-asta già segnalati; 31 e 162: stesso corso d\'acqua a valle di una piccola confluenza (41.46 contro 39.05 e 7.69 contro 7.05 km2); 77: KML abbinato al ponte sbagliato'],
        ['asta usata non tra gli incroci del tracciato', '3', '111 (multi-asta), 154 (canale di bonifica), 204 (KML abbinato al ponte sbagliato)'],
        ['il tracciato non incrocia il reticolo a 0.1 km2', '13', '10 fossi piccoli calcolati con soglia ridotta; 14, 98, 155 sezione lontana dal ponte (già segnalati)'],
      ], [3300, 700, 5638]),
      vuoto(),
      p('**Oltre ai 5 multi-asta già segnalati non ci sono altre interferenze multi-asta.** Per i non compatibili 19, 58, 118, 164 e 174 sotto il ponte passa una sola asta, quella usata: la differenza non dipende dalla scelta della sezione ma dall\'area della relazione.'),

      h1('4. Validazione manuale'),
      p('Il manuale di verifica descrive la ricostruzione del bacino e dei 25 parametri in QGIS/GRASS partendo solo dal punto del ponte, dal DEM e dal Curve Number, con i calcoli a mano e il confronto con il codice solo alla fine.'),
      tabella(['Ponte', 'Esecuzione', 'Risultato'], [
        ['100', 'a mano in QGIS, seguendo il manuale', 'tutte le variabili entro lo 0.7% (distanza di aggancio 1.77 contro 1.8 m: centro contro angolo della cella)'],
        ['15', 'stessa procedura e stessi algoritmi, eseguita con script PyQGIS/GRASS e controllata (lo script riproduce esattamente i valori del ponte 100)', 'bacino identico (4.0017 contro 4.001 km2, perimetro 17.4 km); quote, CN, pendenza della cella e di tratto entro le tolleranze; percorso più lungo 7.62 contro 6.63 km e pendenza media 0.036 contro 0.030 m/m'],
      ], [800, 3800, 5038]),
      vuoto(),
      p('Il ponte 15 è su un canale di scolo in pianura costiera (rilievo 19 m su 4 km2). Il bacino coincide, ma all\'interno, sulle zone piatte, GRASS e il codice instradano il flusso su percorsi diversi e riempiono le depressioni in modo diverso: è la differenza "aree piatte" prevista dal manuale, che qui pesa di più. Un primo tentativo con ritaglio di 3 km dava un bacino troncato al bordo (3.39 km2): con 6 km il bacino è completo. È lo stesso motivo per cui nel codice la porzione del ponte 15 era stata allargata.'),

      h1('5. Database delle situazioni dubbie'),
      p('Il database (copia del database originale con colonne aggiunte in fondo) segnala 36 ponti; per ognuno categoria, motivazione, azione proposta e, per tutti i 212 ponti, le aste che passano sotto il ponte con la loro area. La mappa QGIS mostra per ogni ponte sezione, tracciato, aste con area, bacino e reticolo, con un segnalibro per ponte.'),
      tabella(['Categoria', 'Ponti', 'ID', 'Significato'], [
        ['canali di bonifica', '3', '13, 15, 154', 'pianura con canali: il canale non è rappresentato nel DEM e il bacino calcolato può essere incompleto (13 e 154: 4.09 km2 contro 18 della relazione; 15: area della relazione assente)'],
        ['multi-asta', '5', '107, 108, 109, 111, 196', 'sotto il ponte passano più aste: sezione sull\'asta indicata dalla relazione, da confermare'],
        ['area relazione non riproducibile', '7', '19, 58, 72, 117, 118, 164, 174', 'nessuna sezione vicino al ponte riproduce l\'area della relazione'],
        ['quasi compatibile', '11', '44, 85, 102, 103, 104, 106, 116, 124, 129, 151, 200', 'differenze contenute, nessuna azione'],
        ['sezione lontana dal ponte', '4', '14, 82, 98, 155', 'sezione a più di 50 m dal ponte del database'],
        ['coordinate database errate', '4', '73, 83, 90, 143', 'un estremo del ponte nel database è lontano dal tracciato KML; sezione corretta'],
        ['anagrafica KML incongruente', '2', '77, 204', 'nel KML i nomi dei due ponti sono scambiati tra le progressive; sezioni e aree corrette'],
      ], [2100, 650, 2300, 4588], [C.bon, C.multi, C.nonr, C.quasi, C.lont, C.coord, C.anag]),
      vuoto(),
      p('Non compatibili (8): 13 e 154 (canali di bonifica), 19, 58, 117, 118, 164 e 174 (area della relazione non riproducibile vicino al ponte).'),

      h1('Contenuto della cartella'),
      tabella(['Cartella o file', 'Contenuto'], [
        ['1_validazione_manuale/ID100', 'verifica manuale del ponte 100: progetto QGIS, file intermedi, foglio di calcolo, manuale'],
        ['1_validazione_manuale/ID15', 'verifica del ponte 15: progetto QGIS, file p15_, cronologia degli algoritmi, foglio Confronto con note'],
        ['2_database_situazioni_dubbie', 'Database_situazioni_dubbie.xlsx, mappa QGIS (situazioni_dubbie.qgs + .gpkg), tabella csv, LEGGIMI'],
        ['3_cosa_e_stato_fatto.docx', 'questo documento'],
      ], [3200, 6438]),
    ],
  }],
});
Packer.toBuffer(doc).then(b => fs.writeFileSync(process.argv[2], b));
