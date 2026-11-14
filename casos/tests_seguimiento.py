import datetime

from django.urls import reverse

from .models import AccionSeguimiento, Acuerdo, Asunto, Interviniente, Invitacion, Sesion
from .tests import Base
from .views import PESTANAS_BITACORA

E = Asunto.Estatus


class BaseSeguimiento(Base):
    def setUp(self):
        self.victima = self.crear_victima()
        self.imputado = self.crear_victima(tipo=Interviniente.Tipo.IMPUTADO, nombre="Raúl")
        self.client.force_login(self.ana)

    def url(self, nombre, *args):
        return reverse(f"casos:{nombre}", args=[self.asunto.pk, *args])

    def estatus(self):
        return Asunto.objects.get(pk=self.asunto.pk).estatus

    def datos_invitacion(self, **cambios):
        datos = {
            "persona": self.imputado.pk,
            "fecha": "2026-03-03",
            "medio": "telefono",
            "medio_otro": "",
            "resultado": "sin_respuesta",
        }
        datos.update(cambios)
        return datos

    def datos_sesion(self, **cambios):
        datos = {
            "fecha": "2026-03-10",
            "tipo": "conjunta",
            "resultado": "continua",
            "interprete": "no",
            "asistentes": [self.victima.pk, self.imputado.pk],
        }
        datos.update(cambios)
        return datos

    def datos_acuerdo(self, **cambios):
        datos = {
            "fecha_celebracion": "2026-03-20",
            "lugar_celebracion": "Colima",
            "alcance": "total",
            "obligaciones": ["obligacion_dar"],
            "reparaciones": ["reparacion_restitucion"],
            "monto_reparacion": "1500.00",
            "forma_cumplimiento": "diferido",
            "fecha_limite": "2026-09-20",
            "fecha_validacion": "",
            "autoridad_aprueba": "",
            "fecha_aprobacion": "",
        }
        datos.update(cambios)
        return datos

    def crear_acuerdo(self, **campos):
        valores = dict(
            asunto=self.asunto,
            fecha_celebracion=datetime.date(2026, 3, 20),
            lugar_celebracion="Colima",
            alcance="total",
            obligacion_dar=True,
            forma_cumplimiento="inmediato",
        )
        valores.update(campos)
        return Acuerdo.objects.create(**valores)

    def no_admitir(self):
        Asunto.objects.filter(pk=self.asunto.pk).update(admisible="no")


class EstatusTests(BaseSeguimiento):
    def test_el_estatus_avanza_con_el_procedimiento(self):
        self.assertEqual(self.estatus(), E.REGISTRADO)
        self.client.post(self.url("invitacion_crear"), self.datos_invitacion())
        self.assertEqual(self.estatus(), E.EN_INVITACION)
        self.client.post(self.url("sesion_crear"), self.datos_sesion())
        self.assertEqual(self.estatus(), E.EN_SESIONES)
        self.client.post(self.url("acuerdo_crear"), self.datos_acuerdo())
        self.assertEqual(self.estatus(), E.ACUERDO_EN_CUMPLIMIENTO)
        self.client.post(
            self.url("cumplimiento"),
            {
                "estado_cumplimiento": "cumplido",
                "fecha_cierre": "2026-06-01",
                "fecha_comunicacion": "",
                "efecto": "extincion",
            },
        )
        self.assertEqual(self.estatus(), E.ACUERDO_CUMPLIDO)

    def test_no_admitido_y_cancelado_mandan_sobre_lo_demas(self):
        self.crear_acuerdo()
        self.no_admitir()
        self.assertEqual(self.estatus(), E.NO_ADMITIDO)
        Asunto.objects.filter(pk=self.asunto.pk).update(cancelado=True)
        self.assertEqual(self.estatus(), E.CANCELADO)

    def test_la_lista_filtra_por_estatus(self):
        self.crear_asunto("A-5", self.ana)
        self.crear_acuerdo()
        respuesta = self.client.get(
            reverse("casos:lista"), {"estatus": E.ACUERDO_EN_CUMPLIMIENTO.value}
        )
        self.assertContains(respuesta, ">A-1<")
        self.assertNotContains(respuesta, ">A-5<")

    def test_aviso_cuando_vence_el_plazo_para_invitar(self):
        Asunto.objects.filter(pk=self.asunto.pk).update(
            fecha_ingreso=datetime.date.today() - datetime.timedelta(days=30)
        )
        respuesta = self.client.get(reverse("casos:detalle", args=[self.asunto.pk]))
        self.assertContains(respuesta, "no hay invitación registrada")
        self.client.post(self.url("invitacion_crear"), self.datos_invitacion())
        respuesta = self.client.get(reverse("casos:detalle", args=[self.asunto.pk]))
        self.assertNotContains(respuesta, "no hay invitación registrada")


