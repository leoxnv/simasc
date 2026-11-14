from django import forms
from django.db.models import Q

from catalogos.models import Facilitador, Municipio, Sede, UnidadOrigen

from .models import (
    AccionSeguimiento,
    Acuerdo,
    Asunto,
    Delito,
    Interviniente,
    Invitacion,
    Sesion,
)


def _activos_o_actual(modelo, pk_actual):
    """Opciones activas del catálogo, más la ya elegida aunque esté desactivada."""
    return modelo.objects.filter(Q(activo=True) | Q(pk=pk_actual))


class FormularioBase(forms.ModelForm):
    """Base de todos los formularios de captura.

    - Fechas con el selector del navegador.
    - Opción vacía clara en las listas, y ausente en los botones de opción
      obligatorios.
    - `secciones` y `dependencias` describen cómo se dibuja el formulario en la
      plantilla genérica (`casos/formulario.html`).
    """

    VACIO = "Selecciona…"
    SIN_DATO = "Sin dato"

    # [(título, [campos])]. Sin definir: una sola sección con todos los campos.
    secciones = None
    # campo: (campo del que depende, [valores con los que se muestra])
    dependencias = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo, forms.DateField):
                campo.widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
            elif isinstance(campo, forms.ModelMultipleChoiceField):
                continue
            elif isinstance(campo, forms.ModelChoiceField):
                campo.empty_label = self.VACIO
            elif isinstance(campo, forms.ChoiceField) and not isinstance(
                campo, forms.MultipleChoiceField
            ):
                es_radio = isinstance(campo.widget, forms.RadioSelect)
                vacio = self.SIN_DATO if es_radio else self.VACIO
                campo.choices = [
                    (valor, vacio if valor == "" else etiqueta)
                    for valor, etiqueta in campo.choices
                    if not (valor == "" and es_radio and campo.required)
                ]

    @property
    def bloques(self):
        """Secciones con sus campos, listas para la plantilla genérica."""
        secciones = self.secciones or [("", list(self.fields))]
        bloques = []
        for titulo, nombres in secciones:
            celdas = [self._celda(n) for n in nombres if n in self.fields]
            if celdas:
                bloques.append({"titulo": titulo, "celdas": celdas})
        return bloques

    def _celda(self, nombre):
        campo = self[nombre]
        depende_de, valores = self.dependencias.get(nombre, ("", []))
        return {
            "campo": campo,
            "ancha": isinstance(
                campo.field.widget, (forms.Textarea, forms.CheckboxSelectMultiple)
            ),
            "depende_de": depende_de,
            "valores": ",".join(valores),
        }


# --------------------------------------------------------------------------
# Asunto, personas y delitos
# --------------------------------------------------------------------------


class AsuntoForm(FormularioBase):
    class Meta:
        model = Asunto
        fields = [
            "folio",
            "fecha_ingreso",
            "sistema",
            "carpeta_investigacion",
            "nuc",
            "sede",
            "unidad_origen",
            "municipio_origen",
            "tipo_derivacion",
            "tipo_derivacion_otra",
            "admisible",
        ]
        widgets = {"sistema": forms.RadioSelect, "admisible": forms.RadioSelect}

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario.puede_supervisar:
            # Solo supervisión decide (o cambia) qué sede lleva el asunto.
            self.fields["sede"].queryset = _activos_o_actual(Sede, self.instance.sede_id)
            if self.instance._state.adding:
                self.fields["sede"].initial = usuario.sede_id
        else:
            # El asunto de un capturista nace en la sede del capturista.
            del self.fields["sede"]
            if self.instance._state.adding:
                self.instance.sede = usuario.sede
        self.fields["unidad_origen"].queryset = _activos_o_actual(
            UnidadOrigen, self.instance.unidad_origen_id
        )
        self.fields["municipio_origen"].queryset = _activos_o_actual(
            Municipio, self.instance.municipio_origen_id
        )


