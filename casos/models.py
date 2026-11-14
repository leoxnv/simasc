"""Modelo de datos de los asuntos MASC.

Entre paréntesis va la clave de la variable en el diccionario de datos
original (M1, A2, D5…), que es la que se usará en el archivo de intercambio.
"""

import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, Exists, Max, OuterRef, Value, When
from django.utils import timezone
from simple_history.models import HistoricalRecords

from catalogos.models import Facilitador, Municipio, Sede, UnidadOrigen

# Plazo del art. 14 de la LNMASCMP para invitar al requerido.
DIAS_HABILES_PARA_INVITAR = 5


class SiNo(models.TextChoices):
    SI = "si", "Sí"
    NO = "no", "No"


def dias_habiles_desde(fecha):
    """Días de lunes a viernes transcurridos desde `fecha` hasta hoy."""
    hoy = timezone.localdate()
    dias = 0
    while fecha < hoy:
        fecha += datetime.timedelta(days=1)
        dias += fecha.weekday() < 5
    return dias


class AsuntoQuerySet(models.QuerySet):
    def con_estatus(self):
        """Agrega `estatus_codigo`: en qué punto del procedimiento va cada asunto.

        El orden importa: gana la primera condición que se cumple.
        """
        E = Asunto.Estatus
        C = Acuerdo.Cumplimiento
        return self.annotate(
            estatus_codigo=Case(
                When(cancelado=True, then=Value(E.CANCELADO.value)),
                When(admisible=SiNo.NO, then=Value(E.NO_ADMITIDO.value)),
                When(acuerdo__estado_cumplimiento=C.CUMPLIDO, then=Value(E.ACUERDO_CUMPLIDO.value)),
                When(acuerdo__estado_cumplimiento=C.PARCIAL, then=Value(E.ACUERDO_PARCIAL.value)),
                When(
                    acuerdo__estado_cumplimiento=C.INCUMPLIDO,
                    then=Value(E.ACUERDO_INCUMPLIDO.value),
                ),
                When(acuerdo__isnull=False, then=Value(E.ACUERDO_EN_CUMPLIMIENTO.value)),
                When(fecha_conclusion__isnull=False, then=Value(E.SIN_ACUERDO.value)),
                When(
                    Exists(Sesion.objects.filter(asunto=OuterRef("pk"))),
                    then=Value(E.EN_SESIONES.value),
                ),
                When(
                    Exists(Invitacion.objects.filter(asunto=OuterRef("pk"))),
                    then=Value(E.EN_INVITACION.value),
                ),
                default=Value(E.REGISTRADO.value),
            )
        )


