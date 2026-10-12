"""Clasificación por reglas (Fase 1, sin IA).

Cada noticia recibe:
- puntaje_geo: suma de los pesos de los términos geopolíticos encontrados,
  pero solo si además se menciona a Argentina.
- es_ataque: tiene al menos un término cibernético Y menciona a Argentina
  (o un dominio .gob.ar / .ar).
- técnicas MITRE ATT&CK según config/mitre_mapeo.json.

En la Fase 2 este módulo se podrá reemplazar (o complementar) por
monitor/ia/clasificador_haiku.py, que devolverá la misma estructura.
"""
from .texto import buscar_mayusculas, buscar_terminos, normalizar


class Clasificador:
    def __init__(self, config: dict, mapeo_mitre: dict):
        pc = config["palabras_clave"]
        self.pais = pc["pais_objetivo"]
        self.geo = pc["geopoliticas"]
        self.ciber = pc["ciberneticas"]
        self.grupos = pc["grupos_hacktivistas"]
        self.mayus = pc.get("terminos_sensibles_mayusculas", [])
        self.reglas_mitre = mapeo_mitre["reglas"]
        self.umbral = config["semaforo"]["umbral_puntaje_detonante"]

    def clasificar(self, titulo: str, resumen: str = "", url: str = "") -> dict:
        original = f"{titulo} {resumen}"
        texto = normalizar(original)
        texto_con_url = f"{texto} {normalizar(url)}"

        menciona_ar = bool(buscar_terminos(texto, self.pais)) or ".gob.ar" in texto_con_url or "amia" in texto
        terminos_geo = buscar_terminos(texto, self.geo.keys())
        puntaje = sum(self.geo[t] for t in terminos_geo) if menciona_ar else 0

        terminos_ciber = buscar_terminos(texto, self.ciber) + buscar_mayusculas(original, self.mayus)
        mayus_norm = {normalizar(m) for m in self.mayus}
        grupos_normales = [g for g in self.grupos if normalizar(g) not in mayus_norm]
        grupos = buscar_terminos(texto, grupos_normales) + [
            m for m in buscar_mayusculas(original, self.mayus) if normalizar(m) in {normalizar(g) for g in self.grupos}
        ]
        es_ataque = bool(terminos_ciber) and menciona_ar

        tecnicas, categorias = [], []
        if es_ataque:
            for regla in self.reglas_mitre:
                if buscar_terminos(texto, regla["terminos"]):
                    categorias.append(regla["categoria"])
                    tecnicas.extend(t for t in regla["tecnicas"] if t not in tecnicas)

        return {
            "menciona_argentina": menciona_ar,
            "terminos_geo": terminos_geo,
            "puntaje_geo": puntaje,
            "es_geo_relevante": puntaje >= self.umbral,
            "terminos_ciber": sorted(set(terminos_ciber)),
            "grupos": sorted(set(grupos)),
            "es_ataque": es_ataque,
            "tecnicas": tecnicas,
            "categorias_ataque": categorias,
        }

    def carril(self, c: dict) -> str | None:
        """Carril de la línea de tiempo: 'ataque', 'geo' o None (se descarta)."""
        if c["es_ataque"]:
            return "ataque"
        if c["es_geo_relevante"]:
            return "geo"
        return None
