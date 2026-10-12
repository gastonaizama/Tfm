/* Monitor Ciber-Geopolítico · Argentina — interfaz web (sin dependencias externas). */
"use strict";

const NIVEL_TXT = { verde: "Verde", amarillo: "Amarillo", rojo: "Rojo", info: "Info" };
const NIVEL_DESC = {
  verde: "Sin hechos geopolíticos detonantes recientes.",
  amarillo: "Se detectó un hecho geopolítico detonante: ventana de vigilancia abierta.",
  rojo: "Dentro de la ventana de vigilancia se detectaron ataques contra objetivos argentinos.",
};
const ORIGEN_TXT = {
  rss: "RSS", gdelt: "GDELT", gdelt_historico: "GDELT (histórico)",
  hecho_clave: "Hecho clave (manual)", incidente_csv: "Incidente (manual)",
};
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

const $ = (id) => document.getElementById(id);
const estado = { datos: null, modo: "vivo", desde: null, hasta: null, diaSel: null };

// ---------- utilidades de fechas (todas en UTC, formato AAAA-MM-DD) ----------
const aFecha = (s) => new Date(s + "T00:00:00Z");
const aISO = (d) => d.toISOString().slice(0, 10);
const sumarDias = (s, n) => { const d = aFecha(s); d.setUTCDate(d.getUTCDate() + n); return aISO(d); };
const difDias = (a, b) => Math.round((aFecha(b) - aFecha(a)) / 86400000);
const fechaLarga = (s) => { const d = aFecha(s); return `${d.getUTCDate()} ${MESES[d.getUTCMonth()]} ${d.getUTCFullYear()}`; };
const hoyISO = () => aISO(new Date());
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const enlace = (url, txt) => url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(txt)}</a>` : esc(txt);
const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
const esCurado = (e) => e.origen === "hecho_clave" || e.origen === "incidente_csv";

// ---------- carga ----------
async function iniciar() {
  try {
    const r = await fetch("datos.json", { cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    estado.datos = await r.json();
  } catch (e) {
    $("actualizado").textContent = "No se pudieron cargar los datos (" + e.message + ").";
    return;
  }
  const d = estado.datos;
  d.porId = Object.fromEntries(d.eventos.map((e) => [e.id, e]));
  d.serieMap = Object.fromEntries(d.serie_diaria.map((s) => [s.dia, s]));
  $("actualizado").textContent = "Última revisión: " + new Date(d.generado).toLocaleString("es-AR", { dateStyle: "medium", timeStyle: "short" });

  $("btn-vivo").onclick = () => modoVivo();
  $("btn-hist").onclick = () => modoHistorico();
  $("btn-caso").onclick = () => modoHistorico();
  $("desde").onchange = $("hasta").onchange = () => {
    estado.desde = $("desde").value; estado.hasta = $("hasta").value;
    if (estado.desde > estado.hasta) [estado.desde, estado.hasta] = [estado.hasta, estado.desde];
    marcarModo(estado.hasta >= sumarDias(hoyISO(), -1) ? "vivo" : "historico");
    render();
  };
  $("ver-info").onchange = renderAlertas;
  let t; window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(dibujarLinea, 150); });
  renderFuentes(); renderMetodologia(); renderInforme();
  modoVivo();
}

function marcarModo(m) {
  estado.modo = m;
  $("btn-vivo").classList.toggle("activo", m === "vivo");
  $("btn-hist").classList.toggle("activo", m === "historico");
  $("btn-vivo").setAttribute("aria-pressed", m === "vivo");
  $("btn-hist").setAttribute("aria-pressed", m === "historico");
}
function modoVivo() {
  marcarModo("vivo");
  estado.hasta = hoyISO();
  estado.desde = sumarDias(estado.hasta, -(estado.datos.parametros.dias_modo_vivo || 30));
  render();
}
function modoHistorico() {
  marcarModo("historico");
  estado.desde = estado.datos.parametros.historico.inicio;
  estado.hasta = estado.datos.parametros.historico.fin;
  render();
}

function render() {
  $("desde").value = estado.desde; $("hasta").value = estado.hasta;
  estado.diaSel = null; $("detalle-dia").hidden = true;
  renderSemaforo(); dibujarLinea(); renderAlertas(); renderTabla();
}

const eventosEnRango = () => estado.datos.eventos.filter((e) => e.dia >= estado.desde && e.dia <= estado.hasta);

// ---------- semáforo ----------
function renderSemaforo() {
  const d = estado.datos;
  const enVivo = estado.modo === "vivo";
  const dia = enVivo ? d.actual.fecha : estado.hasta;
  const s = d.serieMap[dia] || { nivel: "verde", periodo: null };
  const periodo = d.periodos.find((p) => p.id === s.periodo);
  $("semaforo").dataset.nivel = s.nivel;
  $("semaforo").setAttribute("aria-label", "Semáforo: nivel " + NIVEL_TXT[s.nivel]);
  $("sem-contexto").textContent = enVivo ? "Nivel actual" : `Nivel al ${fechaLarga(dia)}`;
  $("sem-nivel").textContent = NIVEL_TXT[s.nivel];
  let det = NIVEL_DESC[s.nivel];
  if (periodo) det += ` Ventana abierta el ${fechaLarga(periodo.inicio)}, vigente hasta el ${fechaLarga(periodo.fin)}.`;
  $("sem-detalle").textContent = det;

  const evs = eventosEnRango();
  const dias = d.serie_diaria.filter((x) => x.dia >= estado.desde && x.dia <= estado.hasta);
  const cuenta = (n) => dias.filter((x) => x.nivel === n).length;
  const max = cuenta("rojo") ? "rojo" : cuenta("amarillo") ? "amarillo" : "verde";
  $("resumen").innerHTML = [
    ["Hechos geopolíticos", evs.filter((e) => e.carril === "geo").length],
    ["Ataques", evs.filter((e) => e.carril === "ataque").length],
    ["Días en amarillo", cuenta("amarillo")],
    ["Días en rojo", cuenta("rojo")],
    ["Nivel máximo del periodo", NIVEL_TXT[max]],
  ].map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
}

// ---------- línea de tiempo (SVG) ----------
function dibujarLinea() {
  const cont = $("linea");
  const W = Math.max(320, cont.clientWidth);
  const ML = W < 560 ? 64 : 96, MR = 12, MT = 10;
  const H_CARRIL = W < 560 ? 70 : 92, H_FRANJA = 12, H_EJE = 26;
  const H = MT + H_CARRIL + 6 + H_FRANJA + 6 + H_CARRIL + H_EJE;
  const yGeoBase = MT + H_CARRIL, yFr = yGeoBase + 6, yAtqBase = yFr + H_FRANJA + 6;
  const n = difDias(estado.desde, estado.hasta) + 1;
  const pw = W - ML - MR, bw = pw / n;
  const x = (dia) => ML + difDias(estado.desde, dia) * bw;

  // Agregación por día y carril
  const porDia = {};
  for (const e of eventosEnRango()) {
    const k = (porDia[e.dia] ||= { geo: [], ataque: [] });
    k[e.carril].push(e);
  }
  const conteo = (lista) => lista.filter((e) => !esCurado(e)).length;
  const maxGeo = Math.max(1, ...Object.values(porDia).map((v) => conteo(v.geo)));
  const maxAtq = Math.max(1, ...Object.values(porDia).map((v) => conteo(v.ataque)));
  const anchoBarra = Math.max(1, bw - (bw > 4 ? 2 : 0));
  const rx = Math.min(4, anchoBarra / 2);

  const p = [];
  p.push(`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Línea de tiempo de ${fechaLarga(estado.desde)} a ${fechaLarga(estado.hasta)}">`);

  // Ventanas de vigilancia (bandas de fondo)
  for (const per of estado.datos.periodos) {
    if (per.fin < estado.desde || per.inicio > estado.hasta) continue;
    const a = per.inicio < estado.desde ? estado.desde : per.inicio;
    const b = per.fin > estado.hasta ? estado.hasta : per.fin;
    p.push(`<rect x="${x(a)}" y="${MT}" width="${x(sumarDias(b, 1)) - x(a)}" height="${yAtqBase + H_CARRIL - MT}" fill="var(--banda-a)"/>`);
    if (per.primer_ataque && per.primer_ataque <= estado.hasta) {
      const ra = per.primer_ataque < a ? a : per.primer_ataque;
      p.push(`<rect x="${x(ra)}" y="${MT}" width="${x(sumarDias(b, 1)) - x(ra)}" height="${yAtqBase + H_CARRIL - MT}" fill="var(--banda-r)"/>`);
    }
  }

  // Rejilla y rótulos de carril
  p.push(`<line class="rejilla" x1="${ML}" x2="${W - MR}" y1="${MT}" y2="${MT}"/>`);
  p.push(`<line class="eje" x1="${ML}" x2="${W - MR}" y1="${yGeoBase}" y2="${yGeoBase}"/>`);
  p.push(`<line class="eje" x1="${ML}" x2="${W - MR}" y1="${yAtqBase}" y2="${yAtqBase}"/>`);
  p.push(`<line class="rejilla" x1="${ML}" x2="${W - MR}" y1="${yAtqBase + H_CARRIL}" y2="${yAtqBase + H_CARRIL}"/>`);
  p.push(`<text class="rotulo-carril" x="4" y="${MT + 14}">Geopolítica</text><text x="4" y="${MT + 29}">máx ${maxGeo}/día</text>`);
  p.push(`<text class="rotulo-carril" x="4" y="${yAtqBase + 14}">Ataques</text><text x="4" y="${yAtqBase + 29}">máx ${maxAtq}/día</text>`);
  p.push(`<text x="4" y="${yFr + 10}">Nivel</text>`);

  // Ticks del eje temporal
  const ticks = [];
  if (n > 75) {
    const d0 = aFecha(estado.desde); d0.setUTCDate(1);
    for (let d = d0; aISO(d) <= estado.hasta; d.setUTCMonth(d.getUTCMonth() + 1)) {
      const s = aISO(d); if (s >= estado.desde) ticks.push([s, `${MESES[d.getUTCMonth()]} ${String(d.getUTCFullYear()).slice(2)}`]);
    }
  } else {
    const paso = n > 35 ? 14 : 7;
    for (let s = estado.desde; s <= estado.hasta; s = sumarDias(s, paso)) { const d = aFecha(s); ticks.push([s, `${d.getUTCDate()} ${MESES[d.getUTCMonth()]}`]); }
  }
  const minSep = 44; let ultimo = -1e9;
  for (const [s, txt] of ticks) {
    const tx = x(s); if (tx - ultimo < minSep) continue; ultimo = tx;
    p.push(`<line class="rejilla" x1="${tx}" x2="${tx}" y1="${MT}" y2="${yAtqBase + H_CARRIL}"/>`);
    p.push(`<text x="${tx + 3}" y="${H - 8}">${txt}</text>`);
  }

  // Franja de nivel diario + barras + marcas curadas + zonas de interacción
  for (let i = 0; i < n; i++) {
    const dia = sumarDias(estado.desde, i), xd = ML + i * bw;
    const nivel = (estado.datos.serieMap[dia] || {}).nivel || "verde";
    const color = nivel === "rojo" ? "var(--critico)" : nivel === "amarillo" ? "var(--aviso)" : "var(--ok)";
    p.push(`<rect x="${xd}" y="${yFr}" width="${bw + 0.5}" height="${H_FRANJA}" fill="${color}" opacity="${nivel === "verde" ? 0.35 : 0.9}"/>`);
    const v = porDia[dia];
    if (v) {
      const g = conteo(v.geo), a = conteo(v.ataque);
      const bx = xd + (bw - anchoBarra) / 2;
      if (g) { const h = Math.max(2, (g / maxGeo) * (H_CARRIL - 22)); p.push(`<path d="${barraArriba(bx, yGeoBase, anchoBarra, h, rx)}" fill="var(--geo)"/>`); }
      if (a) { const h = Math.max(2, (a / maxAtq) * (H_CARRIL - 22)); p.push(`<path d="${barraAbajo(bx, yAtqBase, anchoBarra, h, rx)}" fill="var(--ataque)"/>`); }
      const cx = xd + bw / 2;
      if (v.geo.some(esCurado)) p.push(rombo(cx, MT + 9));
      if (v.ataque.some(esCurado)) p.push(rombo(cx, yAtqBase + H_CARRIL - 9));
    }
    p.push(`<rect class="hit" data-dia="${dia}" x="${xd}" y="${MT}" width="${Math.max(bw, 1)}" height="${yAtqBase + H_CARRIL - MT}"/>`);
  }
  p.push("</svg>");
  cont.innerHTML = p.join("");

  cont.querySelectorAll(".hit").forEach((r) => {
    r.addEventListener("mousemove", (ev) => mostrarTooltip(ev, r.dataset.dia, porDia[r.dataset.dia]));
    r.addEventListener("mouseleave", () => ($("tooltip").hidden = true));
    r.addEventListener("click", () => mostrarDia(r.dataset.dia, porDia[r.dataset.dia]));
  });
}
function barraArriba(x, base, w, h, r) {
  r = Math.min(r, h);
  return `M${x},${base}V${base - h + r}Q${x},${base - h} ${x + r},${base - h}H${x + w - r}Q${x + w},${base - h} ${x + w},${base - h + r}V${base}Z`;
}
function barraAbajo(x, base, w, h, r) {
  r = Math.min(r, h);
  return `M${x},${base}V${base + h - r}Q${x},${base + h} ${x + r},${base + h}H${x + w - r}Q${x + w},${base + h} ${x + w},${base + h - r}V${base}Z`;
}
const rombo = (cx, cy) => `<path d="M${cx},${cy - 6}L${cx + 6},${cy}L${cx},${cy + 6}L${cx - 6},${cy}Z" fill="var(--superficie)" stroke="var(--curado)" stroke-width="2"/>`;

