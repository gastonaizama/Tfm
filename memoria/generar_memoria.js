// Genera memoria/Memoria_TFM.docx a partir de este script, bitacora.json, la configuración
// del proyecto y las capturas de memoria/capturas/.  Uso:  node memoria/generar_memoria.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, ImageRun, PageBreak, TableOfContents, Footer, Header,
  PageNumber, LevelFormat, ExternalHyperlink,
} = require("docx");

const DIR = __dirname;
const RAIZ = path.join(DIR, "..");
const bitacora = JSON.parse(fs.readFileSync(path.join(DIR, "bitacora.json"), "utf8"));
const config = JSON.parse(fs.readFileSync(path.join(RAIZ, "config", "config.json"), "utf8"));
const mapeo = JSON.parse(fs.readFileSync(path.join(RAIZ, "config", "mitre_mapeo.json"), "utf8"));
const mitre = JSON.parse(fs.readFileSync(path.join(RAIZ, "datos", "mitre_tecnicas.json"), "utf8"));
const version = bitacora.versiones[bitacora.versiones.length - 1];

// ---------------------------------------------------------------- estilos y ayudas
const FUENTE = "Calibri";
const ANCHO = 9638; // ancho útil A4 con márgenes de 2 cm (DXA)
const GRIS = "F2F1EE", AZUL = "1F4E79", BORDE = "BFBFBF";

// Texto con **negritas** y `código`
function runs(texto, base = {}) {
  const partes = texto.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return partes.map((p) => {
    if (p.startsWith("**")) return new TextRun({ ...base, text: p.slice(2, -2), bold: true });
    if (p.startsWith("`")) return new TextRun({ ...base, text: p.slice(1, -1), font: "Consolas", size: 19 });
    return new TextRun({ ...base, text: p });
  });
}
const P = (t, o = {}) => new Paragraph({ children: runs(t), spacing: { after: 120, line: 290 }, ...o });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], pageBreakBefore: true });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const V = (t) => new Paragraph({ numbering: { reference: "vinetas", level: 0 }, children: runs(t), spacing: { after: 60 } });
const N = (t, ref = "numeros") => new Paragraph({ numbering: { reference: ref, level: 0 }, children: runs(t), spacing: { after: 60 } });
const nota = (t) => new Paragraph({
  children: runs(t), spacing: { before: 120, after: 160 }, indent: { left: 200, right: 200 },
  shading: { type: ShadingType.CLEAR, fill: "EAF1FB" },
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: "2A78D6", space: 8 } },
});
const codigo = (lineas) => lineas.map((l, i) => new Paragraph({
  children: [new TextRun({ text: l || " ", font: "Consolas", size: 18 })],
  shading: { type: ShadingType.CLEAR, fill: GRIS }, spacing: { after: 0, before: i === 0 ? 80 : 0 },
  indent: { left: 200 },
}));

function tabla(encabezados, filas, anchos) {
  const total = anchos.reduce((a, b) => a + b, 0);
  const borde = { style: BorderStyle.SINGLE, size: 4, color: BORDE };
  const bordes = { top: borde, bottom: borde, left: borde, right: borde };
  const celda = (t, i, cab) => new TableCell({
    width: { size: anchos[i], type: WidthType.DXA }, borders: bordes,
    shading: cab ? { type: ShadingType.CLEAR, fill: AZUL } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: String(t).split("\n").map((linea) => new Paragraph({
      children: runs(linea, cab ? { bold: true, color: "FFFFFF", size: 19 } : { size: 19 }), spacing: { after: 20 },
    })),
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: anchos,
    rows: [
      new TableRow({ tableHeader: true, children: encabezados.map((h, i) => celda(h, i, true)) }),
      ...filas.map((f) => new TableRow({ children: f.map((c, i) => celda(c, i, false)) })),
    ],
  });
}
// Título que no aparece en el índice
const titulo = (t, salto = false) => new Paragraph({ pageBreakBefore: salto, spacing: { before: 240, after: 200 },
  children: [new TextRun({ text: t, bold: true, size: 34, color: AZUL })] });
const espacio = () => new Paragraph({ children: [], spacing: { after: 120 } });

// Imágenes con epígrafe numerado
let nFigura = 0;
function dimensionesPNG(buf) { return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) }; }
function figura(archivo, epigrafe, anchoPx = 600) {
  const buf = fs.readFileSync(path.join(DIR, "capturas", archivo));
  const { w, h } = dimensionesPNG(buf);
  const ancho = Math.min(anchoPx, 620);
  let alto = Math.round((h / w) * ancho);
  const maxAlto = 820;
  const escala = alto > maxAlto ? maxAlto / alto : 1;
  nFigura += 1;
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: buf, transformation: { width: Math.round(ancho * escala), height: Math.round(alto * escala) },
        altText: { title: `Figura ${nFigura}`, description: epigrafe, name: archivo } })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: `Figura ${nFigura}. `, bold: true, size: 18, color: "52514E" }),
        new TextRun({ text: epigrafe, italics: true, size: 18, color: "52514E" })],
    }),
  ];
}