class ProcedimientoTests(BaseSeguimiento):
    def test_guarda_los_datos_del_procedimiento(self):
        self.client.post(
            reverse("casos:procedimiento", args=[self.asunto.pk]),
            {"mecanismo": "mediacion", "forma_solicitud": "verbal", "hechos": "Choque."},
        )
        self.asunto.refresh_from_db()
        self.assertEqual(
            (self.asunto.mecanismo, self.asunto.forma_solicitud, self.asunto.hechos),
            ("mediacion", "verbal", "Choque."),
        )

    def test_el_sustituto_debe_ser_otro_mecanismo(self):
        respuesta = self.client.post(
            reverse("casos:procedimiento", args=[self.asunto.pk]),
            {"mecanismo": "mediacion", "mecanismo_sustituto": "mediacion"},
        )
        self.assertContains(respuesta, "Debe ser distinto del mecanismo original")

    def test_no_admitido_pide_motivo_y_no_mecanismo(self):
        self.no_admitir()
        url = reverse("casos:procedimiento", args=[self.asunto.pk])
        campos = self.client.get(url).context["form"].fields
        self.assertIn("motivo_no_admision", campos)
        self.assertNotIn("mecanismo", campos)
        self.client.post(url, {"motivo_no_admision": "Delito grave", "mecanismo": "mediacion"})
        self.asunto.refresh_from_db()
        self.assertEqual(self.asunto.motivo_no_admision, "Delito grave")
        self.assertEqual(self.asunto.mecanismo, "")


class InvitacionYSesionTests(BaseSeguimiento):
    def test_no_se_invita_a_persona_de_otro_asunto(self):
        ajena = self.crear_victima(asunto=self.crear_asunto("A-7", self.ana))
        self.client.post(self.url("invitacion_crear"), self.datos_invitacion(persona=ajena.pk))
        self.assertFalse(Invitacion.objects.exists())

    def test_otro_medio_exige_especificar(self):
        respuesta = self.client.post(
            self.url("invitacion_crear"), self.datos_invitacion(medio="otro")
        )
        self.assertContains(respuesta, "Especifica el medio")

    def test_la_sesion_exige_asistentes_del_asunto(self):
        self.client.post(self.url("sesion_crear"), self.datos_sesion(asistentes=[]))
        ajena = self.crear_victima(asunto=self.crear_asunto("A-7", self.ana))
        self.client.post(self.url("sesion_crear"), self.datos_sesion(asistentes=[ajena.pk]))
        self.assertFalse(Sesion.objects.exists())

    def test_la_sesion_no_guarda_notas(self):
        # Confidencialidad (arts. 4 y 23): solo que ocurrió, quién asistió y cómo terminó.
        campos = {c.name for c in Sesion._meta.get_fields()}
        self.assertFalse(campos & {"notas", "observaciones", "contenido", "descripcion"})

    def test_asunto_no_admitido_no_lleva_seguimiento(self):
        self.no_admitir()
        for nombre, datos in (
            ("invitacion_crear", self.datos_invitacion()),
            ("sesion_crear", self.datos_sesion()),
            ("acuerdo_crear", self.datos_acuerdo()),
        ):
            respuesta = self.client.post(self.url(nombre), datos, follow=True)
            self.assertContains(respuesta, "no admitido o cancelado")
        self.assertFalse(Invitacion.objects.exists() or Sesion.objects.exists())
        self.assertFalse(Acuerdo.objects.exists())

    def test_capturista_de_otra_sede_no_entra(self):
        self.client.force_login(self.beto)
        for nombre in ("invitacion_crear", "sesion_crear", "acuerdo_crear"):
            self.assertEqual(self.client.get(self.url(nombre)).status_code, 404, nombre)