class CancelarAsuntoForm(forms.ModelForm):
    class Meta:
        model = Asunto
        fields = ["motivo_cancelacion"]
        widgets = {"motivo_cancelacion": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["motivo_cancelacion"].required = True


class IntervinienteForm(FormularioBase):
    class Meta:
        model = Interviniente
        fields = [
            "tipo_persona",
            "nombre",
            "primer_apellido",
            "segundo_apellido",
            "sexo",
            "edad",
            "grupo_etario",
            "calidad",
            "telefono",
            "correo",
        ]
        widgets = {"tipo_persona": forms.RadioSelect}


class DelitoForm(FormularioBase):
    class Meta:
        model = Delito
        fields = [
            "victima",
            "imputados",
            "subtipo",
            "articulo",
            "sufijo",
            "gravedad",
            "bien_juridico",
            "forma_comision",
            "forma_accion",
            "modalidad",
            "instrumento",
            "instrumento_especifique",
            "ambito",
            "ambito_especifique",
            "lugar_calle_numero",
            "lugar_colonia",
            "lugar_municipio",
            "lugar_referencias",
            "lugar_otros_datos",
        ]
        widgets = {
            "imputados": forms.CheckboxSelectMultiple,
            "gravedad": forms.RadioSelect,
            "forma_comision": forms.RadioSelect,
            "forma_accion": forms.RadioSelect,
        }

    def __init__(self, *args, asunto, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo las personas de este asunto pueden ligarse al delito.
        personas = asunto.intervinientes.all()
        self.fields["victima"].queryset = personas.filter(tipo=Interviniente.Tipo.VICTIMA)
        self.fields["imputados"].queryset = personas.filter(tipo=Interviniente.Tipo.IMPUTADO)
        self.fields["lugar_municipio"].queryset = _activos_o_actual(
            Municipio, self.instance.lugar_municipio_id
        )


# --------------------------------------------------------------------------
# Seguimiento
# --------------------------------------------------------------------------


class ProcedimientoForm(FormularioBase):
    """Datos del procedimiento. Lo que se pide depende de si el asunto fue admitido."""

    SOLO_NO_ADMITIDO = ("motivo_no_admision", "reconsideracion")
    SOLO_ADMITIDO = ("mecanismo", "mecanismo_sustituto", "facilitador", "fecha_aceptacion")

    secciones = [
        (
            "Solicitud y derivación",
            ["fecha_solicitud", "forma_solicitud", "etapa_procesal", "procedencia"],
        ),
        ("No admisión", ["motivo_no_admision", "reconsideracion"]),
        ("Mecanismo", ["mecanismo", "mecanismo_sustituto", "facilitador", "fecha_aceptacion"]),
        ("Hechos", ["hechos"]),
    ]

    class Meta:
        model = Asunto
        fields = [
            "fecha_solicitud",
            "forma_solicitud",
            "etapa_procesal",
            "procedencia",
            "motivo_no_admision",
            "reconsideracion",
            "mecanismo",
            "mecanismo_sustituto",
            "facilitador",
            "fecha_aceptacion",
            "hechos",
        ]
        widgets = {
            "forma_solicitud": forms.RadioSelect,
            "reconsideracion": forms.RadioSelect,
            "motivo_no_admision": forms.Textarea(attrs={"rows": 3}),
            "hechos": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        admitido = self.instance.admisible == Asunto.Admisible.SI
        for nombre in self.SOLO_NO_ADMITIDO if admitido else self.SOLO_ADMITIDO:
            del self.fields[nombre]
        if admitido:
            self.fields["facilitador"].queryset = _activos_o_actual(
                Facilitador, self.instance.facilitador_id
            )

    def clean(self):
        datos = super().clean()
        mecanismo, sustituto = datos.get("mecanismo"), datos.get("mecanismo_sustituto")
        if sustituto and not mecanismo:
            self.add_error("mecanismo", "Indica primero el mecanismo que se aplicó.")
        elif sustituto and sustituto == mecanismo:
            self.add_error("mecanismo_sustituto", "Debe ser distinto del mecanismo original.")
        return datos


class ConclusionForm(FormularioBase):
    """Conclusión anticipada del mecanismo, sin acuerdo (art. 32)."""

    dependencias = {"causa_conclusion_otra": ("causa_conclusion", ["otra"])}

    class Meta:
        model = Asunto
        fields = ["fecha_conclusion", "causa_conclusion", "causa_conclusion_otra"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_conclusion"].required = True
        self.fields["causa_conclusion"].required = True

    def clean(self):
        datos = super().clean()
        if datos.get("causa_conclusion") == Asunto.CausaConclusion.OTRA:
            if not datos.get("causa_conclusion_otra", "").strip():
                self.add_error("causa_conclusion_otra", "Especifica la causa.")
        else:
            datos["causa_conclusion_otra"] = ""
        return datos


class InvitacionForm(FormularioBase):
    dependencias = {"medio_otro": ("medio", ["otro"])}

    class Meta:
        model = Invitacion
        fields = ["persona", "fecha", "medio", "medio_otro", "resultado"]

    def __init__(self, *args, asunto, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["persona"].queryset = asunto.intervinientes.all()


class SesionForm(FormularioBase):
    class Meta:
        model = Sesion
        fields = ["fecha", "tipo", "resultado", "interprete", "asistentes"]
        widgets = {
            "asistentes": forms.CheckboxSelectMultiple,
            "interprete": forms.RadioSelect,
        }

    def __init__(self, *args, asunto, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asistentes"].queryset = asunto.intervinientes.all()


class AcuerdoForm(FormularioBase):
    """Datos de la celebración del acuerdo. El cierre va en `CumplimientoForm`."""

    obligaciones = forms.MultipleChoiceField(
        label="Tipo de obligaciones",
        choices=list(Acuerdo.OBLIGACIONES.items()),
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Marca al menos un tipo de obligación."},
    )
    reparaciones = forms.MultipleChoiceField(
        label="Contenido de la reparación",
        choices=list(Acuerdo.REPARACIONES.items()),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    secciones = [
        ("Celebración", ["fecha_celebracion", "lugar_celebracion", "alcance"]),
        ("Contenido", ["obligaciones", "reparaciones", "monto_reparacion"]),
        ("Cumplimiento pactado", ["forma_cumplimiento", "fecha_limite"]),
        (
            "Validación y aprobación",
            ["fecha_validacion", "autoridad_aprueba", "fecha_aprobacion"],
        ),
    ]
    dependencias = {"fecha_limite": ("forma_cumplimiento", ["diferido"])}

    class Meta:
        model = Acuerdo
        fields = [
            "fecha_celebracion",
            "lugar_celebracion",
            "alcance",
            "monto_reparacion",
            "forma_cumplimiento",
            "fecha_limite",
            "fecha_validacion",
            "autoridad_aprueba",
            "fecha_aprobacion",
        ]
        widgets = {"alcance": forms.RadioSelect, "forma_cumplimiento": forms.RadioSelect}

    # Cada casilla marcada en pantalla es un campo de sí/no en la base de datos.
    CASILLAS = {"obligaciones": Acuerdo.OBLIGACIONES, "reparaciones": Acuerdo.REPARACIONES}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, columnas in self.CASILLAS.items():
            self.fields[nombre].initial = [c for c in columnas if getattr(self.instance, c)]

    def clean(self):
        datos = super().clean()
        for nombre, columnas in self.CASILLAS.items():
            marcadas = datos.get(nombre, [])
            for columna in columnas:
                setattr(self.instance, columna, columna in marcadas)
        return datos


class CumplimientoForm(FormularioBase):
    """Cierre del acuerdo: si se cumplió, cuándo y con qué efecto (arts. 35 a 39)."""

    _CERRADO = ["cumplido", "parcial", "incumplido"]
    dependencias = {
        "fecha_cierre": ("estado_cumplimiento", _CERRADO),
        "efecto": ("estado_cumplimiento", _CERRADO),
        "fecha_comunicacion": ("estado_cumplimiento", ["parcial", "incumplido"]),
    }

    class Meta:
        model = Acuerdo
        fields = ["estado_cumplimiento", "fecha_cierre", "fecha_comunicacion", "efecto"]

    def clean(self):
        datos = super().clean()
        C, E = Acuerdo.Cumplimiento, Acuerdo.Efecto
        estado, efecto = datos.get("estado_cumplimiento"), datos.get("efecto")
        if estado == C.EN_CURSO:
            datos.update(fecha_cierre=None, fecha_comunicacion=None, efecto="")
            return datos
        if not datos.get("fecha_cierre"):
            self.add_error("fecha_cierre", "Indica la fecha del cumplimiento o incumplimiento.")
        if estado == C.CUMPLIDO:
            datos["fecha_comunicacion"] = None
            if efecto == E.CONTINUACION:
                self.add_error(
                    "efecto", "Un acuerdo cumplido no da lugar a continuar el procedimiento."
                )
        elif estado == C.INCUMPLIDO and efecto in (E.EXTINCION, E.SOBRESEIMIENTO):
            self.add_error(
                "efecto", "El incumplimiento da lugar a continuar el procedimiento (art. 35)."
            )
        return datos


class AccionSeguimientoForm(FormularioBase):
    dependencias = {"accion_otra": ("accion", ["otra"])}

    class Meta:
        model = AccionSeguimiento
        fields = ["fecha", "accion", "accion_otra", "resultado"]
