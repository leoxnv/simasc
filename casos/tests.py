import datetime

from django.test import TestCase
from django.urls import reverse

from catalogos.models import Municipio, Sede, UnidadOrigen
from cuentas.models import EventoAcceso, Usuario

from .models import Asunto, Delito, Interviniente


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.municipio = Municipio.objects.create(nombre="Colima")
        cls.unidad = UnidadOrigen.objects.create(nombre="Agencia 1")
        cls.sede = Sede.objects.create(nombre="Sede Centro")
        cls.otra_sede = Sede.objects.create(nombre="Sede Costa")
        # Ana y Caro comparten sede; Beto está en otra.
        cls.ana = Usuario.objects.create_user(
            "ana", password="x", rol=Usuario.Rol.CAPTURISTA, sede=cls.sede
        )
        cls.caro = Usuario.objects.create_user(
            "caro", password="x", rol=Usuario.Rol.CAPTURISTA, sede=cls.sede
        )
        cls.beto = Usuario.objects.create_user(
            "beto", password="x", rol=Usuario.Rol.CAPTURISTA, sede=cls.otra_sede
        )
        cls.sup = Usuario.objects.create_user("sup", password="x", rol=Usuario.Rol.SUPERVISOR)
        cls.admin = Usuario.objects.create_user(
            "admin", password="x", rol=Usuario.Rol.ADMINISTRADOR
        )
        cls.asunto = cls.crear_asunto("A-1", cls.ana)

    @classmethod
    def crear_asunto(cls, folio, usuario):
        return Asunto.objects.create(
            folio=folio,
            fecha_ingreso=datetime.date(2026, 3, 1),
            sistema=Asunto.Sistema.ADULTOS,
            sede=usuario.sede,
            unidad_origen=cls.unidad,
            municipio_origen=cls.municipio,
            carpeta_investigacion="CI-1",
            tipo_derivacion=Asunto.Derivacion.MINISTERIO_PUBLICO,
            admisible=Asunto.Admisible.SI,
            creado_por=usuario,
        )

    def datos_asunto(self, **cambios):
        datos = {
            "folio": "A-2",
            "fecha_ingreso": "2026-03-02",
            "sistema": "adultos",
            "unidad_origen": self.unidad.pk,
            "municipio_origen": self.municipio.pk,
            "carpeta_investigacion": "CI-2",
            "nuc": "",
            "tipo_derivacion": "mp",
            "tipo_derivacion_otra": "",
            "admisible": "si",
        }
        datos.update(cambios)
        return datos

    def datos_persona(self, **cambios):
        datos = {
            "tipo_persona": "fisica",
            "nombre": "Luz",
            "primer_apellido": "Pérez",
            "segundo_apellido": "",
            "sexo": "mujer",
            "edad": "30",
            "grupo_etario": "adulto",
            "calidad": "solicitante",
            "telefono": "",
            "correo": "",
        }
        datos.update(cambios)
        return datos

    def crear_victima(self, asunto=None, **campos):
        valores = dict(
            asunto=asunto or self.asunto,
            tipo=Interviniente.Tipo.VICTIMA,
            nombre="Luz",
            primer_apellido="Pérez",
            sexo="mujer",
            grupo_etario="adulto",
        )
        valores.update(campos)
        return Interviniente.objects.create(**valores)

    def datos_delito(self, victima, **cambios):
        datos = {
            "victima": victima.pk,
            "subtipo": "Robo simple",
            "articulo": "183",
            "sufijo": "",
            "gravedad": "no_grave",
            "bien_juridico": "patrimonio",
            "forma_comision": "doloso",
            "forma_accion": "sin_violencia",
            "modalidad": "simple",
            "instrumento": "ninguno",
            "instrumento_especifique": "",
            "ambito": "comunitario",
            "ambito_especifique": "",
        }
        datos.update(cambios)
        return datos


