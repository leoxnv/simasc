from django.urls import path

from . import views

app_name = "casos"

urlpatterns = [
    path("", views.AsuntoLista.as_view(), name="lista"),
    path("asuntos/nuevo/", views.AsuntoCrear.as_view(), name="crear"),
    path("asuntos/<int:pk>/", views.AsuntoDetalle.as_view(), name="detalle"),
    path("asuntos/<int:pk>/editar/", views.AsuntoEditar.as_view(), name="editar"),
    path("asuntos/<int:pk>/cancelar/", views.AsuntoCancelar.as_view(), name="cancelar"),
    path(
        "asuntos/<int:asunto_pk>/personas/<str:tipo>/nueva/",
        views.IntervinienteCrear.as_view(),
        name="persona_crear",
    ),
    path(
        "asuntos/<int:asunto_pk>/personas/<int:pk>/editar/",
        views.IntervinienteEditar.as_view(),
        name="persona_editar",
    ),
    path(
        "asuntos/<int:asunto_pk>/personas/<int:pk>/quitar/",
        views.IntervinienteEliminar.as_view(),
        name="persona_eliminar",
    ),
    path(
        "asuntos/<int:asunto_pk>/delitos/nuevo/",
        views.DelitoCrear.as_view(),
        name="delito_crear",
    ),
    path(
        "asuntos/<int:asunto_pk>/delitos/<int:pk>/editar/",
        views.DelitoEditar.as_view(),
        name="delito_editar",
    ),
    path(
        "asuntos/<int:asunto_pk>/delitos/<int:pk>/quitar/",
        views.DelitoEliminar.as_view(),
        name="delito_eliminar",
    ),
    path("bitacora/", views.bitacora, name="bitacora"),
]
