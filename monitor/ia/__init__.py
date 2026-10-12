"""FASE 2 (preparada, NO implementada): integración con la API de Claude.

- clasificador_haiku.py: Claude Haiku 5.5 clasificará cada noticia en cada revisión
  (reemplaza o complementa las reglas de palabras clave de monitor/clasificador.py).
- informe_sonnet.py: Claude Sonnet 5.5 redactará un informe de inteligencia
  SOLO cuando el semáforo esté en rojo (o amarillo, si se configura).
- La API key se leerá de la variable de entorno ANTHROPIC_API_KEY, que GitHub
  Actions completa a partir de un *secreto* del repositorio. Nunca va en el código.
"""