function mostrarTooltip(ev, dia, v) {
  const tt = $("tooltip"), caja = $("linea").parentElement.getBoundingClientRect();
  const nivel = (estado.datos.serieMap[dia] || {}).nivel || "verde";
  const geo = v ? v.geo : [], atq = v ? v.ataque : [];
  const ejemplos = [...atq, ...geo].slice(0, 3).map((e) => `<div>· ${esc(e.titulo.slice(0, 90))}</div>`).join("");
  tt.innerHTML = `<b>${fechaLarga(dia)} · ${NIVEL_TXT[nivel]}</b>${geo.length} geopolíticos · ${atq.length} ataques${ejemplos}` +
    (geo.length + atq.length ? `<div style="color:var(--texto-3);margin-top:3px">Clic para ver el detalle</div>` : "");
  tt.hidden = false;
  let left = ev.clientX - caja.left + 14;
  if (left + 330 > caja.width) left = ev.clientX - caja.left - 330;
  tt.style.left = Math.max(4, left) + "px";
  tt.style.top = ev.clientY - caja.top + 14 + "px";
}

function mostrarDia(dia, v) {
  const box = $("detalle-dia");
  document.querySelectorAll(".hit.sel").forEach((r) => r.classList.remove("sel"));
  if (!v || estado.diaSel === dia) { estado.diaSel = null; box.hidden = true; return; }
  estado.diaSel = dia;
  document.querySelector(`.hit[data-dia="${dia}"]`)?.classList.add("sel");
  const lista = (arr) => arr.length ? `<ul>${arr.map(itemEvento).join("")}</ul>` : `<p class="vacio">Ninguno</p>`;
  box.innerHTML = `<strong>${fechaLarga(dia)}</strong>
    <p style="margin:8px 0 0"><b>Ataques (${v.ataque.length})</b></p>${lista(v.ataque)}
    <p style="margin:8px 0 0"><b>Hechos geopolíticos (${v.geo.length})</b></p>${lista(v.geo.slice(0, 40))}
    ${v.geo.length > 40 ? `<p class="vacio">… y ${v.geo.length - 40} más (ver tabla)</p>` : ""}`;
  box.hidden = false;
}

