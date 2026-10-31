"""Lógica del semáforo de alertas (Fase 1: reglas de palabras clave + fechas).

Reglas:
1. Un DÍA es "detonante" según `modo_detonantes`:
   - "curado" (por defecto): solo los días con un hecho clave cargado a mano
     (datos/hechos_clave.csv). Las noticias que en modo automático habrían sido
     detonantes NO abren ventana: se proponen como candidatos (ver `candidatos_por_dia`)
     para que el autor las revise.
   - "automatico": además de los hechos clave, los días con noticias geopolíticas
     relevantes (puntaje >= umbral) de al menos `min_fuentes_distintas_por_dia`
     fuentes distintas (corroboración).
2. Cada día detonante abre una VENTANA DE VIGILANCIA desde ese día hasta
   `ventana_vigilancia_dias` días después. Ventanas que se solapan se fusionan en
   un único "periodo de vigilancia" (un detonante nuevo extiende el plazo).
3. Nivel de un día:
   - ROJO: el día está dentro de un periodo y, entre el inicio del periodo y ese
     día, apareció al menos un ataque contra objetivos argentinos.
   - AMARILLO: el día está dentro de un periodo, sin ataques todavía.
   - VERDE: el día no está dentro de ningún periodo.
"""
from collections import defaultdict
from datetime import date, timedelta

NIVELES = ("verde", "amarillo", "rojo")


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def _detonantes_automaticos(eventos: list[dict], min_por_dia: int) -> dict[str, list[dict]]:
    """{dia: [noticias]} con los días que cumplen la regla automática (sin contar hechos clave)."""
    por_dia = defaultdict(list)
    for e in eventos:
        if e["carril"] == "geo" and e["origen"] != "hecho_clave":
            por_dia[e["dia"]].append(e)
    # Corroboración: cuenta cada fuente (dominio/medio) una sola vez por día.
    return {dia: evs for dia, evs in por_dia.items() if len({e["fuente"] for e in evs}) >= min_por_dia}


def candidatos_por_dia(eventos: list[dict], min_por_dia: int) -> list[dict]:
    """Un candidato a hecho clave por cada día que sería detonante en modo automático:
    la noticia de mayor puntaje, más la cantidad de noticias y de fuentes de ese día."""
    candidatos = []
    for dia, evs in sorted(_detonantes_automaticos(eventos, min_por_dia).items()):
        mejor = max(evs, key=lambda e: (e.get("puntaje_geo", 0), e.get("titulo", "")))
        candidatos.append({"dia": dia, "titulo": mejor.get("titulo", ""), "fuente": mejor.get("fuente", ""),
                           "url": mejor.get("url", ""), "puntaje": mejor.get("puntaje_geo", 0),
                           "n_noticias": len(evs), "n_fuentes": len({e["fuente"] for e in evs})})
    return candidatos


def dias_detonantes(eventos: list[dict], min_por_dia: int, modo: str = "curado") -> dict[str, list[str]]:
    """{dia: [ids de eventos que lo hacen detonante]}"""
    curados = defaultdict(list)
    for e in eventos:
        if e["carril"] == "geo" and e["origen"] == "hecho_clave":
            curados[e["dia"]].append(e["id"])
    resultado = {}
    if modo == "automatico":
        resultado = {dia: [e["id"] for e in evs] for dia, evs in _detonantes_automaticos(eventos, min_por_dia).items()}
    elif modo != "curado":
        raise ValueError(f"modo_detonantes desconocido: {modo!r} (usar 'curado' o 'automatico')")
    for dia, ids in curados.items():
        resultado.setdefault(dia, [])
        resultado[dia] = ids + resultado[dia]
    return resultado


def periodos_vigilancia(detonantes: dict[str, list[str]], ventana: int) -> list[dict]:
    periodos = []
    for dia in sorted(detonantes):
        d = _d(dia)
        fin = d + timedelta(days=ventana)
        if periodos and d <= _d(periodos[-1]["fin"]):
            p = periodos[-1]
            p["fin"] = max(_d(p["fin"]), fin).isoformat()
            p["dias_detonantes"].append(dia)
            p["eventos_detonantes"].extend(detonantes[dia])
        else:
            periodos.append({"inicio": dia, "fin": fin.isoformat(), "dias_detonantes": [dia],
                             "eventos_detonantes": list(detonantes[dia])})
    for i, p in enumerate(periodos, 1):
        p["id"] = f"P{i:03d}-{p['inicio']}"
    return periodos