class AccesoTests(Base):
    def test_sin_sesion_manda_a_entrar(self):
        respuesta = self.client.get(reverse("casos:lista"))
        self.assertRedirects(respuesta, "/entrar/?next=/")

    def test_capturista_no_ve_asuntos_de_otra_sede(self):
        self.crear_asunto("B-1", self.beto)
        self.client.force_login(self.ana)
        respuesta = self.client.get(reverse("casos:lista"))
        self.assertContains(respuesta, "A-1")
        self.assertNotContains(respuesta, "B-1")

    def test_capturista_no_abre_asunto_de_otra_sede(self):
        self.client.force_login(self.beto)
        respuesta = self.client.get(reverse("casos:detalle", args=[self.asunto.pk]))
        self.assertEqual(respuesta.status_code, 404)

    def test_companera_de_sede_ve_y_continua_el_asunto(self):
        self.client.force_login(self.caro)
        self.assertContains(self.client.get(reverse("casos:lista")), "A-1")
        self.assertEqual(
            self.client.get(reverse("casos:editar", args=[self.asunto.pk])).status_code, 200
        )
        self.client.post(
            reverse("casos:persona_crear", args=[self.asunto.pk, "victima"]),
            self.datos_persona(),
        )
        self.assertEqual(self.asunto.intervinientes.count(), 1)
        self.assertEqual(Interviniente.history.first().history_user, self.caro)

    def test_sin_sede_cada_quien_ve_solo_lo_suyo(self):
        dana = Usuario.objects.create_user("dana", password="x")
        eli = Usuario.objects.create_user("eli", password="x")
        self.crear_asunto("D-1", dana)
        self.client.force_login(eli)
        self.assertNotContains(self.client.get(reverse("casos:lista")), "D-1")

    def test_supervisor_ve_y_edita_todo(self):
        self.client.force_login(self.sup)
        self.assertEqual(
            self.client.get(reverse("casos:detalle", args=[self.asunto.pk])).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("casos:editar", args=[self.asunto.pk])).status_code, 200
        )

    def test_bitacora_solo_administrador(self):
        self.client.force_login(self.sup)
        self.assertEqual(self.client.get(reverse("casos:bitacora")).status_code, 403)
        self.client.force_login(self.admin)
        for ver in ("asuntos", "personas", "delitos", "accesos"):
            respuesta = self.client.get(reverse("casos:bitacora"), {"ver": ver})
            self.assertEqual(respuesta.status_code, 200, ver)

    def test_solo_administrador_entra_al_panel(self):
        self.assertTrue(self.admin.is_staff and self.admin.is_superuser)
        self.assertFalse(self.sup.is_staff or self.sup.is_superuser)

    def test_bajar_de_rol_quita_el_panel(self):
        self.admin.rol = Usuario.Rol.SUPERVISOR
        self.admin.save()
        self.assertFalse(self.admin.is_staff or self.admin.is_superuser)

    def test_intento_fallido_queda_registrado(self):
        self.client.post(reverse("login"), {"username": "ana", "password": "mala"})
        self.assertTrue(
            EventoAcceso.objects.filter(tipo="fallido", nombre_usuario="ana").exists()
        )