// ---------------------------------------------------------------- contenido
const contenido = [];
const add = (...x) => contenido.push(...x.flat());

// Portada
add(
  new Paragraph({ children: [], spacing: { before: 2200 } }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "MÁSTER EN CYBER THREAT INTELLIGENCE · KSCHOOL", size: 22, color: "52514E", bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400, after: 200 }, children: [new TextRun({ text: "Memoria de trabajo del TFM", size: 30, color: "52514E" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Monitor Ciber-Geopolítico · Argentina", size: 52, bold: true, color: AZUL })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 600 }, children: [new TextRun({ text: "Plataforma de alerta temprana que relaciona hechos geopolíticos con ciberataques hacktivistas contra Argentina", size: 26, italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Caso de estudio: hacktivismo pro-Palestina tras el acercamiento de Argentina a Israel (agosto 2023 – julio 2024)", size: 22 })] }),
  new Paragraph({ children: [], spacing: { before: 1600 } }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Autor: [completar nombre y apellido]", size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Repositorio: github.com/gastonaizama/Tfm  ·  Web: gastonaizama.github.io/Tfm", size: 20, color: "52514E" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200 }, children: [new TextRun({ text: `Versión ${version.version} · ${version.fecha}`, size: 20, color: "52514E" })] }),
  new Paragraph({ children: [new PageBreak()] }),
);

// Control de versiones e índice
add(
  titulo("Control de versiones"),
  P("Esta memoria se genera automáticamente desde el repositorio del proyecto (`memoria/generar_memoria.js`) y se actualiza con cada avance. La bitácora completa está en el Anexo A."),
  tabla(["Versión", "Fecha", "Cambios"], bitacora.versiones.map((v) => [v.version, v.fecha, v.cambios]), [1100, 1400, 7138]),
  espacio(),
  nota("**Cómo actualizar el índice en Word:** al abrir el documento, si Word pregunta si desea actualizar los campos, responda «Sí». También puede hacer clic derecho sobre el índice y elegir «Actualizar campos»."),
  titulo("Índice", true),
  new TableOfContents("Índice", { hyperlink: true, headingStyleRange: "1-2" }),
);

// 1. Introducción
add(
  H1("1. Introducción"),
  H2("1.1. Contexto"),
  P("A partir de 2023, el gobierno argentino profundizó su alineamiento con Israel: el presidente electo anunció su intención de trasladar la embajada a Jerusalén, viajó a Israel en febrero de 2024 y, en paralelo, la justicia argentina atribuyó a Irán la responsabilidad por el atentado a la AMIA. En ese mismo período, distintos grupos hacktivistas pro-Palestina reivindicaron ataques contra sitios y organismos argentinos."),
  P("La hipótesis de trabajo es que **los hechos geopolíticos funcionan como detonantes**: tras ellos, durante algunos días, aumenta la probabilidad de ataques hacktivistas contra objetivos argentinos. Si esto es así, monitorear la agenda geopolítica permite emitir **alertas tempranas** antes de que los ataques ocurran."),
  H2("1.2. Objetivos"),
  N("Construir una plataforma web, pública y gratuita, que monitoree de forma automática noticias y feeds de ciberseguridad y geopolítica."),
  N("Detectar hechos geopolíticos detonantes y ataques contra objetivos argentinos mediante reglas de palabras clave (Fase 1)."),
  N("Emitir un semáforo de riesgo (verde, amarillo, rojo) con una ventana de vigilancia configurable."),
  N("Reconstruir el período de estudio (agosto 2023 – julio 2024) en un modo histórico para evaluar la hipótesis."),
  N("Clasificar los ataques según la matriz MITRE ATT&CK."),
  N("Dejar preparada la integración con inteligencia artificial (Fase 2: Claude Haiku 5.5 para clasificar y Claude Sonnet 5.5 para redactar informes)."),
  H2("1.3. Alcance de esta memoria"),
  P("Este documento registra **todo el trabajo realizado**: requisitos, decisiones, desarrollo, problemas encontrados y cómo se resolvieron, pruebas y estado actual. Está pensado como base para redactar la memoria final del TFM y como evidencia del proceso."),
);

