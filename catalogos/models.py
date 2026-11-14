from django.db import models


class Catalogo(models.Model):
    """Base de las listas que cada fiscalía adapta a su realidad."""

    nombre = models.CharField(max_length=200, unique=True)
    activo = models.BooleanField(
        default=True,
        help_text="Desmarca para que deje de aparecer en los formularios sin borrar el historial.",
    )

    class Meta:
        abstract = True
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Municipio(Catalogo):
    clave_inegi = models.CharField("clave INEGI", max_length=5, blank=True)

    class Meta(Catalogo.Meta):
        verbose_name = "municipio"
        verbose_name_plural = "municipios"


class Sede(Catalogo):
    """Sede o unidad del órgano de MASC donde trabajan los capturistas.

    Quienes comparten sede ven y continúan los asuntos de sus compañeros.
    """

    class Meta(Catalogo.Meta):
        verbose_name = "sede de mecanismos alternativos"
        verbose_name_plural = "sedes de mecanismos alternativos"


class Facilitador(Catalogo):
    """Profesional certificado que conduce el mecanismo (art. 3 fr. V de la LNMASCMP)."""

    class Meta(Catalogo.Meta):
        verbose_name = "facilitador"
        verbose_name_plural = "facilitadores"


class UnidadOrigen(Catalogo):
    """Fiscalía, agencia o unidad que deriva el asunto (variable A3)."""

    class Meta(Catalogo.Meta):
        verbose_name = "fiscalía, agencia o unidad de origen"
        verbose_name_plural = "fiscalías, agencias o unidades de origen"
