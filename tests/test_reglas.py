"""Pruebas de las reglas (se ejecutan con: python -m unittest)."""
import unittest
from datetime import date

from monitor import semaforo
from monitor.clasificador import Clasificador
from monitor.config import cargar_config, cargar_mapeo_mitre

CFG = cargar_config()
CLF = Clasificador(CFG, cargar_mapeo_mitre())
# Las pruebas de la regla automática (noticias de 2 o más fuentes) indican el modo explícitamente,
# porque desde el 30/10/2026 el modo por defecto es "curado".
SEM = {"ventana_vigilancia_dias": 7, "min_fuentes_distintas_por_dia": 2, "modo_detonantes": "automatico"}
SEM_CURADO = {**SEM, "modo_detonantes": "curado"}


def ev(id_, dia, carril, fuente="X", origen="rss"):
    return {"id": id_, "dia": dia, "carril": carril, "fuente": fuente, "origen": origen}


class TestClasificador(unittest.TestCase):
    def test_hecho_geopolitico(self):
        c = CLF.clasificar("Milei anunció que trasladará la embajada argentina a Jerusalén")
        self.assertEqual(CLF.carril(c), "geo")

    def test_geo_debil_se_descarta(self):
        c = CLF.clasificar("Argentina votó en la ONU una resolución sobre pesca")
        self.assertIsNone(CLF.carril(c))

    def test_sin_argentina_no_cuenta(self):
        c = CLF.clasificar("Hamás e Irán: nueva escalada en Medio Oriente")
        self.assertEqual(c["puntaje_geo"], 0)

    def test_ataque_defacement(self):
        c = CLF.clasificar("Hacktivistas pro Palestina hackearon el sitio de un municipio argentino",
                           "El defacement mostró mensajes contra Israel")
        self.assertEqual(CLF.carril(c), "ataque")
        self.assertIn("T1491.002", c["tecnicas"])

    def test_ataque_ddos_gob_ar(self):
        c = CLF.clasificar("Cyber Dragonz reivindica DDoS contra portales gob.ar")
        self.assertTrue(c["es_ataque"])
        self.assertIn("cyber dragonz", c["grupos"])
        self.assertIn("T1498", c["tecnicas"])

    def test_rem_solo_en_mayusculas(self):
        self.assertIn("REM", CLF.clasificar("El grupo REM atacó sitios de Argentina")["grupos"])
        self.assertNotIn("REM", CLF.clasificar("el sueño rem en argentina")["terminos_ciber"])

    def test_ciber_sin_argentina(self):
        self.assertFalse(CLF.clasificar("Ransomware attack hits hospital in Germany")["es_ataque"])


class TestSemaforo(unittest.TestCase):
    def test_verde_sin_detonantes(self):
        r = semaforo.calcular([ev("a", "2024-02-01", "ataque")], SEM, date(2024, 2, 1))
        self.assertEqual(r["actual"]["nivel"], "verde")
        self.assertEqual(r["alertas"][0]["nivel"], "info")

    def test_una_sola_fuente_no_alcanza(self):
        r = semaforo.calcular([ev("g1", "2024-02-06", "geo", "A"), ev("g2", "2024-02-06", "geo", "A")], SEM, date(2024, 2, 7))
        self.assertEqual(r["actual"]["nivel"], "verde")

    def test_amarillo_y_rojo(self):
        evs = [ev("g1", "2024-02-06", "geo", "A"), ev("g2", "2024-02-06", "geo", "B"), ev("a1", "2024-02-09", "ataque")]
        self.assertEqual(semaforo.calcular(evs, SEM, date(2024, 2, 8))["actual"]["nivel"], "amarillo")
        self.assertEqual(semaforo.calcular(evs, SEM, date(2024, 2, 10))["actual"]["nivel"], "rojo")
        self.assertEqual(semaforo.calcular(evs, SEM, date(2024, 2, 14))["actual"]["nivel"], "verde")

    def test_hecho_clave_basta_solo(self):
        r = semaforo.calcular([ev("h", "2024-04-11", "geo", origen="hecho_clave")], SEM, date(2024, 4, 12))
        self.assertEqual(r["actual"]["nivel"], "amarillo")

    def test_ventanas_se_fusionan(self):
        evs = [ev("h1", "2024-04-11", "geo", origen="hecho_clave"), ev("h2", "2024-04-13", "geo", origen="hecho_clave")]
        r = semaforo.calcular(evs, SEM, date(2024, 4, 19))
        self.assertEqual(len(r["periodos"]), 1)
        self.assertEqual(r["periodos"][0]["fin"], "2024-04-20")

    def test_ventana_configurable(self):
        evs = [ev("h", "2024-04-11", "geo", origen="hecho_clave")]
        r = semaforo.calcular(evs, {**SEM, "ventana_vigilancia_dias": 3}, date(2024, 4, 16))
        self.assertEqual(r["actual"]["nivel"], "verde")