class AsuntoTests(Base):
    def test_crear_asunto_guarda_quien_capturo(self):
        self.client.force_login(self.ana)
        respuesta = self.client.post(reverse("casos:crear"), self.datos_asunto())
        asunto = Asunto.objects.get(folio="A-2")
        self.assertRedirects(respuesta, reverse("casos:detalle", args=[asunto.pk]))
        self.assertEqual(asunto.creado_por, self.ana)
        self.assertEqual(asunto.sede, self.sede)
        self.assertEqual(asunto.history.first().history_user, self.ana)

    def test_capturista_no_puede_elegir_otra_sede(self):
        self.client.force_login(self.ana)
        self.client.post(reverse("casos:crear"), self.datos_asunto(sede=self.otra_sede.pk))
        self.assertEqual(Asunto.objects.get(folio="A-2").sede, self.sede)

    def test_supervisor_asigna_la_sede(self):
        self.client.force_login(self.sup)
        self.client.post(reverse("casos:crear"), self.datos_asunto(sede=self.otra_sede.pk))
        self.assertEqual(Asunto.objects.get(folio="A-2").sede, self.otra_sede)

    def test_basta_con_nuc_sin_carpeta(self):
        self.client.force_login(self.ana)
        self.client.post(
            reverse("casos:crear"), self.datos_asunto(carpeta_investigacion="", nuc="NUC-9")
        )
        self.assertEqual(Asunto.objects.get(folio="A-2").nuc, "NUC-9")

    def test_sin_carpeta_ni_nuc_se_rechaza(self):
        self.client.force_login(self.ana)
        respuesta = self.client.post(
            reverse("casos:crear"), self.datos_asunto(carpeta_investigacion="", nuc="")
        )
        self.assertContains(respuesta, "al menos uno")
        self.assertFalse(Asunto.objects.filter(folio="A-2").exists())

    def test_sistema_de_justicia_es_obligatorio(self):
        self.client.force_login(self.ana)
        self.client.post(reverse("casos:crear"), self.datos_asunto(sistema=""))
        self.assertFalse(Asunto.objects.filter(folio="A-2").exists())

    def test_busqueda_por_nuc(self):
        asunto = self.crear_asunto("A-8", self.ana)
        Asunto.objects.filter(pk=asunto.pk).update(nuc="NUC-555")
        self.client.force_login(self.ana)
        respuesta = self.client.get(reverse("casos:lista"), {"q": "nuc-555"})
        self.assertContains(respuesta, "A-8")
        self.assertNotContains(respuesta, "A-1<")

    def test_folio_repetido_se_rechaza(self):
        self.client.force_login(self.ana)
        respuesta = self.client.post(reverse("casos:crear"), self.datos_asunto(folio="A-1"))
        self.assertContains(respuesta, "Ya existe un asunto con ese número")

    def test_otra_derivacion_exige_especificar(self):
        self.client.force_login(self.ana)
        respuesta = self.client.post(
            reverse("casos:crear"), self.datos_asunto(tipo_derivacion="otra")
        )
        self.assertContains(respuesta, "Especifica cuál es la otra derivación")
        self.assertFalse(Asunto.objects.filter(folio="A-2").exists())

    def test_capturista_no_cancela(self):
        self.client.force_login(self.ana)
        respuesta = self.client.post(
            reverse("casos:cancelar", args=[self.asunto.pk]), {"motivo_cancelacion": "x"}
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_asunto_cancelado_queda_bloqueado(self):
        self.client.force_login(self.sup)
        self.client.post(
            reverse("casos:cancelar", args=[self.asunto.pk]),
            {"motivo_cancelacion": "Registro duplicado"},
        )
        self.asunto.refresh_from_db()
        self.assertTrue(self.asunto.cancelado)
        self.assertEqual(
            self.client.get(reverse("casos:editar", args=[self.asunto.pk])).status_code, 403
        )
        respuesta = self.client.post(
            reverse("casos:persona_crear", args=[self.asunto.pk, "victima"]),
            self.datos_persona(),
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_busqueda_por_nombre_de_persona(self):
        self.crear_victima(nombre="Griselda")
        self.crear_asunto("A-9", self.ana)
        self.client.force_login(self.ana)
        respuesta = self.client.get(reverse("casos:lista"), {"q": "grisel"})
        self.assertContains(respuesta, "A-1")
        self.assertNotContains(respuesta, "A-9")


class PersonaTests(Base):
    def test_numeracion_por_tipo(self):
        self.client.force_login(self.ana)
        url_victima = reverse("casos:persona_crear", args=[self.asunto.pk, "victima"])
        url_imputado = reverse("casos:persona_crear", args=[self.asunto.pk, "imputado"])
        self.client.post(url_victima, self.datos_persona())
        self.client.post(url_victima, self.datos_persona(nombre="Mar"))
        self.client.post(url_imputado, self.datos_persona(nombre="Raúl", sexo="hombre"))
        numeros = list(
            self.asunto.intervinientes.order_by("tipo", "numero").values_list("tipo", "numero")
        )
        self.assertEqual(numeros, [("imputado", 1), ("victima", 1), ("victima", 2)])

    def test_persona_fisica_exige_apellido_sexo_y_grupo(self):
        self.client.force_login(self.ana)
        respuesta = self.client.post(
            reverse("casos:persona_crear", args=[self.asunto.pk, "victima"]),
            self.datos_persona(primer_apellido="", sexo="", grupo_etario=""),
        )
        self.assertContains(respuesta, "Obligatorio para personas físicas", count=3)

    def test_persona_moral_no_exige_datos_de_persona_fisica(self):
        self.client.force_login(self.ana)
        self.client.post(
            reverse("casos:persona_crear", args=[self.asunto.pk, "victima"]),
            self.datos_persona(
                tipo_persona="moral",
                nombre="Tienda La Esquina SA de CV",
                primer_apellido="",
                sexo="",
                edad="",
                grupo_etario="",
            ),
        )
        self.assertTrue(self.asunto.intervinientes.filter(tipo_persona="moral").exists())

    def test_tipo_desconocido_no_existe(self):
        self.client.force_login(self.ana)
        respuesta = self.client.get(
            reverse("casos:persona_crear", args=[self.asunto.pk, "testigo"])
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_no_se_quita_la_victima_de_un_delito(self):
        victima = self.crear_victima()
        self.client.force_login(self.ana)
        self.client.post(
            reverse("casos:delito_crear", args=[self.asunto.pk]), self.datos_delito(victima)
        )
        respuesta = self.client.post(
            reverse("casos:persona_eliminar", args=[self.asunto.pk, victima.pk]), follow=True
        )
        self.assertContains(respuesta, "No se puede quitar")
        self.assertTrue(Interviniente.objects.filter(pk=victima.pk).exists())


class DelitoTests(Base):
    def test_sin_victima_no_hay_delito(self):
        self.client.force_login(self.ana)
        respuesta = self.client.get(
            reverse("casos:delito_crear", args=[self.asunto.pk]), follow=True
        )
        self.assertContains(respuesta, "agrega al menos una víctima")

    def test_crear_delito_con_imputado(self):
        victima = self.crear_victima()
        imputado = self.crear_victima(tipo=Interviniente.Tipo.IMPUTADO, nombre="Raúl")
        self.client.force_login(self.ana)
        self.client.post(
            reverse("casos:delito_crear", args=[self.asunto.pk]),
            self.datos_delito(victima, imputados=[imputado.pk]),
        )
        delito = Delito.objects.get()
        self.assertEqual(delito.victima, victima)
        self.assertEqual(list(delito.imputados.all()), [imputado])

    def test_otro_instrumento_exige_especificar(self):
        victima = self.crear_victima()
        self.client.force_login(self.ana)
        respuesta = self.client.post(
            reverse("casos:delito_crear", args=[self.asunto.pk]),
            self.datos_delito(victima, instrumento="otro"),
        )
        self.assertContains(respuesta, "Especifica el instrumento")
        self.assertFalse(Delito.objects.exists())

    def test_no_acepta_victima_de_otro_asunto(self):
        self.crear_victima()
        ajena = self.crear_victima(asunto=self.crear_asunto("A-7", self.ana))
        self.client.force_login(self.ana)
        self.client.post(
            reverse("casos:delito_crear", args=[self.asunto.pk]), self.datos_delito(ajena)
        )
        self.assertFalse(Delito.objects.exists())

    def test_quitar_delito_deja_rastro(self):
        victima = self.crear_victima()
        self.client.force_login(self.ana)
        self.client.post(
            reverse("casos:delito_crear", args=[self.asunto.pk]), self.datos_delito(victima)
        )
        delito = Delito.objects.get()
        self.client.post(reverse("casos:delito_eliminar", args=[self.asunto.pk, delito.pk]))
        self.assertFalse(Delito.objects.exists())
        ultimo = Delito.history.first()
        self.assertEqual((ultimo.history_type, ultimo.history_user), ("-", self.ana))
