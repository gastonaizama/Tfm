"""Utilidades de texto: normalización y búsqueda de términos como palabras completas."""
import html
import re
import unicodedata
from functools import lru_cache


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni etiquetas HTML, espacios simples."""
    if not texto:
        return ""
    texto = html.unescape(re.sub(r"<[^>]+>", " ", texto))
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def limpiar_html(texto: str, max_len: int = 300) -> str:
    """Texto legible (con tildes) para mostrar en la web."""
    if not texto:
        return ""
    plano = html.unescape(re.sub(r"<[^>]+>", " ", texto))
    plano = re.sub(r"\s+", " ", plano).strip()
    return plano if len(plano) <= max_len else plano[: max_len - 1].rstrip() + "…"


@lru_cache(maxsize=4096)
def _patron(termino: str) -> re.Pattern:
    # \b no funciona bien con términos que terminan en signos (p. ej. "cve-"), por eso
    # se usan límites explícitos: no puede haber letra o número pegado antes/después.
    return re.compile(r"(?<![a-z0-9])" + re.escape(termino) + r"(?![a-z0-9])")


def buscar_terminos(texto_normalizado: str, terminos) -> list[str]:
    """Devuelve los términos (ya normalizados) que aparecen como palabra completa."""
    encontrados = []
    for t in terminos:
        tn = normalizar(t)
        if tn and _patron(tn).search(texto_normalizado):
            encontrados.append(t)
    return encontrados


def buscar_mayusculas(texto_original: str, terminos) -> list[str]:
    """Términos ambiguos (p. ej. 'REM') que solo cuentan escritos en MAYÚSCULAS."""
    return [t for t in terminos if re.search(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])", texto_original or "")]
