# Monitor Ciber-Geopolítico · Argentina

**Plataforma de alerta temprana que relaciona hechos geopolíticos con ciberataques contra Argentina.**
Trabajo Final del Máster en Cyber Threat Intelligence (KSchool).

🌐 **Página publicada:** https://gastonaizama.github.io/Tfm/

---

## 1. ¿Qué hace?

La plataforma revisa noticias y feeds **cada 6 horas** y busca dos tipos de señales:

| Señal | Ejemplo | Dónde aparece |
|---|---|---|
| **Hecho geopolítico detonante** | Argentina anuncia el traslado de su embajada a Jerusalén | carril superior de la línea de tiempo |
| **Ataque contra objetivos argentinos** | Hacktivistas reivindican la caída de sitios `gob.ar` | carril inferior de la línea de tiempo |

Con el cruce de ambas señales calcula un **semáforo de riesgo**:

- 🟢 **Verde**: no hay hechos detonantes recientes.
- 🟡 **Amarillo**: se detectó un hecho geopolítico detonante y se abre una **ventana de vigilancia de 7 días**. La duración se puede cambiar.
- 🔴 **Rojo**: dentro de esa ventana aparecen noticias de ataques contra objetivos argentinos.

**Caso de estudio:** el hacktivismo pro-Palestina contra Argentina tras su acercamiento a Israel, entre agosto de 2023 y julio de 2024.

La página tiene una sola pantalla:
1. **Arriba**, el semáforo con el nivel actual y un resumen del periodo.
2. **En el centro**, la línea de tiempo con dos carriles: hechos geopolíticos arriba y ataques abajo. Las ventanas de vigilancia aparecen sombreadas y debajo hay una franja con el nivel de cada día. Al pasar el mouse por un día se ve un resumen, y con un clic se ven todas sus noticias.
3. **Abajo**, la lista de alertas con sus noticias, los grupos detectados y las técnicas MITRE ATT&CK.
4. **Selector de fechas**, que permite pasar del modo **en vivo** (últimos 30 días) al modo **histórico** (cualquier rango; un botón carga directamente el caso de estudio).

---

## 2. ¿Cómo funciona?

```
           cada 6 horas (GitHub Actions)
                      │
   ┌──────────────────┼───────────────────────┐
   ▼                  ▼                        ▼
Feeds RSS        GDELT DOC API          Archivos manuales (CSV)
(6 medios)       (noticias mundiales)   hechos clave + incidentes
   └──────────────────┼───────────────────────┘
                      ▼
        Clasificador por palabras clave
   (geopolítica + Argentina / ciber + Argentina)
                      │
                      ├──► MITRE ATT&CK (técnicas del ataque)
                      ▼
              Motor del semáforo
     (días detonantes → ventanas → nivel diario)
                      ▼
               web/datos.json ──► GitHub Pages (la página)
```

No hay servidores ni bases de datos. Todo funciona con dos servicios gratuitos de GitHub:
- **GitHub Actions** ejecuta el programa en Python cada 6 horas y guarda los resultados en el propio repositorio.
- **GitHub Pages** publica la página web, que lee esos resultados.

### Reglas de la Fase 1 (sin inteligencia artificial)

1. **Noticia geopolítica relevante**: menciona a Argentina y sus términos geopolíticos suman **2 puntos o más**. Valen 2 puntos Hamás, Irán, AMIA y Hezbolá; valen 1 punto Israel, Palestina, Gaza, Jerusalén, embajada y ONU. Así, "Argentina e Israel" sola no alcanza, pero "embajada argentina en Jerusalén" sí.
2. **Día detonante**: hay noticias relevantes de **al menos 2 fuentes distintas** ese día (corroboración), o hay un **hecho clave** cargado a mano.
3. **Ventana de vigilancia**: cada día detonante abre una ventana de 7 días. Si llega otro detonante con la ventana todavía abierta, la ventana se extiende.
4. **Noticia de ataque**: contiene un término cibernético (hackeo, filtración de datos, DDoS, hacktivistas, gob.ar, Cyber Dragonz, LulzSec Muslims, REM, etc.) **y** menciona a Argentina.
5. **Rojo**: aparece un ataque dentro de una ventana abierta. Los ataques fuera de cualquier ventana se muestran como alertas **informativas**, porque sirven para evaluar el modelo.

Todos los números se pueden cambiar en [`config/config.json`](config/config.json).