function chipsMitre(tecnicas) {
  return (tecnicas || []).map((t) => {
    const m = estado.datos.mitre[t];
    const url = m?.url || `https://attack.mitre.org/techniques/${t.replace(".", "/")}/`;
    return `<a class="chip" href="${esc(url)}" target="_blank" rel="noopener" title="${esc(m?.nombre || "")}">${esc(t)}${m ? " · " + esc(m.nombre) : ""}</a>`;
  }).join("");
}
function itemEvento(e) {
  const grupos = (e.grupos || []).map((g) => `<span class="chip">👥 ${esc(g)}</span>`).join("");
  return `<li>${enlace(e.url, e.titulo)} <span class="fecha">— ${esc(e.fuente)} · ${ORIGEN_TXT[e.origen] || e.origen}</span> ${grupos}${chipsMitre(e.tecnicas)}</li>`;
}

// ---------- alertas ----------
function renderAlertas() {
  const d = estado.datos;
  const alertas = d.alertas.filter((a) => {
    if (a.nivel === "amarillo") { const p = d.periodos.find((x) => x.id === a.periodo); return p && p.inicio <= estado.hasta && p.fin >= estado.desde; }
    if (a.nivel === "info" && !$("ver-info").checked) return false;
    return a.fecha >= estado.desde && a.fecha <= estado.hasta;
  });
  const n = (nv) => alertas.filter((a) => a.nivel === nv).length;
  $("contador-alertas").textContent = `${plural(n("rojo"), "roja", "rojas")} · ${plural(n("amarillo"), "amarilla", "amarillas")}` +
    ($("ver-info").checked ? ` · ${plural(n("info"), "informativa", "informativas")}` : "");
  if (!alertas.length) { $("alertas").innerHTML = `<li class="vacio" style="border:0">No hay alertas en el periodo seleccionado.</li>`; return; }
  $("alertas").innerHTML = alertas.map((a) => {
    const evs = (a.eventos || []).map((id) => d.porId[id]).filter(Boolean);
    const det = a.nivel === "rojo" ? (a.detonantes || []).map((id) => d.porId[id]).filter(Boolean) : [];
    const tecnicas = [...new Set(evs.flatMap((e) => e.tecnicas || []))];
    return `<li class="${a.nivel}">
      <div class="alerta-cab"><span class="insignia ${a.nivel}">${NIVEL_TXT[a.nivel]}</span>
      <span class="fecha">${fechaLarga(a.fecha)}${a.hasta ? " → " + fechaLarga(a.hasta) : ""}</span></div>
      <div>${esc(a.titulo)}</div>
      ${tecnicas.length ? `<div>${chipsMitre(tecnicas)}</div>` : ""}
      <details><summary>${a.nivel === "amarillo" ? plural(evs.length, "noticia detonante", "noticias detonantes") : plural(evs.length, "ataque", "ataques")}${det.length ? ` · ${plural(det.length, "detonante relacionado", "detonantes relacionados")}` : ""}</summary>
        <ul>${evs.slice(0, 30).map(itemEvento).join("")}</ul>
        ${det.length ? `<p style="margin:4px 0 0"><b>Contexto geopolítico (detonantes)</b></p><ul>${det.slice(0, 10).map(itemEvento).join("")}</ul>` : ""}
      </details></li>`;
  }).join("");
}

