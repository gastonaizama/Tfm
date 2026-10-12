"""FASE 2 – Clasificación de noticias con Claude Haiku 5.5 (pendiente).

Contrato previsto: recibir la lista de eventos y devolverla con los mismos campos que
produce monitor/clasificador.py (carril, puntaje_geo, tecnicas, grupos), más:
  - "confianza_ia": alta / media / baja
  - "justificacion_ia": una frase explicando la clasificación
Ver el borrador de instrucciones en monitor/ia/prompts/clasificacion.md.
"""


def clasificar_eventos(eventos: list[dict], modelo: str) -> list[dict]:
    raise NotImplementedError("Fase 2: pendiente de implementación")