---

## 3. Fuentes

| Fuente | Tipo | Estado (prueba del 12/10/2026) |
|---|---|---|
| [The Record](https://therecord.media/feed) | Ciberseguridad (EN) | ✅ |
| [BleepingComputer](https://www.bleepingcomputer.com/feed/) | Ciberseguridad (EN) | ✅ |
| [The Hacker News](https://feeds.feedburner.com/TheHackersNews) | Ciberseguridad (EN) | ✅ |
| [WeLiveSecurity – ESET](https://www.welivesecurity.com/es/rss/feed/) | Ciberseguridad (ES) | ✅ (la dirección `/es/feed/` da error 404) |
| [Infobae](https://www.infobae.com/arc/outboundfeeds/rss/) | Medio argentino | ✅ |
| [La Nación](https://www.lanacion.com.ar/arc/outboundfeeds/rss/?outputType=xml) | Medio argentino | ✅ |
| [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) | Noticias mundiales, con historial | ✅ (con límite de una consulta cada 5 segundos) |
| [MITRE ATT&CK](https://github.com/mitre/cti) | Catálogo de técnicas | ✅ |

La página muestra en cada revisión el estado de cada fuente, en la sección "Estado de las fuentes y metodología".

---

## 4. Organización del repositorio

```
Tfm/
├── config/
│   ├── config.json            ← palabras clave, fuentes, días de la ventana, umbrales
│   └── mitre_mapeo.json       ← reglas palabra → técnica MITRE ATT&CK
├── datos/
│   ├── incidentes_historicos.csv  ← ATAQUES conocidos (carga manual)
│   ├── hechos_clave.csv           ← HECHOS geopolíticos de referencia (carga manual)
│   ├── gdelt_historico.json       ← noticias GDELT ago-2023 → jul-2024 (se genera solo)
│   ├── noticias_vivo.json         ← archivo propio de noticias relevantes vistas en vivo
│   ├── mitre_tecnicas.json        ← nombres oficiales de las técnicas usadas
│   └── estado_fuentes.json        ← diagnóstico de la última revisión
├── monitor/                   ← programa en Python
│   ├── fuentes/rss.py, gdelt.py   ← conectores
│   ├── clasificador.py            ← reglas de palabras clave
│   ├── semaforo.py                ← lógica verde / amarillo / rojo
│   ├── historico.py               ← modo histórico
│   ├── mitre.py                   ← catálogo ATT&CK
│   ├── procesar.py                ← proceso completo
│   └── ia/                        ← FASE 2 (preparada, desactivada)
├── web/                       ← la página (HTML + CSS + JavaScript, sin librerías)
│   └── datos.json                 ← resultado que lee la página (se genera solo)
├── tests/test_reglas.py       ← pruebas automáticas de las reglas
├── docs/decisiones_tecnicas.md← decisiones de diseño (para la memoria del TFM)
└── .github/workflows/
    ├── actualizar.yml         ← cada 6 h: recolecta, calcula, guarda y publica
    └── verificar.yml          ← prueba los cambios antes de unirlos a main
```

---

## 5. Modo histórico y carga manual de incidentes

Los feeds RSS solo muestran las últimas noticias, así que el periodo **agosto 2023 – julio 2024** se arma con tres fuentes:

1. **GDELT**: se descarga una sola vez, de forma automática, en la primera ejecución. Se guarda en `datos/gdelt_historico.json`.
2. **`datos/hechos_clave.csv`**: hechos geopolíticos de referencia (7 de octubre de 2023, anuncio del traslado de la embajada, fallo AMIA, etc.). Cada uno abre una ventana por sí solo. ⚠️ Están marcados como `verificado = no`: revisá las fechas y completá la columna `fuente_url`.
3. **`datos/incidentes_historicos.csv`**: los ataques conocidos que documentes en tu investigación.

### Columnas de `incidentes_historicos.csv`

| Columna | Qué poner | Ejemplo |
|---|---|---|
| `id` | identificador único | `INC-001` |
| `fecha` | fecha del ataque, formato AAAA-MM-DD | `2024-02-08` |
| `grupo` | actor que lo reivindica | `Cyber Dragonz` |
| `objetivo` | organización atacada | `Municipalidad de X` |
| `dominio_objetivo` | sitio web afectado | `x.gob.ar` |
| `sector` | gobierno, salud, educación, finanzas, medios… | `gobierno` |
| `tipo_ataque` | defacement, ddos, filtracion, otro | `ddos` |
| `tecnicas_mitre` | IDs ATT&CK separados por `;` | `T1498;T1499` |
| `descripcion` | resumen breve | |
| `motivacion_declarada` | lo que dice el grupo | `respuesta al traslado de la embajada` |
| `fuente_nombre` / `fuente_url` | de dónde sale el dato | medio, Telegram, X… |
| `confianza` | alta / media / baja | `media` |
| `verificado` | si / no | `si` |

**Cómo editarlo sin instalar nada:** en GitHub abrí el archivo, pulsá el ícono del lápiz ✏️, agregá una fila por incidente y pulsá **Commit changes**. La página se actualiza sola en unos minutos. Las filas cuyo `id` empieza con `EJEMPLO` se ignoran.

> Consejo: si usás Excel o Google Sheets, guardá como **CSV UTF-8** para no perder las tildes.

---

## 6. Cómo replicar la plataforma (sin instalar nada)

1. **Copiá el repositorio**: en GitHub pulsá **Fork**, o creá un repositorio nuevo y subí estos archivos.
2. **Activá GitHub Pages**: *Settings → Pages → Build and deployment → Source:* **GitHub Actions**.
3. **Dale permiso de escritura a Actions**: *Settings → Actions → General → Workflow permissions:* **Read and write permissions** → *Save*.
4. **Hacé la primera ejecución**: pestaña *Actions → Actualizar monitor → Run workflow*. La primera vez tarda alrededor de **1 hora**, porque descarga el histórico de GDELT. Después tarda unos 2 minutos.
5. Abrí `https://<tu-usuario>.github.io/<repositorio>/`.

A partir de ahí la revisión corre sola cada 6 horas (00:17, 06:17, 12:17 y 18:17 UTC).

**Opciones del botón *Run workflow*:**
- `actualizar`: revisión normal.
- `recalcular`: recalcula el semáforo sin descargar noticias. Sirve después de cambiar `config.json`.
- `historico`: vuelve a descargar el histórico de GDELT.

### Probarlo en una computadora (opcional)
```bash
pip install -r requirements.txt
python -m unittest -v              # pruebas
python -m monitor actualizar       # revisión completa
python -m http.server -d web 8000  # abrir http://localhost:8000
```

---

## 7. Fase 2: inteligencia artificial (preparada, no implementada)

La estructura ya está lista en `monitor/ia/`:
- **Claude Haiku 5.5** (`claude-haiku-5-5`) clasificará cada noticia en cada revisión, en lugar de las palabras clave o junto con ellas.
- **Claude Sonnet 5.5** (`claude-sonnet-5-5`) redactará un informe de inteligencia **solo cuando haya alerta**, para controlar el costo. El informe aparecerá en la página debajo del semáforo.

Para activarla cuando esté implementada:
1. *Settings → Secrets and variables → Actions → New repository secret*, con nombre `ANTHROPIC_API_KEY` y como valor la clave. **La clave nunca se escribe en el código.**
2. En `config/config.json` cambiar `"ia": { "activada": true }`.

---

## 8. Limitaciones conocidas

- **Palabras clave**: hay falsos positivos (noticias que mencionan los términos sin relación real) y falsos negativos (ataques descritos con otras palabras). La Fase 2 busca reducir ambos.
- Solo se analizan el **título y el resumen** de cada noticia, no el texto completo.
- La DOC API de GDELT devuelve como máximo 250 artículos por consulta. Los tramos que llegan a ese máximo quedan marcados como "saturados" en `gdelt_historico.json`.
- Los grupos hacktivistas suelen anunciar sus ataques en Telegram o X, fuentes que esta fase no monitorea. Por eso existe la carga manual de incidentes.
- El semáforo indica **correlación temporal**, no atribución.

---

## 9. Créditos y licencias de los datos

- [The GDELT Project](https://www.gdeltproject.org/): uso libre con atribución.
- [MITRE ATT&CK®](https://attack.mitre.org/): © The MITRE Corporation, usado según sus [términos de uso](https://attack.mitre.org/resources/legal-and-branding/terms-of-use/).
- Los titulares y enlaces pertenecen a sus medios. La plataforma solo guarda el título, un resumen breve y el enlace.

Las decisiones técnicas y su justificación están en [`docs/decisiones_tecnicas.md`](docs/decisiones_tecnicas.md).