// ---------- tabla accesible ----------
function renderTabla() {
  const evs = eventosEnRango().slice().reverse().slice(0, 1500);
  $("tabla").querySelector("tbody").innerHTML = evs.map((e) => `<tr>
    <td style="white-space:nowrap">${e.dia}</td><td>${e.carril === "geo" ? "Geopolítico" : "Ataque"}</td>
    <td>${enlace(e.url, e.titulo)}</td><td>${esc(e.fuente)}<br><small>${ORIGEN_TXT[e.origen] || e.origen}</small></td>
    <td>${(e.tecnicas || []).join(", ")}</td></tr>`).join("") || `<tr><td colspan="5" class="vacio">Sin eventos en el periodo.</td></tr>`;
}

// ---------- fuentes, metodología e informe IA ----------
function renderFuentes() {
  const f = estado.datos.fuentes;
  if (!f || !f.fuentes) { $("fuentes").innerHTML = `<p class="vacio">Todavía no hay diagnóstico de fuentes.</p>`; return; }
  $("fuentes").innerHTML = `<p>Diagnóstico de la última revisión (${new Date(f.fecha).toLocaleString("es-AR")}):</p>
    <div class="tabla-scroll"><table><thead><tr><th>Fuente</th><th>Estado</th><th>Ítems</th><th>Detalle</th></tr></thead><tbody>
    ${f.fuentes.map((x) => `<tr><td>${esc(x.nombre)}<br><small>${esc(x.url)}</small></td>
      <td class="${x.ok ? "ok-txt" : "falla-txt"}">${x.ok ? "✔ OK" : "✖ Falla"}</td><td>${x.items}</td><td>${esc(x.detalle || "")}</td></tr>`).join("")}
    </tbody></table></div>`;
}
function renderMetodologia() {
  const p = estado.datos.parametros;
  $("metodologia").innerHTML = `<p><b>Cómo se calcula el semáforo.</b> Una noticia es <i>geopolítica relevante</i> si menciona a Argentina
  y sus términos geopolíticos suman al menos ${p.umbral_puntaje_detonante} puntos. Un día es <i>detonante</i> cuando esas noticias aparecen en
  al menos ${p.min_fuentes_distintas_por_dia} fuentes distintas, o cuando hay un hecho clave cargado a mano. Cada detonante abre una
  <i>ventana de vigilancia</i> de ${p.ventana_vigilancia_dias} días (amarillo). Si dentro de la ventana aparece una noticia de ataque
  contra objetivos argentinos, el nivel pasa a rojo hasta que la ventana se cierre. Los ataques fuera de toda ventana se listan como
  alertas informativas para evaluar el modelo.</p>
  <p>Clasificación por reglas de palabras clave (Fase 1). IA: ${p.ia_activada ? "activada" : "no activada (Fase 2 pendiente)"}.</p>`;
}
function renderInforme() {
  const inf = estado.datos.informe_ia;
  if (!inf) return;
  $("informe-ia").hidden = false;
  $("informe-contenido").innerHTML = Object.entries(inf).map(([k, v]) => `<p><b>${esc(k)}:</b> ${esc(typeof v === "string" ? v : JSON.stringify(v))}</p>`).join("");
}

iniciar();
