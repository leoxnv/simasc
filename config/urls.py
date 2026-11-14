from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

admin.site.site_header = "SIMASC · Administración"
admin.site.site_title = "SIMASC"
admin.site.index_title = "Usuarios y catálogos"

urlpatterns = [
    path("entrar/", auth_views.LoginView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("cuenta/clave/", auth_views.PasswordChangeView.as_view(), name="password_change"),
    path(
        "cuenta/clave/lista/",
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path("administracion/", admin.site.urls),
    path("", include("casos.urls")),
]
