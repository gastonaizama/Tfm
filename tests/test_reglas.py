"""Pruebas de las reglas (se ejecutan con: python -m unittest)."""
import unittest
from datetime import date

from monitor import semaforo
from monitor.clasificador import Clasificador
from monitor.config import cargar_config, cargar_mapeo_mitre

CFG = cargar_config()
CLF = Clasificador(CFG, cargar_mapeo_mitre())
SEM = {"ventana_vigilancia_dias": 7, "min_fuentes_distintas_por_dia": 2}


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