class Asunto(models.Model):
    class Sistema(models.TextChoices):
        ADULTOS = "adultos", "Adultos"
        ADOLESCENTES = "adolescentes", "Justicia para adolescentes"

    class Estatus(models.TextChoices):
        """Se calcula, no se captura (base de datos que pide el art. 43)."""

        REGISTRADO = "registrado", "Registrado"
        NO_ADMITIDO = "no_admitido", "No admitido"
        EN_INVITACION = "en_invitacion", "En invitación"
        EN_SESIONES = "en_sesiones", "En sesiones"
        SIN_ACUERDO = "sin_acuerdo", "Concluido sin acuerdo"
        ACUERDO_EN_CUMPLIMIENTO = "acuerdo_en_cumplimiento", "Acuerdo en cumplimiento"
        ACUERDO_CUMPLIDO = "acuerdo_cumplido", "Acuerdo cumplido"
        ACUERDO_PARCIAL = "acuerdo_parcial", "Acuerdo cumplido parcialmente"
        ACUERDO_INCUMPLIDO = "acuerdo_incumplido", "Acuerdo incumplido"
        CANCELADO = "cancelado", "Cancelado"

    class FormaSolicitud(models.TextChoices):
        VERBAL = "verbal", "Verbal"
        ESCRITA = "escrita", "Escrita"

    class EtapaProcesal(models.TextChoices):
        INICIAL = "inicial", "Investigación inicial"
        COMPLEMENTARIA = "complementaria", "Investigación complementaria"
        INTERMEDIA = "intermedia", "Etapa intermedia"

    class Procedencia(models.TextChoices):
        QUERELLA = "querella", "Delito de querella o equivalente"
        CULPOSO = "culposo", "Delito culposo"
        PATRIMONIAL = "patrimonial", "Delito patrimonial sin violencia"

    class Mecanismo(models.TextChoices):
        MEDIACION = "mediacion", "Mediación"
        CONCILIACION = "conciliacion", "Conciliación"
        JUNTA_RESTAURATIVA = "junta", "Junta restaurativa"

    class CausaConclusion(models.TextChoices):
        VOLUNTAD = "voluntad", "Voluntad de alguno de los intervinientes"
        INASISTENCIA = "inasistencia", "Inasistencia injustificada en más de una ocasión"
        IRREDUCTIBLES = "irreductibles", "Posiciones irreductibles"
        COMPORTAMIENTO = "comportamiento", "Comportamiento irrespetuoso, agresivo o dilatorio"
        CONFIDENCIALIDAD = "confidencialidad", "Revelación de información confidencial"
        OTRA = "otra", "Otra causa prevista en la ley"

    class Derivacion(models.TextChoices):
        MINISTERIO_PUBLICO = "mp", "Ministerio Público"
        REMISION_JUDICIAL = "judicial", "Remisión judicial"
        OTRA = "otra", "Otra"

    class Admisible(models.TextChoices):
        SI = "si", "Sí"
        NO = "no", "No"

    folio = models.CharField(
        "número de identificación del asunto",  # M1
        max_length=50,
        unique=True,
        error_messages={"unique": "Ya existe un asunto con ese número de identificación."},
    )
    fecha_ingreso = models.DateField("fecha de ingreso")  # A2 (A1 es su año)
    # V1 se registra en dos niveles: aquí, el sistema por el que corre el
    # asunto; en cada interviniente, si la persona es adulta o adolescente.
    sistema = models.CharField("sistema de justicia", max_length=12, choices=Sistema.choices)
    unidad_origen = models.ForeignKey(  # A3
        UnidadOrigen,
        on_delete=models.PROTECT,
        verbose_name="fiscalía, agencia o unidad de origen",
    )
    municipio_origen = models.ForeignKey(  # A4
        Municipio, on_delete=models.PROTECT, verbose_name="municipio de origen"
    )
    # Muchos asuntos llegan antes de que se abra la carpeta, solo con NUC:
    # se exige al menos uno de los dos.
    carpeta_investigacion = models.CharField(  # A5
        "número de carpeta de investigación", max_length=80, blank=True
    )
    nuc = models.CharField("número único de caso (NUC)", max_length=80, blank=True)
    tipo_derivacion = models.CharField(  # A6
        "tipo de derivación", max_length=10, choices=Derivacion.choices
    )
    tipo_derivacion_otra = models.CharField(
        "especifique la derivación", max_length=200, blank=True
    )
    admisible = models.CharField(  # A7
        "admisibilidad", max_length=2, choices=Admisible.choices
    )

    sede = models.ForeignKey(
        Sede,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name="sede que lleva el asunto",
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asuntos_creados",
        verbose_name="capturó",
        editable=False,
    )
    creado_en = models.DateTimeField("fecha de captura", auto_now_add=True)
    actualizado_en = models.DateTimeField("última modificación", auto_now=True)

    # Un asunto nunca se borra: se cancela y queda el rastro.
    cancelado = models.BooleanField(default=False, editable=False)
    motivo_cancelacion = models.TextField("motivo de la cancelación", blank=True)

    # ---- Procedimiento (se llena conforme avanza; por eso todo es opcional) ----
    fecha_solicitud = models.DateField("fecha de la solicitud", null=True, blank=True)  # P1
    forma_solicitud = models.CharField(  # P2
        "forma de la solicitud", max_length=8, choices=FormaSolicitud.choices, blank=True
    )
    etapa_procesal = models.CharField(  # P3
        "etapa del proceso penal al derivar",
        max_length=15,
        choices=EtapaProcesal.choices,
        blank=True,
    )
    procedencia = models.CharField(  # P4
        "supuesto de procedencia", max_length=12, choices=Procedencia.choices, blank=True
    )
    motivo_no_admision = models.TextField("motivo de no admisión", blank=True)  # P5
    reconsideracion = models.CharField(  # P6
        "¿se pidió reconsideración?", max_length=2, choices=SiNo.choices, blank=True
    )
    hechos = models.TextField(  # P7
        "breve relación de los hechos",
        blank=True,
        help_text="Lo que motivó el asunto. No registres aquí lo dicho en las sesiones.",
    )
    mecanismo = models.CharField(  # P8
        "mecanismo aplicado", max_length=12, choices=Mecanismo.choices, blank=True
    )
    mecanismo_sustituto = models.CharField(  # P9
        "mecanismo que lo sustituyó",
        max_length=12,
        choices=Mecanismo.choices,
        blank=True,
        help_text="Solo si durante el procedimiento se cambió de mecanismo.",
    )
    facilitador = models.ForeignKey(  # P10
        Facilitador,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name="facilitador asignado",
    )
    fecha_aceptacion = models.DateField(  # P11
        "fecha en que aceptaron sujetarse al mecanismo", null=True, blank=True
    )

    # ---- Conclusión anticipada, sin acuerdo (art. 32) ----
    fecha_conclusion = models.DateField("fecha de conclusión", null=True, blank=True)  # C1
    causa_conclusion = models.CharField(  # C3
        "causa de la conclusión", max_length=20, choices=CausaConclusion.choices, blank=True
    )
    causa_conclusion_otra = models.CharField("especifique la causa", max_length=200, blank=True)

    objects = AsuntoQuerySet.as_manager()
    history = HistoricalRecords()

    class Meta:
        verbose_name = "asunto"
        verbose_name_plural = "asuntos"
        ordering = ["-fecha_ingreso", "-id"]

    def __str__(self):
        return self.folio

    @property
    def anio_ingreso(self):  # A1
        return self.fecha_ingreso.year

    @property
    def estatus(self):
        codigo = getattr(self, "estatus_codigo", None)
        if codigo is None:
            codigo = (
                Asunto.objects.con_estatus()
                .values_list("estatus_codigo", flat=True)
                .get(pk=self.pk)
            )
        return self.Estatus(codigo)

    @property
    def acuerdo_o_nada(self):
        return getattr(self, "acuerdo", None)

    @property
    def admite_seguimiento(self):
        """Solo un asunto admitido y sin cancelar tiene invitaciones, sesiones y acuerdo."""
        return self.admisible == SiNo.SI and not self.cancelado

    @property
    def mecanismo_abierto(self):
        """Falso cuando ya concluyó sin acuerdo: no caben más sesiones ni acuerdo."""
        return self.admite_seguimiento and self.fecha_conclusion is None

    @property
    def dias_sin_invitar(self):
        """Días hábiles desde el ingreso si ya venció el plazo para invitar; si no, 0."""
        if self.estatus != self.Estatus.REGISTRADO:
            return 0
        dias = dias_habiles_desde(self.fecha_ingreso)
        return dias if dias > DIAS_HABILES_PARA_INVITAR else 0

    def clean(self):
        errores = {}
        if not self.carpeta_investigacion.strip() and not self.nuc.strip():
            errores["carpeta_investigacion"] = (
                "Captura la carpeta de investigación o el NUC (al menos uno)."
            )
        if self.tipo_derivacion == self.Derivacion.OTRA:
            if not self.tipo_derivacion_otra.strip():
                errores["tipo_derivacion_otra"] = "Especifica cuál es la otra derivación."
        else:
            self.tipo_derivacion_otra = ""
        if errores:
            raise ValidationError(errores)

    @classmethod
    def visibles_para(cls, usuario):
        """Capturista: los suyos y los de su sede. Supervisor y administrador: todos."""
        if usuario.puede_supervisar:
            return cls.objects.all()
        propios = models.Q(creado_por=usuario)
        if usuario.sede_id:
            propios |= models.Q(sede_id=usuario.sede_id)
        return cls.objects.filter(propios)

    def editable_por(self, usuario):
        """Quien puede verlo puede continuarlo, salvo que esté cancelado."""
        if self.cancelado:
            return False
        return (
            usuario.puede_supervisar
            or self.creado_por_id == usuario.id
            or (usuario.sede_id is not None and self.sede_id == usuario.sede_id)
        )