def calcular(eventos: list[dict], cfg_semaforo: dict, hoy: date) -> dict:
    ventana = cfg_semaforo["ventana_vigilancia_dias"]
    detonantes = dias_detonantes(eventos, cfg_semaforo["min_fuentes_distintas_por_dia"],
                                 cfg_semaforo.get("modo_detonantes", "curado"))
    periodos = periodos_vigilancia(detonantes, ventana)

    ataques_por_dia = defaultdict(list)
    for e in eventos:
        if e["carril"] == "ataque":
            ataques_por_dia[e["dia"]].append(e["id"])

    alertas = []
    dias_en_periodo = {}
    for p in periodos:
        ini, fin = _d(p["inicio"]), _d(p["fin"])
        p["ataques"] = []
        primer_ataque = None
        for dia in sorted(ataques_por_dia):
            if ini <= _d(dia) <= fin:
                p["ataques"].extend(ataques_por_dia[dia])
                primer_ataque = primer_ataque or dia
                alertas.append({
                    "id": f"R-{dia}-{p['id']}", "nivel": "rojo", "fecha": dia, "periodo": p["id"],
                    "titulo": f"Ataque contra objetivos argentinos dentro de la ventana de vigilancia abierta el {p['inicio']}",
                    "eventos": ataques_por_dia[dia], "detonantes": p["eventos_detonantes"][:20],
                })
        p["nivel_max"] = "rojo" if p["ataques"] else "amarillo"
        p["primer_ataque"] = primer_ataque
        alertas.append({
            "id": f"A-{p['id']}", "nivel": "amarillo", "fecha": p["inicio"], "periodo": p["id"],
            "titulo": f"Hecho geopolítico detonante: ventana de vigilancia hasta el {p['fin']}",
            "eventos": p["eventos_detonantes"][:20], "detonantes": p["eventos_detonantes"][:20],
            "hasta": p["fin"],
        })
        d = ini
        while d <= fin:
            rojo = primer_ataque is not None and d >= _d(primer_ataque)
            dias_en_periodo[d.isoformat()] = ("rojo" if rojo else "amarillo", p["id"])
            d += timedelta(days=1)

    # Ataques fuera de cualquier ventana: no cambian el semáforo, pero se informan
    # porque son útiles para evaluar el modelo (posibles falsos negativos).
    for dia, ids in ataques_por_dia.items():
        if dia not in dias_en_periodo:
            alertas.append({"id": f"I-{dia}", "nivel": "info", "fecha": dia, "periodo": None,
                            "titulo": "Ataque detectado sin hecho geopolítico detonante previo",
                            "eventos": ids, "detonantes": []})

    # Serie diaria completa (para que la web muestre el nivel de cualquier fecha)
    todas = [e["dia"] for e in eventos] + [p["fin"] for p in periodos]
    inicio_serie = min([_d(x) for x in todas], default=hoy)
    fin_serie = max([hoy] + [_d(x) for x in todas])
    serie = []
    d = inicio_serie
    while d <= fin_serie:
        nivel, pid = dias_en_periodo.get(d.isoformat(), ("verde", None))
        serie.append({"dia": d.isoformat(), "nivel": nivel, "periodo": pid})
        d += timedelta(days=1)

    nivel_hoy, pid_hoy = dias_en_periodo.get(hoy.isoformat(), ("verde", None))
    periodo_hoy = next((p for p in periodos if p["id"] == pid_hoy), None)
    alertas.sort(key=lambda a: (a["fecha"], NIVELES.index(a["nivel"]) if a["nivel"] in NIVELES else -1), reverse=True)
    return {
        "actual": {"fecha": hoy.isoformat(), "nivel": nivel_hoy, "periodo": periodo_hoy},
        "periodos": periodos,
        "alertas": alertas,
        "serie_diaria": serie,
    }
