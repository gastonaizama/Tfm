"""Evaluación del modelo: ¿los ataques caen dentro de las ventanas de vigilancia?

Para cada tamaño de ventana (análisis de sensibilidad) y cada tipo de actor
(hacktivista, cibercriminal, estatal, desconocido) se calcula lo siguiente. Los ataques detectados
automáticamente forman dos grupos aparte: reclamos en canales de Telegram de los grupos y
noticias de ataques.

- n: cantidad de ataques con fecha dentro del período evaluado.
- dentro: cuántos ocurrieron dentro de una ventana de vigilancia.
- pct_dentro: porcentaje de ataques dentro de ventanas.
- cobertura: porcentaje de DÍAS del período cubiertos por ventanas. Es lo que se esperaría
  por azar: si las ventanas cubren el 20 % de los días, un ataque al azar cae dentro
  de una ventana el 20 % de las veces.
- razon: pct_dentro / cobertura. Mayor que 1 indica que ese tipo de actor ataca dentro de
  las ventanas MÁS de lo esperable por azar (evidencia a favor de la hipótesis).
- anticipacion_mediana: días entre el último detonante y el ataque (solo los de dentro).

El grupo de comparación (cibercriminales) debería dar una razón cercana a 1.

Con `confianzas` se puede restringir la evaluación a los incidentes cargados a mano con
cierto nivel de confianza (por ejemplo {"media", "alta"}) para comprobar que las
conclusiones se mantienen sin los datos más débiles (análisis de robustez).
Con `solo_verificados=True` se usan únicamente los incidentes que el autor verificó
(columna `verificado = si`, con su código del Almirantazgo).
"""
from datetime import date, timedelta
from statistics import median

from . import semaforo

GRUPOS = ("hacktivista", "cibercriminal", "estatal", "desconocido", "reclamo_telegram", "detectado_automaticamente")


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def evaluar(eventos: list[dict], cfg_semaforo: dict, ventanas: list[int], inicio: str, fin: str,
            confianzas: set[str] | None = None, solo_verificados: bool = False) -> dict:
    ini, fn = _d(inicio), _d(fin)
    total_dias = (fn - ini).days + 1
    detonantes = semaforo.dias_detonantes(eventos, cfg_semaforo["min_fuentes_distintas_por_dia"])
    dias_detonantes = sorted(_d(d) for d in detonantes)
    ataques = [e for e in eventos if e["carril"] == "ataque" and ini <= _d(e["dia"]) <= fn
               and (confianzas is None or e.get("origen") != "incidente_csv"
                    or (e.get("confianza") or "").lower() in confianzas)
               and (not solo_verificados or e.get("origen") != "incidente_csv"
                    or (e.get("verificado") or "").lower() == "si")]

    # Varias noticias del mismo día suelen describir el MISMO ataque (por ejemplo, cinco medios
    # italianos sobre la filtración de licencias de conducir): en el grupo detectado
    # automáticamente se cuenta un solo evento por día (los reclamos de Telegram, aparte: un grupo
    # suele publicar varios objetivos el mismo día). Los incidentes cargados a mano no se agrupan.
    vistos, depurados = set(), []
    for e in ataques:
        if e.get("origen") != "incidente_csv":
            clave = (e.get("origen") == "telegram", e["dia"])
            if clave in vistos:
                continue
            vistos.add(clave)
        depurados.append(e)
    ataques = depurados

    resultados = []
    for v in ventanas:
        periodos = semaforo.periodos_vigilancia(detonantes, v)
        cubiertos = set()
        for p in periodos:
            d = max(_d(p["inicio"]), ini)
            while d <= min(_d(p["fin"]), fn):
                cubiertos.add(d)
                d += timedelta(days=1)
        cobertura = len(cubiertos) / total_dias if total_dias > 0 else 0

        grupos = {g: {"n": 0, "dentro": 0, "anticipaciones": [], "ids_dentro": [], "ids_fuera": []} for g in GRUPOS}
        for e in ataques:
            if e.get("origen") == "incidente_csv":
                g = e.get("tipo_actor")
            else:
                g = "reclamo_telegram" if e.get("origen") == "telegram" else "detectado_automaticamente"
            g = g if g in grupos else "desconocido"
            dia = _d(e["dia"])
            grupos[g]["n"] += 1
            if dia in cubiertos:
                grupos[g]["dentro"] += 1
                grupos[g]["ids_dentro"].append(e["id"])
                previos = [t for t in dias_detonantes if t <= dia]
                if previos:
                    grupos[g]["anticipaciones"].append((dia - previos[-1]).days)
            else:
                grupos[g]["ids_fuera"].append(e["id"])

        salida = {}
        for g, x in grupos.items():
            pct = x["dentro"] / x["n"] if x["n"] else None
            salida[g] = {
                "n": x["n"], "dentro": x["dentro"],
                "pct_dentro": round(pct * 100, 1) if pct is not None else None,
                "razon": round(pct / cobertura, 2) if pct is not None and cobertura > 0 else None,
                "anticipacion_mediana": median(x["anticipaciones"]) if x["anticipaciones"] else None,
                "ids_dentro": x["ids_dentro"], "ids_fuera": x["ids_fuera"],
            }
        resultados.append({"ventana_dias": v, "cobertura_pct": round(cobertura * 100, 1),
                           "periodos": len(periodos), "grupos": salida})
    return {"inicio": ini.isoformat(), "fin": fn.isoformat(), "dias": total_dias,
            "confianzas": sorted(confianzas) if confianzas else "todas",
            "solo_verificados": solo_verificados,
            "detonantes": len(dias_detonantes), "ventanas": resultados}