class Interviniente(models.Model):
    """Persona que participa en el asunto (art. 3 de la Ley Nacional de MASC penal)."""

    class Tipo(models.TextChoices):
        VICTIMA = "victima", "Víctima u ofendido"
        IMPUTADO = "imputado", "Imputado"

    class Calidad(models.TextChoices):
        SOLICITANTE = "solicitante", "Solicitante"
        REQUERIDO = "requerido", "Requerido"

    class TipoPersona(models.TextChoices):
        FISICA = "fisica", "Persona física"
        MORAL = "moral", "Persona moral"

    class Sexo(models.TextChoices):
        MUJER = "mujer", "Mujer"
        HOMBRE = "hombre", "Hombre"
        NO_BINARIO = "no_binario", "No binario"
        NO_ESPECIFICADO = "no_especificado", "No especificado"

    class GrupoEtario(models.TextChoices):
        ADULTO = "adulto", "Adulto"
        ADOLESCENTE = "adolescente", "Adolescente"

    # Campos que identifican a una persona: nunca salen en el archivo anonimizado.
    DATOS_PERSONALES = (
        "nombre",
        "primer_apellido",
        "segundo_apellido",
        "telefono",
        "correo",
    )

    asunto = models.ForeignKey(Asunto, on_delete=models.CASCADE, related_name="intervinientes")
    tipo = models.CharField("participa como", max_length=10, choices=Tipo.choices)
    numero = models.PositiveSmallIntegerField("número", editable=False)  # M2 en víctimas
    calidad = models.CharField(
        "calidad en el mecanismo", max_length=12, choices=Calidad.choices, blank=True
    )
    tipo_persona = models.CharField(
        "tipo de persona", max_length=6, choices=TipoPersona.choices, default=TipoPersona.FISICA
    )
    nombre = models.CharField("nombre(s) o razón social", max_length=200)
    primer_apellido = models.CharField("primer apellido", max_length=100, blank=True)
    segundo_apellido = models.CharField("segundo apellido", max_length=100, blank=True)
    sexo = models.CharField(max_length=16, choices=Sexo.choices, blank=True)
    edad = models.PositiveSmallIntegerField("edad", null=True, blank=True)
    grupo_etario = models.CharField(  # V1
        "adulto o adolescente", max_length=12, choices=GrupoEtario.choices, blank=True
    )
    telefono = models.CharField("teléfono", max_length=30, blank=True)
    correo = models.EmailField("correo electrónico", blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "interviniente"
        verbose_name_plural = "intervinientes"
        ordering = ["tipo", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["asunto", "tipo", "numero"], name="numero_unico_por_asunto_y_tipo"
            )
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.numero}: {self.nombre_completo}"

    @property
    def nombre_completo(self):
        return " ".join(
            p for p in (self.nombre, self.primer_apellido, self.segundo_apellido) if p
        )

    def clean(self):
        if self.tipo_persona == self.TipoPersona.FISICA:
            faltan = {
                campo: "Obligatorio para personas físicas."
                for campo in ("primer_apellido", "sexo", "grupo_etario")
                if not getattr(self, campo)
            }
            if faltan:
                raise ValidationError(faltan)
        else:
            # Una empresa o institución no tiene apellidos, sexo ni edad.
            self.primer_apellido = self.segundo_apellido = ""
            self.sexo = self.grupo_etario = ""
            self.edad = None

    def save(self, *args, **kwargs):
        if self.numero is None:
            ultimo = Interviniente.objects.filter(asunto=self.asunto, tipo=self.tipo).aggregate(
                m=Max("numero")
            )["m"]
            self.numero = (ultimo or 0) + 1
        super().save(*args, **kwargs)