// 2. Metodología
add(
  H1("2. Metodología de trabajo"),
  H2("2.1. Enfoque"),
  P("El proyecto se desarrolló con un enfoque **iterativo y verificable**: cada componente se construyó, se probó con datos reales en el mismo entorno donde funciona la plataforma (GitHub Actions) y se ajustó según los resultados medidos."),
  H2("2.2. Desarrollo asistido por inteligencia artificial"),
  P("El autor no tiene formación previa en programación. El desarrollo se realizó con **Claude Code** (asistente de programación de Anthropic) ejecutándose en un entorno en la nube, de modo que **no fue necesario instalar nada** en la computadora del autor. La división de roles fue la siguiente:"),
  tabla(["Rol", "Responsabilidades"], [
    ["Autor (analista)", "Definir requisitos y caso de estudio; aprobar el plan; tomar decisiones; configurar GitHub (permisos, Pages, rama principal); revisar y aprobar cambios (Pull Requests); investigar y cargar incidentes y hechos clave."],
    ["Asistente (Claude Code)", "Proponer el plan; escribir el código, las pruebas y la documentación; ejecutar verificaciones en GitHub Actions; diagnosticar problemas; explicar cada paso en lenguaje simple."],
  ], [2400, 7238]),
  espacio(),
  P("Toda acción con efectos externos (crear ramas, abrir Pull Requests, cambiar configuraciones) se realizó **con autorización explícita del autor**."),
  H2("2.3. Herramientas"),
  tabla(["Herramienta", "Uso en el proyecto"], [
    ["GitHub (repositorio público)", "Código, datos, documentación e historial de cambios. Forma parte del portfolio del autor."],
    ["GitHub Actions", "Ejecuta automáticamente la recolección y el análisis (cada 6 horas) y la descarga del histórico (cada hora)."],
    ["GitHub Pages", "Publica la página web: https://gastonaizama.github.io/Tfm/"],
    ["Python 3.12", "Lenguaje del programa de monitoreo (librerías: requests y feedparser)."],
    ["HTML, CSS y JavaScript", "Página web sin librerías externas."],
    ["Claude Code", "Asistente de desarrollo (ver 2.2)."],
  ], [2800, 6838]),
);

// 3. Requisitos
add(
  H1("3. Requisitos de la plataforma"),
  P("Los requisitos fueron definidos por el autor al inicio del proyecto:"),
  tabla(["Área", "Requisito"], [
    ["Tecnología", "Repositorio público en GitHub; GitHub Actions cada 6 horas; publicación con GitHub Pages; sin instalaciones locales."],
    ["Fuentes", "GDELT (API de documentos, con historial); RSS de The Record, BleepingComputer, The Hacker News, WeLiveSecurity (ESET), Infobae y La Nación; MITRE ATT&CK."],
    ["Palabras clave geopolíticas", "Argentina junto con Israel, Palestina, Hamás, Irán, embajada, AMIA, ONU."],
    ["Palabras clave cibernéticas", "hackeo, filtración de datos, ataque a sitio web, sitio caído, hacktivistas, gob.ar, Cyber Dragonz, LulzSec Muslims, REM."],
    ["Semáforo", "Verde: sin detonantes. Amarillo: hecho detonante, ventana de 7 días (configurable). Rojo: ataques contra objetivos argentinos dentro de la ventana."],
    ["Pantalla", "Una sola página: semáforo arriba, línea de tiempo con dos carriles en el centro, lista de alertas abajo, selector de fechas (vivo / histórico)."],
    ["Modo histórico", "Agosto 2023 – julio 2024 con GDELT + archivo de incidentes cargados a mano."],
    ["Fases", "Fase 1 sin IA (reglas). Fase 2: Claude Haiku 5.5 clasifica y Claude Sonnet 5.5 redacta un informe solo con alerta; API key como secreto de GitHub."],
    ["Documentación", "README en español (anexo del TFM) y registro de decisiones técnicas."],
  ], [2600, 7038]),
);

// 4. Arquitectura
add(
  H1("4. Arquitectura"),
  P("La plataforma no usa servidores ni bases de datos propias. Todo funciona sobre servicios gratuitos de GitHub:"),
  ...figura("arquitectura.png", "Arquitectura general de la plataforma en la Fase 1."),
  N("**Recolección:** se leen los feeds RSS y se consulta GDELT. Las noticias potencialmente relevantes se acumulan en un archivo propio (`datos/noticias_vivo.json`), porque los feeds RSS no guardan noticias antiguas.", "numeros2"),
  N("**Clasificación:** cada noticia se analiza con reglas de palabras clave y se le asignan técnicas MITRE ATT&CK.", "numeros2"),
  N("**Semáforo:** se calculan los días detonantes, las ventanas de vigilancia, el nivel de cada día y las alertas.", "numeros2"),
  N("**Resultados:** todo se guarda en `web/datos.json` y se registra en el repositorio (historial versionado).", "numeros2"),
  N("**Publicación:** GitHub Pages muestra la página, que lee ese archivo.", "numeros2"),
  H2("4.1. Organización del repositorio"),
  ...codigo([
    "Tfm/",
    "├── config/config.json          palabras clave, fuentes, umbrales, ventana",
    "├── config/mitre_mapeo.json     reglas palabra → técnica MITRE ATT&CK",
    "├── datos/                      incidentes y hechos clave (CSV), histórico GDELT,",
    "│                               noticias acumuladas, diagnóstico de fuentes",
    "├── monitor/                    programa en Python (fuentes, clasificador,",
    "│                               semáforo, histórico, MITRE, ia/ para la Fase 2)",
    "├── web/                        página (index.html, app.js, estilo.css, datos.json)",
    "├── tests/                      pruebas automáticas de las reglas",
    "├── docs/decisiones_tecnicas.md decisiones de diseño justificadas",
    "├── memoria/                    esta memoria (generador, bitácora, capturas)",
    "└── .github/workflows/          actualizar.yml · historico.yml · verificar.yml",
  ]),
);