if __name__ == "__main__":
    unittest.main()


class TestEvaluacion(unittest.TestCase):
    def test_razon_y_cobertura(self):
        from monitor import evaluacion
        evs = [ev("h", "2024-02-06", "geo", origen="hecho_clave"),
               {**ev("a1", "2024-02-09", "ataque", origen="incidente_csv"), "tipo_actor": "hacktivista"},
               {**ev("a2", "2024-03-20", "ataque", origen="incidente_csv"), "tipo_actor": "cibercriminal"}]
        r = evaluacion.evaluar(evs, SEM, [7], "2024-02-01", "2024-03-31")
        v = r["ventanas"][0]
        self.assertEqual(v["grupos"]["hacktivista"]["dentro"], 1)
        self.assertEqual(v["grupos"]["cibercriminal"]["dentro"], 0)
        self.assertEqual(v["grupos"]["hacktivista"]["anticipacion_mediana"], 3)
        self.assertAlmostEqual(v["cobertura_pct"], round(8 / 60 * 100, 1))
        self.assertGreater(v["grupos"]["hacktivista"]["razon"], 1)


class TestIncidentes(unittest.TestCase):
    def test_fecha_desconocida_queda_fuera(self):
        from monitor import historico
        con_fecha = {e["id"] for e in historico.cargar_incidentes()}
        sin_fecha = {e["id"] for e in historico.cargar_incidentes_sin_fecha()}
        self.assertFalse(con_fecha & sin_fecha)
        for e in historico.cargar_incidentes_sin_fecha():
            self.assertEqual(e["fecha_precision"], "desconocida")


class TestFiltroConfianza(unittest.TestCase):
    def test_excluye_confianza_baja(self):
        from monitor import evaluacion
        evs = [ev("h", "2024-02-06", "geo", origen="hecho_clave"),
               {**ev("a1", "2024-02-09", "ataque", origen="incidente_csv"), "tipo_actor": "hacktivista", "confianza": "baja"},
               {**ev("a2", "2024-02-10", "ataque", origen="incidente_csv"), "tipo_actor": "hacktivista", "confianza": "alta"}]
        todos = evaluacion.evaluar(evs, SEM, [7], "2024-02-01", "2024-03-31")
        filtrado = evaluacion.evaluar(evs, SEM, [7], "2024-02-01", "2024-03-31", confianzas={"media", "alta"})
        self.assertEqual(todos["ventanas"][0]["grupos"]["hacktivista"]["n"], 2)
        self.assertEqual(filtrado["ventanas"][0]["grupos"]["hacktivista"]["n"], 1)


class TestSoloVerificados(unittest.TestCase):
    def test_usa_solo_verificados(self):
        from monitor import evaluacion
        evs = [ev("h", "2024-02-06", "geo", origen="hecho_clave"),
               {**ev("a1", "2024-02-09", "ataque", origen="incidente_csv"), "tipo_actor": "hacktivista", "verificado": "si"},
               {**ev("a2", "2024-02-10", "ataque", origen="incidente_csv"), "tipo_actor": "hacktivista", "verificado": "no"}]
        r = evaluacion.evaluar(evs, SEM, [7], "2024-02-01", "2024-03-31", solo_verificados=True)
        self.assertEqual(r["ventanas"][0]["grupos"]["hacktivista"]["n"], 1)


