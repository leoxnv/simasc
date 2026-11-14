import datetime
import json

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from casos.models import (
    AccionSeguimiento,
    Acuerdo,
    Asunto,
    Delito,
    Interviniente,
    Invitacion,
    Sesion,
)
from catalogos.models import Facilitador, Municipio, Sede, UnidadOrigen
from cuentas.models import Usuario


class Command(BaseCommand):
    help = "Carga usuarios, catálogos y un asunto de ejemplo para probar el sistema."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Los datos de demostración solo se cargan con SIMASC_DEBUG=1. "
                "Nunca en el servidor real de una fiscalía."
            )

        call_command("loaddata", "municipios_colima", verbosity=0)
        unidad, _ = UnidadOrigen.objects.get_or_create(
            nombre="Agencia del Ministerio Público (ejemplo)"
        )

        sede, _ = Sede.objects.get_or_create(nombre="Sede Colima (ejemplo)")

        ruta = settings.BASE_DIR / "datos_demo" / "usuarios_demo.json"
        usuarios = {}
        for datos in json.loads(ruta.read_text(encoding="utf-8")):
            clave = datos.pop("password")
            # Los capturistas de demostración comparten sede: cada uno ve
            # y puede continuar los asuntos del otro.
            datos["sede"] = sede if datos["rol"] == Usuario.Rol.CAPTURISTA else None
            usuario, _ = Usuario.objects.update_or_create(
                username=datos.pop("username"), defaults=datos
            )
            usuario.set_password(clave)
            usuario.save()
            usuarios[usuario.username] = usuario

        comunes = dict(
            fecha_ingreso=datetime.date.today(),
            sede=sede,
            unidad_origen=unidad,
            municipio_origen=Municipio.objects.get(nombre="Colima"),
            tipo_derivacion=Asunto.Derivacion.MINISTERIO_PUBLICO,
            admisible=Asunto.Admisible.SI,
        )
        # Un asunto que llegó solo con NUC, capturado por la segunda capturista.
        Asunto.objects.get_or_create(
            folio="DEMO-0002",
            defaults=dict(
                comunes,
                sistema=Asunto.Sistema.ADOLESCENTES,
                nuc="NUC/DEMO/0002/2026",
                creado_por=usuarios["capturista2.demo"],
            ),
        )

        if not Asunto.objects.filter(folio="DEMO-0001").exists():
            asunto = Asunto.objects.create(
                folio="DEMO-0001",
                sistema=Asunto.Sistema.ADULTOS,
                carpeta_investigacion="CI/DEMO/001/2026",
                creado_por=usuarios["capturista.demo"],
                **comunes,
            )
            victima = Interviniente.objects.create(
                asunto=asunto,
                tipo=Interviniente.Tipo.VICTIMA,
                calidad=Interviniente.Calidad.SOLICITANTE,
                nombre="Persona",
                primer_apellido="Ejemplo",
                segundo_apellido="Uno",
                sexo=Interviniente.Sexo.MUJER,
                edad=34,
                grupo_etario=Interviniente.GrupoEtario.ADULTO,
            )
            imputado = Interviniente.objects.create(
                asunto=asunto,
                tipo=Interviniente.Tipo.IMPUTADO,
                calidad=Interviniente.Calidad.REQUERIDO,
                nombre="Persona",
                primer_apellido="Ejemplo",
                segundo_apellido="Dos",
                sexo=Interviniente.Sexo.HOMBRE,
                edad=41,
                grupo_etario=Interviniente.GrupoEtario.ADULTO,
            )
            delito = Delito.objects.create(
                asunto=asunto,
                victima=victima,
                subtipo="Daño en propiedad ajena",
                articulo="200",
                gravedad=Delito.Gravedad.NO_GRAVE,
                bien_juridico=Delito.BienJuridico.PATRIMONIO,
                forma_comision=Delito.FormaComision.CULPOSO,
                forma_accion=Delito.FormaAccion.SIN_VIOLENCIA,
                modalidad=Delito.Modalidad.SIMPLE,
                instrumento=Delito.Instrumento.VEHICULO,
                ambito=Delito.Ambito.COMUNITARIO,
            )
            delito.imputados.add(imputado)

        self._seguimiento(Asunto.objects.get(folio="DEMO-0001"))

        self.stdout.write(
            self.style.SUCCESS(
                "Datos de demostración listos. Usuarios y contraseñas: datos_demo/usuarios_demo.json"
            )
        )

    def _seguimiento(self, asunto):
        """Lleva el asunto de ejemplo hasta un acuerdo en cumplimiento."""
        personas = asunto.intervinientes
        victima = personas.filter(tipo=Interviniente.Tipo.VICTIMA).first()
        imputado = personas.filter(tipo=Interviniente.Tipo.IMPUTADO).first()
        if asunto.invitaciones.exists() or not (victima and imputado):
            return

        hoy = datetime.date.today()
        asunto.fecha_solicitud = hoy
        asunto.forma_solicitud = Asunto.FormaSolicitud.VERBAL
        asunto.etapa_procesal = Asunto.EtapaProcesal.INICIAL
        asunto.procedencia = Asunto.Procedencia.CULPOSO
        asunto.mecanismo = Asunto.Mecanismo.MEDIACION
        asunto.facilitador, _ = Facilitador.objects.get_or_create(
            nombre="Facilitadora de ejemplo"
        )
        asunto.fecha_aceptacion = hoy
        asunto.hechos = "Choque entre dos vehículos con daños materiales."
        asunto.save()

        Invitacion.objects.create(
            asunto=asunto,
            persona=imputado,
            fecha=hoy,
            medio=Invitacion.Medio.TELEFONO,
            resultado=Invitacion.Resultado.ACEPTO,
        )
        sesion = Sesion.objects.create(
            asunto=asunto,
            fecha=hoy,
            tipo=Sesion.Tipo.CONJUNTA,
            resultado=Sesion.Resultado.ACUERDO,
        )
        sesion.asistentes.set([victima, imputado])
        acuerdo = Acuerdo.objects.create(
            asunto=asunto,
            fecha_celebracion=hoy,
            lugar_celebracion="Colima, Colima",
            alcance=Acuerdo.Alcance.TOTAL,
            obligacion_dar=True,
            reparacion_restitucion=True,
            monto_reparacion=8500,
            forma_cumplimiento=Acuerdo.FormaCumplimiento.DIFERIDO,
            fecha_limite=hoy + datetime.timedelta(days=90),
        )
        AccionSeguimiento.objects.create(
            acuerdo=acuerdo,
            fecha=hoy,
            accion=AccionSeguimiento.Accion.LLAMADA,
            resultado="Confirma que hará el primer pago en la fecha pactada.",
        )