// 5. Fuentes
add(
  H1("5. Fuentes de datos"),
  H2("5.1. Validación de las fuentes"),
  P("Las fuentes se probaron el 12/10/2026 **desde los servidores de GitHub Actions**, que es donde la plataforma funciona. Resultado:"),
  tabla(["Fuente", "Tipo", "Resultado de la prueba"], [
    ["The Record", "Ciberseguridad (EN)", "Funciona (5 ítems por lectura)"],
    ["BleepingComputer", "Ciberseguridad (EN)", "Funciona (15 ítems)"],
    ["The Hacker News", "Ciberseguridad (EN)", "Funciona (50 ítems)"],
    ["WeLiveSecurity (ESET)", "Ciberseguridad (ES)", "Funciona con /es/rss/feed/ (100 ítems). La URL /es/feed/ da error 404."],
    ["Infobae", "Medio argentino", "Funciona con /arc/outboundfeeds/rss/ (100 ítems). La URL /feeds/rss/ da error 404."],
    ["La Nación", "Medio argentino", "Funciona (88–89 ítems)"],
    ["GDELT DOC 2.0 API", "Noticias mundiales", "Funciona y tiene historial 2023–2024, pero con límite de uso estricto (HTTP 429 frecuentes)."],
    ["MITRE ATT&CK (STIX)", "Catálogo de técnicas", "Funciona (descarga oficial desde github.com/mitre/cti)."],
  ], [2300, 2000, 5338]),
  espacio(),
  P("Ninguna fuente tuvo que descartarse. Las direcciones que fallaron se reemplazaron por las alternativas que sí funcionan."),
  H2("5.2. GDELT: el principal desafío técnico"),
  P("GDELT admite aproximadamente una consulta cada 5 segundos por dirección IP. Como los servidores de GitHub son compartidos con muchos otros usuarios, en la práctica se midió **una consulta exitosa cada 20 segundos a 3,5 minutos**, con muchos rechazos (HTTP 429). Además, las consultas geopolíticas alcanzaban el máximo de 250 artículos incluso en tramos de 3 días."),
  P("Para resolverlo se rediseñó la descarga del histórico:"),
  V("Una sola consulta geopolítica y una sola consulta ciber (español e inglés combinados)."),
  V("Artículos ordenados por **relevancia**, para que, si se llega al máximo de 250, se conserven los más pertinentes."),
  V("Tramos de **2 días** para la consulta geopolítica y de **30 días** para la ciber: 196 consultas en total."),
  V("**Descarga por partes y reanudable:** cada ejecución trabaja como máximo 40 minutos, guarda el progreso y se detiene antes si GDELT rechaza 3 consultas seguidas. Un workflow dedicado la repite cada hora hasta completarla."),
  P("Un diagnóstico posterior confirmó que, para el monitoreo **en vivo**, los feeds RSS son la fuente principal y GDELT es complementario. GDELT aporta su mayor valor en el **análisis histórico**."),
  H2("5.3. Archivos de carga manual"),
  P("Dado que los grupos hacktivistas anuncian sus ataques mayormente en Telegram o X (fuera del alcance de la Fase 1), se crearon dos archivos CSV editables desde GitHub:"),
  V("`datos/hechos_clave.csv`: 8 hechos geopolíticos de referencia (7 de octubre de 2023, balotaje, asunción presidencial, visita a Israel y anuncio sobre la embajada, fallo AMIA, ataque iraní a Israel, declaración de Hamás como organización terrorista, 30.º aniversario de la AMIA). Están marcados como **no verificados** hasta que el autor confirme fechas y fuentes."),
  V("`datos/incidentes_historicos.csv`: ataques conocidos. Se entregó solo con una fila de ejemplo (que se ignora); **no se inventaron incidentes**. Su carga es la próxima tarea del autor."),
  tabla(["Columna", "Contenido"], [
    ["id, fecha", "Identificador único y fecha del ataque (AAAA-MM-DD)"],
    ["grupo, objetivo, dominio_objetivo, sector", "Quién atacó, a quién, qué sitio y de qué sector"],
    ["tipo_ataque, tecnicas_mitre", "defacement / ddos / filtracion / otro y técnicas ATT&CK"],
    ["descripcion, motivacion_declarada", "Resumen y motivación reivindicada por el grupo"],
    ["fuente_nombre, fuente_url", "Origen del dato"],
    ["confianza, verificado", "Alta/media/baja y si fue verificado (práctica estándar de CTI)"],
  ], [3600, 6038]),
);

