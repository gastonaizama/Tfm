"""Punto único de conexión entre el proceso principal y la IA (Fase 2)."""
import os


def procesar_si_esta_activada(config: dict, eventos: list[dict], resultado: dict) -> dict | None:
    cfg = config.get("ia", {})
    if not cfg.get("activada"):
        return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[IA] 'ia.activada' es true pero falta el secreto ANTHROPIC_API_KEY: se omite la IA.")
        return None
    # Cuando se implemente la Fase 2:
    #   from .clasificador_haiku import clasificar_eventos
    #   from .informe_sonnet import redactar_informe
    #   eventos = clasificar_eventos(eventos, cfg["modelo_clasificador"])
    #   if resultado["actual"]["nivel"] == "rojo" or not cfg["generar_informe_solo_en_rojo"]:
    #       return redactar_informe(eventos, resultado, cfg["modelo_informe"])
    print("[IA] La Fase 2 todavía no está implementada.")
    return None