class AcuerdoTests(BaseSeguimiento):
    def test_guarda_obligaciones_y_reparacion(self):
        self.client.post(
            self.url("acuerdo_crear"),
            self.datos_acuerdo(obligaciones=["obligacion_dar", "obligacion_no_hacer"]),
        )
        acuerdo = Acuerdo.objects.get()
        self.assertEqual(acuerdo.obligaciones, ["Dar", "No hacer"])
        self.assertEqual(acuerdo.reparaciones, ["Plan de restitución"])
        self.assertEqual(acuerdo.history.first().history_user, self.ana)

    def test_exige_al_menos_una_obligacion(self):
        respuesta = self.client.post(
            self.url("acuerdo_crear"), self.datos_acuerdo(obligaciones=[])
        )
        self.assertContains(respuesta, "Marca al menos un tipo de obligación")

    def test_diferido_sin_plazo_queda_a_un_anio(self):
        self.client.post(self.url("acuerdo_crear"), self.datos_acuerdo(fecha_limite=""))
        self.assertEqual(Acuerdo.objects.get().fecha_limite, datetime.date(2027, 3, 20))

    def test_el_plazo_no_excede_tres_anios(self):
        respuesta = self.client.post(
            self.url("acuerdo_crear"), self.datos_acuerdo(fecha_limite="2029-03-21")
        )
        self.assertContains(respuesta, "no puede exceder de tres años")
        self.assertFalse(Acuerdo.objects.exists())

    def test_cumplimiento_inmediato_no_lleva_fecha_limite(self):
        self.client.post(
            self.url("acuerdo_crear"), self.datos_acuerdo(forma_cumplimiento="inmediato")
        )
        self.assertIsNone(Acuerdo.objects.get().fecha_limite)

    def test_un_solo_acuerdo_por_asunto(self):
        self.crear_acuerdo()
        respuesta = self.client.post(
            self.url("acuerdo_crear"), self.datos_acuerdo(), follow=True
        )
        self.assertContains(respuesta, "ya tiene un acuerdo registrado")
        self.assertEqual(Acuerdo.objects.count(), 1)

    def test_editar_el_acuerdo_no_toca_el_cumplimiento(self):
        self.crear_acuerdo(estado_cumplimiento="cumplido", fecha_cierre=datetime.date(2026, 5, 1))
        self.client.post(self.url("acuerdo_editar"), self.datos_acuerdo(alcance="parcial"))
        acuerdo = Acuerdo.objects.get()
        self.assertEqual((acuerdo.alcance, acuerdo.estado_cumplimiento), ("parcial", "cumplido"))

    def test_solo_supervision_quita_el_acuerdo(self):
        acuerdo = self.crear_acuerdo()
        AccionSeguimiento.objects.create(
            acuerdo=acuerdo, fecha=datetime.date(2026, 4, 1), accion="llamada"
        )
        self.assertEqual(self.client.post(self.url("acuerdo_eliminar")).status_code, 403)
        self.client.force_login(self.sup)
        self.client.post(self.url("acuerdo_eliminar"))
        self.assertFalse(Acuerdo.objects.exists() or AccionSeguimiento.objects.exists())