// 6. Clasificación
const geo = Object.entries(config.palabras_clave.geopoliticas);
const porPeso = (w) => geo.filter(([, p]) => p === w).map(([t]) => t).join(", ");
add(
  H1("6. Clasificación por reglas (Fase 1)"),
  H2("6.1. Noticias geopolíticas"),
  P(`Una noticia es **geopolítica relevante** si menciona a Argentina y la suma de los pesos de sus términos geopolíticos alcanza el umbral (**${config.semaforo.umbral_puntaje_detonante} puntos**). Los términos se buscan sin tildes, sin distinguir mayúsculas y como palabras completas.`),
  tabla(["Peso", "Términos (español e inglés)"], [
    ["2 puntos", porPeso(2)],
    ["1 punto", porPeso(1)],
  ], [1400, 8238]),
  espacio(),
  P("Ejemplos: «Argentina e Israel firman un acuerdo comercial» suma 1 punto y **no** se considera relevante. «Milei anunció que trasladará la embajada argentina a Jerusalén» suma 2 (embajada + Jerusalén) y **sí** se considera relevante."),
  H2("6.2. Noticias de ataque"),
  P("Una noticia es de **ataque** si contiene al menos un término cibernético **y** menciona a Argentina (o un dominio `.gob.ar`). Entre los términos están: hackeo, hackers, ciberataque, filtración de datos, defacement, sitio caído, DDoS, hacktivistas, ransomware, gob.ar y los nombres de los grupos (Cyber Dragonz, LulzSec Muslims, REM, Ripper Sec, Anonymous Sudan, Mysterious Team, Team Insane PK)."),
  V("La sigla **REM** solo cuenta si aparece en MAYÚSCULAS, para evitar falsos positivos (por ejemplo, la «fase REM» del sueño)."),
  V("Se descartaron términos demasiado genéricos como «filtración» a secas, que en la prensa argentina se usa mucho para filtraciones políticas."),
  H2("6.3. Mapeo a MITRE ATT&CK"),
  P("A cada noticia de ataque se le asignan técnicas de la matriz Enterprise ATT&CK según las expresiones que contiene. Los nombres oficiales se descargan de MITRE en cada ejecución."),
  tabla(["Categoría", "Técnicas asignadas"], mapeo.reglas.map((r) => [r.categoria,
    r.tecnicas.map((t) => `${t}${mitre[t] ? " · " + mitre[t].nombre : ""}`).join("\n")]), [3600, 6038]),
);

// 7. Semáforo
const S = config.semaforo;
add(
  H1("7. El semáforo de alertas"),
  H2("7.1. Reglas"),
  N(`**Día detonante:** hay noticias geopolíticas relevantes de al menos **${S.min_fuentes_distintas_por_dia} fuentes distintas** (corroboración independiente), o hay un hecho clave cargado a mano.`, "numeros3"),
  N(`**Ventana de vigilancia:** cada día detonante abre una ventana de **${S.ventana_vigilancia_dias} días**. Si aparece otro detonante con la ventana abierta, la ventana se extiende.`, "numeros3"),
  N("**Amarillo:** el día está dentro de una ventana y todavía no hubo ataques.", "numeros3"),
  N("**Rojo:** dentro de la ventana apareció al menos un ataque contra objetivos argentinos. El nivel se mantiene en rojo hasta que la ventana se cierra.", "numeros3"),
  N("**Verde:** el día no está dentro de ninguna ventana.", "numeros3"),
  N("**Alerta informativa:** un ataque fuera de toda ventana no cambia el semáforo, pero se informa, porque sirve para evaluar el modelo (posibles detonantes no detectados).", "numeros3"),
  H2("7.2. Ejemplo"),
  tabla(["Fecha", "Qué ocurre", "Nivel"], [
    ["6 feb 2024", "Visita a Israel y anuncio sobre la embajada (hecho detonante)", "Amarillo — ventana hasta el 13 feb"],
    ["7–8 feb", "Sin ataques registrados", "Amarillo"],
    ["9 feb", "Se registra un ataque contra un sitio .gob.ar (ejemplo ilustrativo)", "Rojo"],
    ["10–13 feb", "Ventana todavía abierta", "Rojo"],
    ["14 feb", "La ventana se cierra", "Verde"],
  ], [1600, 5238, 2800]),
  espacio(),
  P("Este comportamiento está cubierto por las pruebas automáticas del proyecto (ver capítulo 10)."),
  H2("7.3. Parámetros configurables"),
  tabla(["Parámetro (config.json)", "Valor actual", "Qué controla"], [
    ["ventana_vigilancia_dias", String(S.ventana_vigilancia_dias), "Duración de la ventana de vigilancia"],
    ["umbral_puntaje_detonante", String(S.umbral_puntaje_detonante), "Puntaje mínimo para que una noticia sea geopolítica relevante"],
    ["min_fuentes_distintas_por_dia", String(S.min_fuentes_distintas_por_dia), "Corroboración: fuentes distintas necesarias para un día detonante"],
    ["dias_modo_vivo", String(S.dias_modo_vivo), "Días que muestra el modo en vivo"],
  ], [3200, 1400, 5038]),
);

