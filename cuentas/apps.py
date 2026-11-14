from django.apps import AppConfig


class CuentasConfig(AppConfig):
    name = "cuentas"
    verbose_name = "Usuarios y accesos"

    def ready(self):
        from . import senales  # noqa: F401
