from django.contrib import admin

from .models import Facilitador, Municipio, Sede, UnidadOrigen


class CatalogoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)

    def has_delete_permission(self, request, obj=None):
        # Lo ya usado en asuntos no se borra: se desactiva.
        return False


@admin.register(Municipio)
class MunicipioAdmin(CatalogoAdmin):
    list_display = ("nombre", "clave_inegi", "activo")


@admin.register(UnidadOrigen)
class UnidadOrigenAdmin(CatalogoAdmin):
    pass


@admin.register(Sede)
class SedeAdmin(CatalogoAdmin):
    pass


@admin.register(Facilitador)
class FacilitadorAdmin(CatalogoAdmin):
    pass