// 8. Web
add(
  H1("8. La página web"),
  P("La página tiene una sola pantalla, como se pidió en los requisitos. Funciona en computadora y en celular, en modo claro y oscuro, y no depende de librerías externas."),
  ...figura("web_vivo.png", "Modo en vivo (últimos 30 días): semáforo, línea de tiempo y alertas. Datos reales de la primera revisión, 12/10/2026."),
  H2("8.1. Componentes"),
  V("**Semáforo:** nivel actual (o el nivel en la fecha final del rango, en modo histórico) y resumen del período: cantidad de hechos, ataques, días en amarillo y en rojo, y nivel máximo."),
  V("**Línea de tiempo:** carril superior con hechos geopolíticos (barras por día) y carril inferior con ataques. Los rombos marcan datos cargados a mano; las bandas sombreadas son las ventanas de vigilancia; la franja central muestra el nivel de cada día. Al pasar el mouse por un día se ve un resumen, y con un clic se ven todas sus noticias."),
  V("**Alertas:** lista con nivel, fechas, noticias relacionadas, grupos detectados y técnicas MITRE, con enlaces a la fuente y a ATT&CK. Un interruptor muestra u oculta las alertas informativas."),
  V("**Selector de fechas:** permite pasar del modo en vivo al histórico; el botón «Caso de estudio» carga agosto 2023 – julio 2024."),
  V("**Tabla de eventos** (accesible) y **estado de las fuentes y metodología**."),
  ...figura("web_historico.png", "Modo histórico del caso de estudio con los 8 hechos clave. Todavía sin ataques cargados: 6 alertas amarillas y ninguna roja.", 520),
  ...figura("web_alertas_info.png", "Alerta informativa real detectada automáticamente: el ciberataque a la Asociación del Fútbol Argentino (fuente: WeLiveSecurity)."),
  ...figura("web_fuentes.png", "Diagnóstico de fuentes de la última revisión y explicación de la metodología, visibles en la propia página."),
  ...figura("web_movil.png", "Vista en celular.", 260),
);

// 9. Automatización y puesta en marcha
add(
  H1("9. Automatización y puesta en marcha"),
  H2("9.1. Workflows de GitHub Actions"),
  tabla(["Workflow", "Cuándo se ejecuta", "Qué hace"], [
    ["Actualizar monitor (actualizar.yml)", "Cada 6 horas (00:17, 06:17, 12:17, 18:17 UTC), manualmente o al cambiar la configuración o los CSV", "Ejecuta las pruebas, recolecta, clasifica, calcula el semáforo, guarda los datos y publica la web."],
    ["Completar histórico (historico.yml)", "Cada hora, hasta completar el histórico", "Descarga por partes el histórico de GDELT; cuando está completo, termina en segundos."],
    ["Verificar cambios (verificar.yml)", "En cada cambio de la rama de desarrollo y en los Pull Requests", "Prueba los cambios con datos reales sin modificar la plataforma publicada."],
  ], [2700, 3000, 3938]),
  H2("9.2. Configuración realizada por el autor"),
  P("La puesta en marcha requirió cinco acciones del autor en la web de GitHub, guiadas paso a paso:"),
  N("Autorizar a la aplicación de Claude a escribir en el repositorio (resolvió el error 403).", "numeros4"),
  N("Activar GitHub Pages con el origen «GitHub Actions».", "numeros4"),
  N("Dar permisos de lectura y escritura a los workflows.", "numeros4"),
  N("Marcar la rama `main` como rama principal.", "numeros4"),
  N("Autorizar a `main` a publicar en el entorno `github-pages`.", "numeros4"),
  ...figura("github_pages_origen.png", "Configuración de GitHub Pages antes del cambio (origen «Deploy from a branch»)."),
  ...figura("github_pages_menu.png", "Selección del origen «GitHub Actions» para GitHub Pages."),
  H2("9.3. Flujo de cambios con Pull Requests"),
  P("Los cambios se desarrollan en una rama de trabajo y llegan a `main` mediante un **Pull Request** que el autor revisa y aprueba. El primero (#1) incorporó la decisión técnica sobre GDELT."),
  ...figura("pull_request.png", "Pull Request #1 en GitHub (interfaz traducida automáticamente al español por el navegador)."),
  ...figura("pull_request_fusion.png", "Fusión del Pull Request: se mantiene la opción «Crear una confirmación de fusión»."),
);

// 10. Pruebas
add(
  H1("10. Pruebas y verificación"),
  H2("10.1. Pruebas automáticas"),
  P("El archivo `tests/test_reglas.py` contiene 13 pruebas que se ejecutan antes de cada revisión. Si alguna falla, la revisión se detiene y la web publicada no cambia."),
  tabla(["Prueba", "Qué comprueba"], [
    ["Hecho geopolítico", "«embajada argentina a Jerusalén» se clasifica como geopolítico"],
    ["Geo débil", "«Argentina votó en la ONU…» (1 punto) se descarta"],
    ["Sin Argentina", "Noticias de Hamás o Irán sin Argentina no suman puntos"],
    ["Defacement", "Se detecta como ataque y se asigna T1491.002"],
    ["DDoS gob.ar", "Se detecta el grupo Cyber Dragonz y se asigna T1498"],
    ["REM", "Solo cuenta en mayúsculas"],
    ["Ciber sin Argentina", "Un ransomware en Alemania no es ataque contra Argentina"],
    ["Verde", "Un ataque sin detonante genera solo una alerta informativa"],
    ["Corroboración", "Una sola fuente no alcanza para un día detonante"],
    ["Amarillo → rojo → verde", "Secuencia completa de niveles"],
    ["Hecho clave", "Un hecho clave abre la ventana por sí solo"],
    ["Fusión de ventanas", "Detonantes cercanos forman un único período"],
    ["Ventana configurable", "Con 3 días, la ventana se cierra antes"],
  ], [2600, 7038]),
  H2("10.2. Verificaciones con datos reales"),
  tabla(["Ejecución", "Resultado", "Observación"], [
    ["Prueba de fuentes", "Éxito", "6 RSS operativos; GDELT con historial y límite de uso"],
    ["Verificación 1 y 2", "Cortadas a los 30 min", "Midieron la lentitud de GDELT y motivaron el rediseño del histórico"],
    ["Verificación 3", "Éxito", "Detención controlada ante rechazos de GDELT; detección del ataque a la AFA"],
    ["Diagnóstico GDELT", "Éxito", "3 de 5 consultas rechazadas; GDELT pasa a ser complementario en vivo"],
    ["Primera revisión oficial", "Revisión OK; publicación rechazada", "Regla del entorno github-pages (resuelta)"],
    ["Segunda revisión oficial", "Éxito", "Plataforma publicada"],
  ], [2600, 2400, 4638]),
);