class TestDeduplicacion(unittest.TestCase):
    def test_noticias_del_mismo_dia_cuentan_una_vez(self):
        from monitor import evaluacion
        evs = [ev("n1", "2024-04-17", "ataque", "A"), ev("n2", "2024-04-17", "ataque", "B"),
               ev("n3", "2024-04-18", "ataque", "A")]
        r = evaluacion.evaluar(evs, SEM, [7], "2024-04-01", "2024-04-30")
        self.assertEqual(r["ventanas"][0]["grupos"]["detectado_automaticamente"]["n"], 2)


class TestDescartados(unittest.TestCase):
    def test_descartados_fuera_del_calculo(self):
        from monitor import historico
        ids = {e["id"] for e in historico.cargar_incidentes() + historico.cargar_incidentes_sin_fecha()}
        for e in historico.cargar_incidentes_descartados():
            self.assertNotIn(e["id"], ids)
            self.assertEqual(e["decision"], "descartado")


# Página de ejemplo con la MISMA ESTRUCTURA que t.me/s/<canal> (textos inventados solo para la prueba).
PAGINA_TELEGRAM = """
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message js-widget_message" data-post="canal_prueba/10">
 <div class="tgme_widget_message_text js-message_text" dir="auto">Primera línea<br/>segunda &amp; línea</div>
 <a class="tgme_widget_message_date" href="https://t.me/canal_prueba/10"><time datetime="2024-02-22T10:00:00+00:00">10:00</time></a>
</div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message js-widget_message" data-post="canal_prueba/11">
 <div class="tgme_widget_message_reply"><div class="tgme_widget_message_text js-message_reply_text">texto citado</div></div>
 <div class="tgme_widget_message_text js-message_text" dir="auto">Respuesta propia</div>
 <time datetime="2024-02-23T11:00:00+00:00">11:00</time>
</div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message js-widget_message" data-post="canal_prueba/12">
 <a class="tgme_widget_message_photo_wrap"></a><time datetime="2024-02-24T12:00:00+00:00">12:00</time>
</div></div>
"""


class TestTelegram(unittest.TestCase):
    def test_lee_mensajes_de_la_vista_web(self):
        from monitor.fuentes import telegram
        msgs = telegram.parsear_pagina(PAGINA_TELEGRAM, {"nombre": "Prueba"})
        self.assertEqual([m["url"] for m in msgs], ["https://t.me/canal_prueba/10", "https://t.me/canal_prueba/11"])
        self.assertEqual(msgs[0]["titulo"], "Primera línea")
        self.assertIn("segunda & línea", msgs[0]["resumen"])
        self.assertEqual(msgs[1]["titulo"], "Respuesta propia")  # no toma el texto citado
        self.assertEqual(msgs[0]["origen"], "telegram")
        self.assertEqual(msgs[0]["fecha"][:10], "2024-02-22")

    def test_reclamo_con_dominio_ar(self):
        c = CLF.clasificar("Target down: ejemplo.gob.ar https://check-host.net/x", reclamo=True)
        self.assertTrue(c["es_ataque"])
        self.assertIn("ejemplo.gob.ar", c["dominios_ar"])

    def test_reclamo_con_bandera(self):
        self.assertTrue(CLF.clasificar("\U0001F1E6\U0001F1F7 down", reclamo=True)["es_ataque"])

    def test_proclama_sin_senal_no_es_ataque(self):
        c = CLF.clasificar("Argentina is an enemy of Palestine", reclamo=True)
        self.assertTrue(c["menciona_argentina"])
        self.assertFalse(c["es_ataque"])

    def test_noticia_comun_no_usa_regla_de_reclamo(self):
        self.assertFalse(CLF.clasificar("Target down: ejemplo.com.ar")["es_ataque"])
        self.assertTrue(CLF.clasificar("Target down: ejemplo.com.ar", reclamo=True)["es_ataque"])

    def test_reclamos_forman_grupo_aparte_en_evaluacion(self):
        from monitor import evaluacion
        eventos = [ev("hc", "2024-03-01", "geo", origen="hecho_clave"),
                   ev("t1", "2024-03-03", "ataque", origen="telegram"),
                   ev("t2", "2024-03-03", "ataque", origen="telegram"),
                   ev("n1", "2024-03-03", "ataque", origen="rss")]
        r = evaluacion.evaluar(eventos, SEM, [7], "2024-03-01", "2024-03-31")
        g = r["ventanas"][0]["grupos"]
        self.assertEqual(g["reclamo_telegram"]["n"], 1)  # mismo día: cuenta una vez
        self.assertEqual(g["detectado_automaticamente"]["n"], 1)


