"""FASE 2 – Informe de inteligencia con Claude Sonnet 5.5 (pendiente).

Se invocará solo cuando haya alerta, para controlar el costo. Devolverá un dict:
  {"modelo", "fecha", "nivel", "resumen_ejecutivo", "contexto_geopolitico",
   "actividad_observada", "tecnicas_mitre", "evaluacion", "recomendaciones", "fuentes"}
que la web mostrará debajo del semáforo (campo "informe_ia" de web/datos.json).
Ver el borrador de instrucciones en monitor/ia/prompts/informe.md.
"""


def redactar_informe(eventos: list[dict], resultado: dict, modelo: str) -> dict:
    raise NotImplementedError("Fase 2: pendiente de implementación")
