import datetime
import json

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from casos.models import Asunto, Delito, Interviniente
from catalogos.models import Municipio, Sede, UnidadOrigen
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

        self.stdout.write(
            self.style.SUCCESS(
                "Datos de demostración listos. Usuarios y contraseñas: datos_demo/usuarios_demo.json"
            )
        )