def geo(id_, dia, fuente, puntaje=2, origen="gdelt_historico"):
    return {**ev(id_, dia, "geo", fuente, origen), "puntaje_geo": puntaje, "titulo": f"Noticia {id_}", "url": f"https://x/{id_}"}


class TestModoCurado(unittest.TestCase):
    def test_noticias_no_abren_ventana(self):
        evs = [geo("g1", "2024-02-06", "A"), geo("g2", "2024-02-06", "B"), ev("a1", "2024-02-09", "ataque")]
        self.assertEqual(semaforo.calcular(evs, SEM_CURADO, date(2024, 2, 10))["actual"]["nivel"], "verde")
        self.assertEqual(semaforo.calcular(evs, SEM, date(2024, 2, 10))["actual"]["nivel"], "rojo")

    def test_hecho_clave_abre_ventana(self):
        evs = [ev("h", "2024-02-06", "geo", origen="hecho_clave"), ev("a1", "2024-02-09", "ataque")]
        self.assertEqual(semaforo.calcular(evs, SEM_CURADO, date(2024, 2, 10))["actual"]["nivel"], "rojo")

    def test_curado_es_el_modo_por_defecto(self):
        sin_modo = {"ventana_vigilancia_dias": 7, "min_fuentes_distintas_por_dia": 2}
        evs = [geo("g1", "2024-02-06", "A"), geo("g2", "2024-02-06", "B")]
        self.assertEqual(semaforo.calcular(evs, sin_modo, date(2024, 2, 7))["actual"]["nivel"], "verde")
        self.assertEqual(CFG["semaforo"]["modo_detonantes"], "curado")
        self.assertEqual(CFG["semaforo"]["ventana_vigilancia_dias"], 21)

    def test_modo_desconocido_da_error(self):
        with self.assertRaises(ValueError):
            semaforo.dias_detonantes([], 2, "otro")


class TestCandidatos(unittest.TestCase):
    EVS = [geo("g1", "2024-05-20", "A", 2), geo("g2", "2024-05-20", "B", 4), geo("g3", "2024-05-20", "B", 3),
           geo("g4", "2024-05-21", "A", 5),  # una sola fuente: no es candidato
           ev("h", "2024-05-22", "geo", origen="hecho_clave")]

    def test_un_candidato_por_dia(self):
        c = semaforo.candidatos_por_dia(self.EVS, 2)
        self.assertEqual(len(c), 1)
        self.assertEqual((c[0]["dia"], c[0]["url"], c[0]["puntaje"]), ("2024-05-20", "https://x/g2", 4))
        self.assertEqual((c[0]["n_noticias"], c[0]["n_fuentes"]), (3, 2))

    def test_envio_al_csv_sin_duplicar(self):
        import csv
        import tempfile
        from pathlib import Path
        from monitor import historico
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "candidatos.csv"
            ruta.write_text("id,fecha,titulo,fuente_url,estado_revision\n"
                            "CHC-01,2024-01-01,Manual,https://manual,cargado (sin verificar)\n", encoding="utf-8")
            c = semaforo.candidatos_por_dia(self.EVS, 2)
            self.assertEqual(historico.agregar_candidatos_hechos_clave(c, ruta), 1)
            self.assertEqual(historico.agregar_candidatos_hechos_clave(c, ruta), 0)  # segunda vez: nada nuevo
            filas = list(csv.DictReader(open(ruta, encoding="utf-8")))
            self.assertEqual([f["id"] for f in filas], ["CHC-01", "CHC-A-20240520"])
            self.assertEqual(filas[0]["titulo"], "Manual")  # la fila manual no se toca
            self.assertEqual((filas[1]["puntaje"], filas[1]["n_noticias"], filas[1]["n_fuentes"]), ("4", "3", "2"))
            # Si el histórico suma noticias ese día, se actualizan los conteos del candidato pendiente
            mas = c[0] | {"n_noticias": 5}
            self.assertEqual(historico.agregar_candidatos_hechos_clave([mas], ruta), 0)
            self.assertEqual(list(csv.DictReader(open(ruta, encoding="utf-8")))[1]["n_noticias"], "5")
            # Un día que ya tiene un hecho clave cargado no se propone
            self.assertEqual(historico.agregar_candidatos_hechos_clave([c[0] | {"dia": "2024-02-06", "url": "https://y"}], ruta), 0)
            # Una noticia que ya está en la lista no se repite con otro id
            otra = c[0] | {"dia": "2024-03-01"}
            self.assertEqual(historico.agregar_candidatos_hechos_clave([otra], ruta), 0)


