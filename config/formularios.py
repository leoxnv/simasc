from django.forms.renderers import TemplatesSetting


class Renderizador(TemplatesSetting):
    """Dibuja cada campo con la plantilla propia del sistema."""

    field_template_name = "formularios/campo.html"