class CumplimientoTests(BaseSeguimiento):
    def setUp(self):
        super().setUp()
        self.acuerdo = self.crear_acuerdo()

    def cerrar(self, **datos):
        base = dict(estado_cumplimiento="", fecha_cierre="", fecha_comunicacion="", efecto="")
        base.update(datos)
        return self.client.post(self.url("cumplimiento"), base)

    def test_cerrar_exige_fecha(self):
        respuesta = self.cerrar(estado_cumplimiento="incumplido")
        self.assertContains(respuesta, "Indica la fecha del cumplimiento o incumplimiento")

    def test_incumplido_no_extingue_la_accion_penal(self):
        respuesta = self.cerrar(
            estado_cumplimiento="incumplido", fecha_cierre="2026-05-01", efecto="extincion"
        )
        self.assertContains(respuesta, "da lugar a continuar el procedimiento")
        self.assertEqual(self.estatus(), E.ACUERDO_EN_CUMPLIMIENTO)

    def test_incumplido_cambia_el_estatus(self):
        self.cerrar(
            estado_cumplimiento="incumplido",
            fecha_cierre="2026-05-01",
            fecha_comunicacion="2026-05-02",
            efecto="continuacion",
        )
        self.assertEqual(self.estatus(), E.ACUERDO_INCUMPLIDO)

    def test_volver_a_en_curso_limpia_el_cierre(self):
        Acuerdo.objects.filter(pk=self.acuerdo.pk).update(
            estado_cumplimiento="cumplido",
            fecha_cierre=datetime.date(2026, 5, 1),
            efecto="extincion",
        )
        self.cerrar(estado_cumplimiento="en_curso", fecha_cierre="2026-05-01", efecto="extincion")
        self.acuerdo.refresh_from_db()
        self.assertEqual((self.acuerdo.fecha_cierre, self.acuerdo.efecto), (None, ""))

    def test_acciones_de_seguimiento(self):
        self.client.post(
            self.url("accion_crear"),
            {"fecha": "2026-04-01", "accion": "llamada", "accion_otra": "", "resultado": "Pagó"},
        )
        accion = AccionSeguimiento.objects.get()
        self.assertEqual((accion.acuerdo, accion.resultado), (self.acuerdo, "Pagó"))
        respuesta = self.client.post(
            self.url("accion_crear"),
            {"fecha": "2026-04-02", "accion": "otra", "accion_otra": "", "resultado": ""},
        )
        self.assertContains(respuesta, "Especifica la medida")


class ConclusionTests(BaseSeguimiento):
    def concluir(self):
        return self.client.post(
            reverse("casos:conclusion", args=[self.asunto.pk]),
            {
                "fecha_conclusion": "2026-03-15",
                "causa_conclusion": "voluntad",
                "causa_conclusion_otra": "",
            },
        )

    def test_concluir_sin_acuerdo_cierra_el_mecanismo(self):
        self.concluir()
        self.assertEqual(self.estatus(), E.SIN_ACUERDO)
        for nombre, datos in (
            ("sesion_crear", self.datos_sesion()),
            ("acuerdo_crear", self.datos_acuerdo()),
        ):
            respuesta = self.client.post(self.url(nombre), datos, follow=True)
            self.assertContains(respuesta, "ya concluyó sin acuerdo")
        self.assertFalse(Sesion.objects.exists() or Acuerdo.objects.exists())

    def test_sin_acciones_no_hay_seguimiento_sin_acuerdo(self):
        respuesta = self.client.get(self.url("accion_crear"), follow=True)
        self.assertContains(respuesta, "Primero registra el acuerdo")

    def test_con_acuerdo_no_se_concluye_sin_acuerdo(self):
        self.crear_acuerdo()
        self.assertEqual(self.concluir().status_code, 403)

    def test_solo_supervision_reabre(self):
        self.concluir()
        url = reverse("casos:conclusion_quitar", args=[self.asunto.pk])
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.sup)
        self.client.post(url)
        self.assertEqual(self.estatus(), E.REGISTRADO)


class PantallasTests(BaseSeguimiento):
    def test_detalle_y_bitacora_con_todo_capturado(self):
        self.client.post(self.url("delito_crear"), self.datos_delito(self.victima))
        self.client.post(self.url("invitacion_crear"), self.datos_invitacion())
        self.client.post(self.url("sesion_crear"), self.datos_sesion())
        self.client.post(self.url("acuerdo_crear"), self.datos_acuerdo())
        self.client.post(
            self.url("accion_crear"),
            {"fecha": "2026-04-01", "accion": "visita", "accion_otra": "", "resultado": ""},
        )
        self.client.post(
            self.url("sesion_editar", Sesion.objects.get().pk),
            self.datos_sesion(tipo="revision"),
        )
        detalle = self.client.get(reverse("casos:detalle", args=[self.asunto.pk]))
        for texto in ("Teléfono", "De revisión del acuerdo", "Plan de restitución", "Visita"):
            self.assertContains(detalle, texto)
        self.client.force_login(self.admin)
        for clave, _ in PESTANAS_BITACORA:
            respuesta = self.client.get(reverse("casos:bitacora"), {"ver": clave})
            self.assertEqual(respuesta.status_code, 200, clave)
            if clave != "accesos":
                self.assertContains(respuesta, ">A-1<")