class TestFocoLulzSec(unittest.TestCase):
    ALC = CFG["alcance"]

    def test_que_eventos_estan_en_foco(self):
        from monitor.procesar import en_foco
        inc = lambda g: {"carril": "ataque", "origen": "incidente_csv", "grupos": [g], "titulo": f"{g} → x"}
        self.assertTrue(en_foco(inc("LulzSec Muslims"), self.ALC))
        self.assertFalse(en_foco(inc("RansomHub"), self.ALC))
        self.assertTrue(en_foco({"carril": "ataque", "origen": "telegram", "titulo": "x"}, self.ALC))
        self.assertTrue(en_foco({"carril": "ataque", "origen": "rss", "titulo": "LulzSec hackeó un sitio argentino"}, self.ALC))
        self.assertFalse(en_foco({"carril": "ataque", "origen": "rss", "titulo": "Ransomware en un municipio argentino"}, self.ALC))
        self.assertTrue(en_foco({"carril": "geo", "origen": "rss", "titulo": "Milei en Israel"}, self.ALC))

    def test_lulzsec_y_comparacion_en_evaluacion(self):
        from monitor import evaluacion
        evs = [ev("h", "2024-03-01", "geo", origen="hecho_clave"),
               {**ev("l", "2024-03-05", "ataque", origen="incidente_csv"), "tipo_actor": "hacktivista", "en_foco": True},
               {**ev("c", "2024-03-20", "ataque", origen="incidente_csv"), "tipo_actor": "cibercriminal", "en_foco": False}]
        r = evaluacion.evaluar(evs, SEM_CURADO, [7], "2024-03-01", "2024-03-31")["ventanas"][0]["grupos"]
        self.assertEqual((r["lulzsec"]["n"], r["lulzsec"]["dentro"]), (1, 1))
        self.assertEqual((r["cibercriminal"]["n"], r["cibercriminal"]["dentro"]), (1, 0))
        self.assertEqual(r["hacktivista"]["n"], 0)

    def test_comparar_modos_por_tramo(self):
        from monitor import evaluacion
        evs = [geo("g1", "2024-02-06", "A"), geo("g2", "2024-02-06", "B"),
               {**ev("l", "2024-02-09", "ataque", origen="incidente_csv"), "tipo_actor": "hacktivista", "en_foco": True}]
        tramos = [{"clave": "cal", "nombre": "Calibración", "inicio": "2024-01-01", "fin": "2024-06-30"},
                  {"clave": "val", "nombre": "Validación", "inicio": "2024-07-01", "fin": "hoy"}]
        r = evaluacion.comparar_modos(evs, SEM, [7], tramos, "2024-12-31")
        self.assertEqual(set(r), {"automatico", "curado"})
        self.assertEqual(r["automatico"]["cal"]["ventanas"][0]["grupos"]["lulzsec"]["dentro"], 1)
        self.assertEqual(r["curado"]["cal"]["ventanas"][0]["grupos"]["lulzsec"]["dentro"], 0)
        self.assertEqual(r["curado"]["val"]["fin"], "2024-12-31")  # "hoy" se reemplaza
        self.assertEqual(r["automatico"]["val"]["ventanas"][0]["grupos"]["lulzsec"]["n"], 0)