class Delito(models.Model):
    class Gravedad(models.TextChoices):
        GRAVE = "grave", "Grave"
        NO_GRAVE = "no_grave", "No grave"

    class BienJuridico(models.TextChoices):
        VIDA_SALUD = "vida_salud", "De peligro contra la vida y la salud personal"
        LIBERTAD_SEXUAL = (
            "libertad_sexual",
            "Que atentan contra la libertad y la seguridad sexual",
        )
        DESARROLLO_PERSONALIDAD = (
            "desarrollo_personalidad",
            "Que atentan contra el libre desarrollo de la personalidad",
        )
        PAZ_SEGURIDAD = "paz_seguridad", "Contra la paz y la seguridad personal"
        HONOR = "honor", "Contra el honor"
        VIOLENCIA_POLITICA = "violencia_politica", "De violencia política"
        FAMILIA = "familia", "Contra la familia"
        VIAS_COMUNICACION = "vias_comunicacion", "Contra las vías de comunicación"
        PATRIMONIO = "patrimonio", "Contra el patrimonio"

    class FormaComision(models.TextChoices):
        DOLOSO = "doloso", "Doloso"
        CULPOSO = "culposo", "Culposo"

    class FormaAccion(models.TextChoices):
        CON_VIOLENCIA = "con_violencia", "Con violencia"
        SIN_VIOLENCIA = "sin_violencia", "Sin violencia"

    class Modalidad(models.TextChoices):
        SIMPLE = "simple", "Simple"
        ATENUADO = "atenuado", "Atenuado"
        AGRAVADO = "agravado", "Agravado"
        CALIFICADO = "calificado", "Calificado"
        AGRAVADO_CALIFICADO = "agravado_calificado", "Agravado-calificado"

    class Instrumento(models.TextChoices):
        ARMA_FUEGO = "arma_fuego", "Arma de fuego"
        ARMA_BLANCA = "arma_blanca", "Arma blanca"
        PARTE_CUERPO = "parte_cuerpo", "Parte del cuerpo"
        VEHICULO = "vehiculo", "Vehículo"
        MEDIO_ELECTRONICO = "medio_electronico", "Medio electrónico o informático"
        DOS_O_MAS = "dos_o_mas", "Dos o más instrumentos"
        NINGUNO = "ninguno", "Ningún instrumento"
        OTRO = "otro", "Otro instrumento"

    class Ambito(models.TextChoices):
        FAMILIAR = "familiar", "Familiar"
        COMUNITARIO = "comunitario", "Comunitario"
        ESCOLAR = "escolar", "Escolar"
        LABORAL = "laboral", "Laboral"
        OTRO = "otro", "Otro"

    INSTRUMENTOS_A_ESPECIFICAR = (Instrumento.DOS_O_MAS, Instrumento.OTRO)

    asunto = models.ForeignKey(Asunto, on_delete=models.CASCADE, related_name="delitos")
    victima = models.ForeignKey(
        Interviniente,
        on_delete=models.PROTECT,
        related_name="delitos_sufridos",
        verbose_name="víctima u ofendido",
        limit_choices_to={"tipo": Interviniente.Tipo.VICTIMA},
    )
    imputados = models.ManyToManyField(
        Interviniente,
        blank=True,
        related_name="delitos_atribuidos",
        verbose_name="imputados",
        limit_choices_to={"tipo": Interviniente.Tipo.IMPUTADO},
    )

    subtipo = models.CharField("subtipo del delito", max_length=200)  # D1
    articulo = models.CharField("artículo", max_length=50)  # D2
    sufijo = models.CharField(  # D3
        "sufijo", max_length=50, blank=True, help_text="Por ejemplo: Bis, Ter."
    )
    gravedad = models.CharField("gravedad", max_length=10, choices=Gravedad.choices)  # D4
    bien_juridico = models.CharField(  # D5
        "bien jurídico tutelado", max_length=30, choices=BienJuridico.choices
    )
    forma_comision = models.CharField(  # D6
        "forma de comisión", max_length=10, choices=FormaComision.choices
    )
    forma_accion = models.CharField(  # D7
        "forma de acción", max_length=15, choices=FormaAccion.choices
    )
    modalidad = models.CharField("modalidad", max_length=20, choices=Modalidad.choices)  # D8
    instrumento = models.CharField(  # D9
        "instrumento para la comisión", max_length=20, choices=Instrumento.choices
    )
    instrumento_especifique = models.CharField(
        "especifique el instrumento", max_length=200, blank=True
    )
    ambito = models.CharField("ámbito del hecho", max_length=15, choices=Ambito.choices)  # D10
    ambito_especifique = models.CharField("especifique el ámbito", max_length=200, blank=True)

    lugar_calle_numero = models.CharField("calle y número", max_length=200, blank=True)  # D11_1
    lugar_colonia = models.CharField("colonia", max_length=150, blank=True)  # D11_2
    lugar_municipio = models.ForeignKey(  # D11_3
        Municipio,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="municipio del hecho",
    )
    lugar_referencias = models.CharField("referencias", max_length=300, blank=True)  # D11_4
    lugar_otros_datos = models.CharField("otros datos", max_length=300, blank=True)  # D11_5

    history = HistoricalRecords(m2m_fields=[imputados])

    class Meta:
        verbose_name = "delito"
        verbose_name_plural = "delitos"
        ordering = ["id"]

    def __str__(self):
        return f"{self.subtipo} (art. {self.articulo}{' ' + self.sufijo if self.sufijo else ''})"

    def clean(self):
        errores = {}
        if self.instrumento in self.INSTRUMENTOS_A_ESPECIFICAR:
            if not self.instrumento_especifique.strip():
                errores["instrumento_especifique"] = "Especifica el instrumento."
        else:
            self.instrumento_especifique = ""
        if self.ambito == self.Ambito.OTRO:
            if not self.ambito_especifique.strip():
                errores["ambito_especifique"] = "Especifica el ámbito."
        else:
            self.ambito_especifique = ""
        if errores:
            raise ValidationError(errores)