// 11. Problemas
add(
  H1("11. Problemas encontrados y soluciones"),
  tabla(["Problema", "Causa", "Solución"], [
    ["El entorno de desarrollo no accede a los feeds", "Red restringida del entorno en la nube", "Probar y ejecutar todo desde GitHub Actions"],
    ["Error 403 al subir el código", "La app de Claude no tenía permiso sobre el repositorio", "El autor instaló o reconectó la Claude GitHub App"],
    ["URLs de feeds con error 404", "Rutas antiguas de WeLiveSecurity e Infobae", "Se usaron las rutas vigentes"],
    ["GDELT rechaza consultas (HTTP 429)", "Límite de uso por IP en servidores compartidos", "Reintentos con espera, consultas unificadas y descarga por partes"],
    ["Verificaciones cortadas a los 30 minutos", "Descarga del histórico demasiado lenta", "Presupuesto de tiempo, progreso reanudable y workflow horario"],
    ["Mensajes del programa invisibles en GitHub", "Salida de Python con búfer", "Variable PYTHONUNBUFFERED=1"],
    ["La rama principal era la de desarrollo", "El repositorio estaba vacío al empezar", "Se creó main y el autor la marcó como principal"],
    ["Publicación de la web rechazada", "El entorno github-pages solo autorizaba la rama original", "El autor agregó main a las reglas del entorno"],
    ["Confusión entre configuración de cuenta y de repositorio", "Hay dos menús «Settings» distintos en GitHub", "Enlaces directos a cada pantalla"],
  ], [3000, 3200, 3438]),
);

// 12. Decisiones
add(
  H1("12. Decisiones técnicas"),
  P("Las decisiones completas, con alternativas descartadas y consecuencias, están en `docs/decisiones_tecnicas.md`. Resumen:"),
  tabla(["Id", "Decisión", "Motivo principal"], [
    ["D1", "GitHub Actions + Pages, sin servidores", "Costo cero, sin mantenimiento, auditable"],
    ["D2", "Datos versionados en el propio repositorio", "Trazabilidad y reproducibilidad"],
    ["D3", "Python con solo dos dependencias", "Simplicidad y menor superficie de ataque"],
    ["D4", "Web sin librerías ni CDN", "Robustez y privacidad del visitante"],
    ["D5", "Lógica de alertas solo en Python", "Una única fuente de verdad, probada"],
    ["D6", "Configuración en JSON", "El analista ajusta el modelo sin programar"],
    ["D7", "Seis feeds validados con diagnóstico", "Detectar caídas de fuentes"],
    ["D8", "GDELT con reintentos y orden por relevancia", "Límite de uso estricto"],
    ["D8b", "RSS como fuente principal en vivo", "Resultado del diagnóstico de GDELT"],
    ["D9", "Histórico por partes y reanudable", "Cumplir límites sin perder progreso"],
    ["D10", "Archivo propio de noticias en vivo", "Los RSS no guardan historia"],
    ["D11", "Carga manual de incidentes y hechos clave", "Telegram/X fuera de alcance; sin datos inventados"],
    ["D12–D16", "Normalización, puntaje, corroboración, reglas de ataque, REM", "Reducir falsos positivos"],
    ["D17", "Mapeo MITRE por reglas", "Comparabilidad con informes de CTI"],
    ["D18–D20", "Ventanas fusionables, rojo persistente, alertas informativas", "Coherencia operativa y evaluación del modelo"],
    ["D21–D24", "Horarios, workflows separados, pruebas, secretos", "Calidad y seguridad"],
    ["D25", "Diseño de la Fase 2 (Haiku clasifica, Sonnet informa)", "Comparar IA con reglas y controlar el costo"],
  ], [1100, 4600, 3938]),
);

