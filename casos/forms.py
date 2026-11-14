from django import forms
from django.db.models import Q

from catalogos.models import Municipio, Sede, UnidadOrigen

from .models import Asunto, Delito, Interviniente


def _activos_o_actual(modelo, pk_actual):
    """Opciones activas del catálogo, más la ya elegida aunque esté desactivada."""
    return modelo.objects.filter(Q(activo=True) | Q(pk=pk_actual))


class FormularioBase(forms.ModelForm):
    """Ajusta la opción vacía de las listas: fuera en los botones de opción
    obligatorios, y con un texto claro en los desplegables."""

    VACIO = "Selecciona…"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo, forms.ModelMultipleChoiceField):
                continue
            if isinstance(campo, forms.ModelChoiceField):
                campo.empty_label = self.VACIO
            elif isinstance(campo, forms.ChoiceField):
                es_radio = isinstance(campo.widget, forms.RadioSelect)
                campo.choices = [
                    (valor, self.VACIO if valor == "" else etiqueta)
                    for valor, etiqueta in campo.choices
                    if not (valor == "" and es_radio and campo.required)
                ]


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
        widgets = {
            "fecha_ingreso": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "sistema": forms.RadioSelect,
            "admisible": forms.RadioSelect,
        }

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
