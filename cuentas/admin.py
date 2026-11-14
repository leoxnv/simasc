from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from .models import EventoAcceso, Usuario

# Los grupos de Django no se usan: el rol del usuario lo decide todo.
admin.site.unregister(Group)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "rol", "sede", "is_active", "last_login")
    list_filter = ("rol", "sede", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")
    # Sin grupos ni permisos sueltos: el rol lo decide todo.
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Datos de la persona", {"fields": ("first_name", "last_name", "email")}),
        ("Acceso", {"fields": ("rol", "sede", "is_active")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "first_name",
                    "last_name",
                    "rol",
                    "sede",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    readonly_fields = ("last_login", "date_joined")

    def has_delete_permission(self, request, obj=None):
        # Un usuario que ya capturó no se borra: se desactiva.
        return False


@admin.register(EventoAcceso)
class EventoAccesoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "nombre_usuario", "ip")
    list_filter = ("tipo",)
    search_fields = ("nombre_usuario", "ip")
    date_hierarchy = "fecha"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