// 13. Estado actual
add(
  H1("13. Estado actual y próximos pasos"),
  H2("13.1. Estado"),
  V("**Fase 1 completa y en producción** en https://gastonaizama.github.io/Tfm/."),
  V("Revisión automática cada 6 horas; histórico de GDELT descargándose por partes."),
  V("Fase 2 preparada (carpeta `monitor/ia/`, interruptor en la configuración y lugar para el secreto), sin implementar."),
  H2("13.2. Tareas pendientes del autor"),
  N("**Cargar los ataques conocidos** del período en `datos/incidentes_historicos.csv`. Sin ellos, el modo histórico no puede mostrar alertas rojas ni evaluar la hipótesis.", "numeros5"),
  N("**Verificar los 8 hechos clave:** confirmar fechas, completar `fuente_url` y marcar `verificado = si`.", "numeros5"),
  N("Completar el nombre del autor en la portada de esta memoria.", "numeros5"),
  H2("13.3. Próximos pasos propuestos"),
  V("**Evaluación del modelo:** proporción de ataques ocurridos dentro de ventanas de vigilancia, días de anticipación entre detonante y ataque, y alertas sin ataques posteriores."),
  V("**Análisis de sensibilidad:** comparar ventanas de 3, 7 y 14 días y distintos umbrales."),
  V("**Fase 2:** clasificación con Claude Haiku 5.5, informe de inteligencia con Claude Sonnet 5.5 y comparación con las reglas de la Fase 1."),
);

// Anexo A: bitácora
add(
  H1("Anexo A. Bitácora del proyecto"),
  P("Registro cronológico de todo lo realizado. Se actualiza con cada avance."),
  tabla(["Fecha", "Tipo", "Hito", "Detalle"], bitacora.eventos.map((e) => [e.fecha, e.tipo, e.titulo, e.detalle]), [1250, 1650, 2300, 4438]),
);

// Anexo B: glosario
add(
  H1("Anexo B. Glosario"),
  tabla(["Término", "Significado"], [
    ["API", "Interfaz que permite a un programa pedir datos a otro servicio (por ejemplo, GDELT)."],
    ["Commit", "Registro de un conjunto de cambios en el repositorio, con fecha y descripción."],
    ["CSV", "Archivo de texto con datos en columnas separadas por comas; se abre con Excel."],
    ["CTI", "Cyber Threat Intelligence: inteligencia sobre amenazas cibernéticas."],
    ["Cron", "Forma de indicar cada cuánto se ejecuta una tarea programada."],
    ["DDoS", "Ataque de denegación de servicio distribuido: satura un sitio hasta dejarlo inaccesible."],
    ["Defacement", "Modificación no autorizada de la apariencia de un sitio web."],
    ["GDELT", "Proyecto que indexa noticias de todo el mundo y ofrece una API pública."],
    ["GitHub Actions", "Servicio de GitHub que ejecuta programas automáticamente en sus servidores."],
    ["GitHub Pages", "Servicio de GitHub que publica páginas web gratuitas."],
    ["Hacktivismo", "Ciberataques con motivación política o ideológica."],
    ["HTTP 403 / 404 / 429", "Respuestas de un servidor: acceso denegado / no encontrado / demasiadas consultas."],
    ["JSON", "Formato de texto para guardar datos estructurados."],
    ["MITRE ATT&CK", "Matriz pública que cataloga tácticas y técnicas de ataque."],
    ["OSINT", "Inteligencia de fuentes abiertas (información pública)."],
    ["Pull Request", "Propuesta de cambios que se revisa y aprueba antes de incorporarla a la rama principal."],
    ["Rama (branch)", "Línea de trabajo paralela dentro de un repositorio; main es la principal."],
    ["Repositorio", "Carpeta en GitHub con el código, los datos y su historial."],
    ["RSS", "Formato con el que los medios publican sus últimas noticias para ser leídas automáticamente."],
    ["Secreto (GitHub)", "Valor confidencial (por ejemplo, una API key) que GitHub guarda cifrado y no muestra."],
    ["TTP", "Tácticas, técnicas y procedimientos de un actor de amenazas."],
    ["Workflow", "Tarea automática definida en GitHub Actions."],
  ], [2400, 7238]),
);

// ---------------------------------------------------------------- documento
const doc = new Document({
  creator: "TFM Máster CTI - KSchool",
  title: "Memoria de trabajo del TFM - Monitor Ciber-Geopolítico Argentina",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FUENTE, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 34, bold: true, font: FUENTE, color: AZUL }, paragraph: { spacing: { before: 240, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 27, bold: true, font: FUENTE, color: "2E2E2B" }, paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: FUENTE }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "vinetas", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      ...["numeros", "numeros2", "numeros3", "numeros4", "numeros5"].map((ref) => ({
        reference: ref, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
      })),
    ],
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: "Memoria de trabajo · Monitor Ciber-Geopolítico Argentina", size: 16, color: "8F8E86" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Página ", size: 16, color: "8F8E86" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "8F8E86" }),
        new TextRun({ text: ` · Versión ${version.version} (${version.fecha})`, size: 16, color: "8F8E86" })] })] }) },
    children: contenido,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const salida = path.join(DIR, "Memoria_TFM.docx");
  fs.writeFileSync(salida, buf);
  console.log(`Memoria generada: ${salida} (versión ${version.version}, ${nFigura} figuras)`);
});