# --------------------------------------------------------------------------
# Seguimiento del procedimiento
#
# Las sesiones son confidenciales (art. 4 fr. III) y de ellas solo se registra
# el acuerdo (art. 23): aquí se anota QUE ocurrieron, nunca lo que se dijo.
# Por eso las sesiones no tienen campo de notas.
# --------------------------------------------------------------------------


class Invitacion(models.Model):
    """Invitación a participar en el mecanismo (arts. 14 y 15)."""

    class Medio(models.TextChoices):
        PERSONAL = "personal", "Personal"
        TELEFONO = "telefono", "Teléfono"
        CORREO = "correo", "Correo electrónico"
        CORRESPONDENCIA = "correspondencia", "Correspondencia"
        OTRO = "otro", "Otro"

    class Resultado(models.TextChoices):
        SIN_RESPUESTA = "sin_respuesta", "Sin respuesta"
        ACEPTO = "acepto", "Aceptó"
        RECHAZO = "rechazo", "Rechazó"
        NO_LOCALIZADO = "no_localizado", "No localizado"

    asunto = models.ForeignKey(Asunto, on_delete=models.CASCADE, related_name="invitaciones")
    persona = models.ForeignKey(
        Interviniente,
        on_delete=models.PROTECT,
        related_name="invitaciones",
        verbose_name="persona invitada",
    )
    fecha = models.DateField("fecha de la invitación")  # I1
    medio = models.CharField("medio", max_length=16, choices=Medio.choices)  # I2
    medio_otro = models.CharField("especifique el medio", max_length=200, blank=True)
    resultado = models.CharField(  # I3
        "resultado", max_length=14, choices=Resultado.choices, default=Resultado.SIN_RESPUESTA
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "invitación"
        verbose_name_plural = "invitaciones"
        ordering = ["fecha", "id"]

    def __str__(self):
        return f"Invitación del {self.fecha:%d/%m/%Y} a {self.persona.nombre_completo}"

    def clean(self):
        if self.medio == self.Medio.OTRO:
            if not self.medio_otro.strip():
                raise ValidationError({"medio_otro": "Especifica el medio."})
        else:
            self.medio_otro = ""


class Sesion(models.Model):
    class Tipo(models.TextChoices):
        PRELIMINAR = "preliminar", "Preliminar"
        CONJUNTA = "conjunta", "Conjunta"
        REVISION = "revision", "De revisión del acuerdo"

    class Resultado(models.TextChoices):
        CONTINUA = "continua", "Continúa el mecanismo"
        ACUERDO = "acuerdo", "Se alcanzó acuerdo"
        SIN_ACUERDO = "sin_acuerdo", "Concluye sin acuerdo"

    asunto = models.ForeignKey(Asunto, on_delete=models.CASCADE, related_name="sesiones")
    fecha = models.DateField("fecha de la sesión")  # S1
    tipo = models.CharField("tipo de sesión", max_length=10, choices=Tipo.choices)  # S2
    asistentes = models.ManyToManyField(  # S3
        Interviniente, related_name="sesiones", verbose_name="asistentes"
    )
    interprete = models.CharField(  # S4
        "¿hubo intérprete?", max_length=2, choices=SiNo.choices, default=SiNo.NO
    )
    resultado = models.CharField("resultado", max_length=12, choices=Resultado.choices)  # S5

    history = HistoricalRecords(m2m_fields=[asistentes])

    class Meta:
        verbose_name = "sesión"
        verbose_name_plural = "sesiones"
        ordering = ["fecha", "id"]

    def __str__(self):
        return f"Sesión {self.get_tipo_display().lower()} del {self.fecha:%d/%m/%Y}"


def _sumar_anios(fecha, anios):
    try:
        return fecha.replace(year=fecha.year + anios)
    except ValueError:  # 29 de febrero
        return fecha.replace(year=fecha.year + anios, day=28)


class Acuerdo(models.Model):
    """Acuerdo reparatorio (arts. 33 a 35) y su cumplimiento (arts. 35 a 39)."""

    ANIOS_MAXIMOS = 3  # art. 33 fr. IV
    ANIOS_SIN_PLAZO = 1  # CNPP art. 189, cumplimiento diferido sin plazo

    class Alcance(models.TextChoices):
        TOTAL = "total", "Total"
        PARCIAL = "parcial", "Parcial"

    class FormaCumplimiento(models.TextChoices):
        INMEDIATO = "inmediato", "Inmediato"
        DIFERIDO = "diferido", "Diferido"

    class Autoridad(models.TextChoices):
        MINISTERIO_PUBLICO = "mp", "Ministerio Público"
        JUEZ = "juez", "Juez de control"

    class Cumplimiento(models.TextChoices):
        EN_CURSO = "en_curso", "En curso"
        CUMPLIDO = "cumplido", "Cumplido"
        PARCIAL = "parcial", "Cumplido parcialmente"
        INCUMPLIDO = "incumplido", "Incumplido"

    class Efecto(models.TextChoices):
        EXTINCION = "extincion", "Extinción de la acción penal"
        SOBRESEIMIENTO = "sobreseimiento", "Sobreseimiento"
        CONTINUACION = "continuacion", "Continuación del procedimiento penal"

    # Etiquetas de los campos de sí/no que en pantalla se eligen como casillas.
    OBLIGACIONES = {
        "obligacion_dar": "Dar",
        "obligacion_hacer": "Hacer",
        "obligacion_no_hacer": "No hacer",
    }
    REPARACIONES = {
        "reparacion_disculpa": "Reconocimiento de responsabilidad y disculpa",
        "reparacion_no_repeticion": "Compromiso de no repetición",
        "reparacion_restitucion": "Plan de restitución",
    }

    asunto = models.OneToOneField(Asunto, on_delete=models.CASCADE, related_name="acuerdo")
    fecha_celebracion = models.DateField("fecha de celebración")  # R1
    lugar_celebracion = models.CharField("lugar de celebración", max_length=200)  # R2
    alcance = models.CharField("alcance", max_length=8, choices=Alcance.choices)  # R3
    obligacion_dar = models.BooleanField("obligación de dar", default=False)  # R4
    obligacion_hacer = models.BooleanField("obligación de hacer", default=False)
    obligacion_no_hacer = models.BooleanField("obligación de no hacer", default=False)
    reparacion_disculpa = models.BooleanField(  # R5
        "reconocimiento de responsabilidad y disculpa", default=False
    )
    reparacion_no_repeticion = models.BooleanField("compromiso de no repetición", default=False)
    reparacion_restitucion = models.BooleanField("plan de restitución", default=False)
    monto_reparacion = models.DecimalField(  # R6
        "monto de la reparación económica",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="En pesos. Déjalo vacío si no hay reparación económica.",
    )
    forma_cumplimiento = models.CharField(  # R7
        "cumplimiento", max_length=10, choices=FormaCumplimiento.choices
    )
    fecha_limite = models.DateField(  # R8
        "fecha límite de cumplimiento",
        null=True,
        blank=True,
        help_text=(
            "Máximo 3 años desde la firma. Si es diferido y la dejas vacía, "
            "se fija a un año de la celebración."
        ),
    )
    fecha_validacion = models.DateField(  # R9
        "fecha de validación por licenciado en derecho del Órgano", null=True, blank=True
    )
    autoridad_aprueba = models.CharField(  # R10
        "autoridad que aprueba", max_length=4, choices=Autoridad.choices, blank=True
    )
    fecha_aprobacion = models.DateField("fecha de aprobación", null=True, blank=True)  # R11

    # ---- Cierre ----
    estado_cumplimiento = models.CharField(  # F1
        "estado de cumplimiento",
        max_length=10,
        choices=Cumplimiento.choices,
        default=Cumplimiento.EN_CURSO,
    )
    fecha_cierre = models.DateField(  # F2
        "fecha del cumplimiento o incumplimiento", null=True, blank=True
    )
    fecha_comunicacion = models.DateField(  # F3
        "fecha de comunicación al MP o al juez", null=True, blank=True
    )
    efecto = models.CharField("efecto", max_length=14, choices=Efecto.choices, blank=True)  # F4

    history = HistoricalRecords()

    class Meta:
        verbose_name = "acuerdo"
        verbose_name_plural = "acuerdos"

    def __str__(self):
        return f"Acuerdo del {self.fecha_celebracion:%d/%m/%Y}"

    def _elegidas(self, etiquetas):
        return [texto for campo, texto in etiquetas.items() if getattr(self, campo)]

    @property
    def obligaciones(self):
        return self._elegidas(self.OBLIGACIONES)

    @property
    def reparaciones(self):
        return self._elegidas(self.REPARACIONES)

    def clean(self):
        """Solo valida los datos de la celebración; el cierre lo valida su formulario."""
        if not self.fecha_celebracion:
            return
        if self.forma_cumplimiento == self.FormaCumplimiento.INMEDIATO:
            self.fecha_limite = None
            return
        if self.fecha_limite is None:
            self.fecha_limite = _sumar_anios(self.fecha_celebracion, self.ANIOS_SIN_PLAZO)
        elif self.fecha_limite < self.fecha_celebracion:
            raise ValidationError(
                {"fecha_limite": "No puede ser anterior a la celebración del acuerdo."}
            )
        elif self.fecha_limite > _sumar_anios(self.fecha_celebracion, self.ANIOS_MAXIMOS):
            raise ValidationError(
                {"fecha_limite": "El plazo no puede exceder de tres años desde la firma."}
            )


class AccionSeguimiento(models.Model):
    """Lo que hace el área de seguimiento para vigilar el cumplimiento (art. 36)."""

    class Accion(models.TextChoices):
        APERCIBIMIENTO = "apercibimiento", "Apercibimiento"
        VISITA = "visita", "Visita de verificación"
        LLAMADA = "llamada", "Llamada telefónica"
        RECEPCION = "recepcion", "Recepción o entrega de documentos, pagos, bienes u objetos"
        CITACION = "citacion", "Citación"
        COMUNICACION = "comunicacion", "Envío de correspondencia o comunicación"
        OTRA = "otra", "Otra medida"

    acuerdo = models.ForeignKey(Acuerdo, on_delete=models.CASCADE, related_name="acciones")
    fecha = models.DateField("fecha")  # G1
    accion = models.CharField("acción", max_length=16, choices=Accion.choices)  # G2
    accion_otra = models.CharField("especifique la medida", max_length=200, blank=True)
    resultado = models.CharField("resultado", max_length=300, blank=True)  # G3

    history = HistoricalRecords()

    class Meta:
        verbose_name = "acción de seguimiento"
        verbose_name_plural = "acciones de seguimiento"
        ordering = ["fecha", "id"]

    def __str__(self):
        return f"{self.get_accion_display()} del {self.fecha:%d/%m/%Y}"

    def clean(self):
        if self.accion == self.Accion.OTRA:
            if not self.accion_otra.strip():
                raise ValidationError({"accion_otra": "Especifica la medida."})
        else:
            self.accion_otra = ""
