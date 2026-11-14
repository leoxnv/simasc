from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Persona que usa el sistema. El rol decide qué puede ver y hacer."""

    class Rol(models.TextChoices):
        CAPTURISTA = "capturista", "Capturista"
        SUPERVISOR = "supervisor", "Supervisor"
        ADMINISTRADOR = "administrador", "Administrador"

    rol = models.CharField(
        "rol",
        max_length=20,
        choices=Rol.choices,
        default=Rol.CAPTURISTA,
        help_text=(
            "Capturista: registra asuntos y edita los de su sede. "
            "Supervisor: ve y corrige todos. "
            "Administrador: además gestiona usuarios, catálogos y bitácora."
        ),
    )

    sede = models.ForeignKey(
        "catalogos.Sede",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name="sede",
        help_text=(
            "Los capturistas de una misma sede ven y continúan los asuntos de sus "
            "compañeros. Sin sede, cada capturista ve solo los suyos."
        ),
    )

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def save(self, *args, **kwargs):
        # El rol es la única fuente de verdad: quien se crea con
        # `createsuperuser` nace administrador, y solo el administrador
        # entra al panel de administración.
        if self._state.adding and self.is_superuser:
            self.rol = self.Rol.ADMINISTRADOR
        self.is_staff = self.is_superuser = self.rol == self.Rol.ADMINISTRADOR
        super().save(*args, **kwargs)

    @property
    def es_administrador(self):
        return self.rol == self.Rol.ADMINISTRADOR

    @property
    def puede_supervisar(self):
        return self.rol in {self.Rol.SUPERVISOR, self.Rol.ADMINISTRADOR}

    @property
    def nombre_visible(self):
        return self.get_full_name() or self.username


class EventoAcceso(models.Model):
    """Entradas, salidas e intentos fallidos de inicio de sesión."""

    class Tipo(models.TextChoices):
        ENTRADA = "entrada", "Inicio de sesión"
        SALIDA = "salida", "Cierre de sesión"
        FALLIDO = "fallido", "Intento fallido"

    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    nombre_usuario = models.CharField("usuario escrito", max_length=150, blank=True)
    ip = models.GenericIPAddressField("dirección IP", null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "evento de acceso"
        verbose_name_plural = "eventos de acceso"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.nombre_usuario} · {self.fecha:%Y-%m-%d %H:%M}"
