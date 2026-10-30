"""Lectura de canales PÚBLICOS de Telegram a través de su vista web (https://t.me/s/<canal>).

No usa cuenta ni claves: es la misma página que ve cualquier persona en el navegador.
Solo funciona con canales públicos; los grupos privados (enlaces con "+") no tienen vista web.

Lo que publica un grupo en su propio canal es un RECLAMO: sirve para fechar el ataque y
conocer la motivación declarada, pero no prueba que el ataque haya ocurrido. Por eso cada
mensaje se marca con origen "telegram" y se muestra como "reclamo del grupo".
Para no republicar datos filtrados, solo se guarda el texto del mensaje (recortado), nunca
archivos adjuntos ni imágenes.
"""
import html
import re

import requests

from ..texto import limpiar_html

CABECERAS = {"User-Agent": "Mozilla/5.0 (compatible; TFM-CTI-Monitor/1.0; +https://github.com/gastonaizama/Tfm)"}

_MENSAJE = re.compile(r'data-post="([^"/]+)/(\d+)"')
# Las respuestas citan otro mensaje con la clase "js-message_reply_text": se toma solo el texto propio.
_TEXTO = re.compile(r'<div class="tgme_widget_message_text js-message_text[^"]*"[^>]*>(.*?)</div>', re.S)
_FECHA = re.compile(r'<time[^>]*datetime="([^"]+)"')


def _texto_plano(fragmento: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<br\s*/?>", "\n", fragmento)))


def parsear_pagina(contenido: str, canal: dict) -> list[dict]:
    """Convierte la página t.me/s/<canal> en una lista de noticias (formato común del monitor)."""
    trozos = _MENSAJE.split(contenido)
    # split devuelve [antes, canal, numero, cuerpo, canal, numero, cuerpo, ...]
    mensajes = []
    for i in range(1, len(trozos) - 2, 3):
        nombre_canal, numero, cuerpo = trozos[i], trozos[i + 1], trozos[i + 2]
        fecha = _FECHA.search(cuerpo)
        texto = _TEXTO.search(cuerpo)
        if not fecha or not texto:
            continue  # mensajes sin texto (solo imagen o archivo) o de servicio
        plano = _texto_plano(texto.group(1))
        primera_linea = next((l.strip() for l in plano.splitlines() if l.strip()), "")
        mensajes.append({
            "titulo": limpiar_html(primera_linea, 200) or f"Mensaje {numero}",
            "resumen": limpiar_html(plano, 600),
            "url": f"https://t.me/{nombre_canal}/{numero}",
            "fecha": fecha.group(1),
            "fuente": f"Telegram · {canal['nombre']}",
            "origen": "telegram",
            "idioma": canal.get("idioma", ""),
            "numero_mensaje": int(numero),
        })
    return mensajes


def describir_pagina(contenido: str, url_final: str) -> str:
    """Explica por qué una página no tiene mensajes (para el diagnóstico de la fuente)."""
    titulo = re.search(r'<meta property="og:title" content="([^"]*)"', contenido)
    titulo = html.unescape(titulo.group(1)) if titulo else "sin título"
    if "/s/" not in url_final:
        motivo = "Telegram redirigió fuera de la vista pública (el canal no la tiene activada, es privado o no existe)"
    elif "tgme_channel_info" in contenido:
        motivo = "el canal existe pero no muestra mensajes de texto"
    else:
        motivo = "la página no tiene el formato de un canal público"
    return f"{motivo}; título de la página: «{titulo}»; dirección final: {url_final}"[:300]


def leer_canal(canal: dict) -> tuple[list[dict], dict]:
    """Lee las últimas páginas del canal. Nunca lanza excepción: un canal caído no detiene el resto."""
    url = f"https://t.me/s/{canal['canal']}"
    diag = {"nombre": f"Telegram · {canal['nombre']}", "url": url, "ok": False, "items": 0, "detalle": ""}
    mensajes, antes = [], None
    try:
        for _ in range(max(1, canal.get("paginas", 1))):
            r = requests.get(url, params={"before": antes} if antes else None, headers=CABECERAS, timeout=30)
            diag["http"] = r.status_code
            r.raise_for_status()
            pagina = parsear_pagina(r.text, canal)
            if not pagina:
                if not mensajes:
                    diag["detalle_pagina"] = describir_pagina(r.text, r.url)
                break
            mensajes.extend(pagina)
            antes = min(m["numero_mensaje"] for m in pagina)
        vistos, unicos = set(), []
        for m in mensajes:
            if m["url"] not in vistos:
                vistos.add(m["url"])
                unicos.append(m)
        diag.update(ok=len(unicos) > 0, items=len(unicos),
                    detalle="" if unicos else "sin mensajes visibles: " + diag.get("detalle_pagina", ""))
        return unicos, diag
    except Exception as ex:
        diag["detalle"] = f"{type(ex).__name__}: {ex}"[:300]
        return mensajes, diag
