from django.urls import path

from . import views

app_name = "casos"

A = "asuntos/<int:asunto_pk>/"

urlpatterns = [
    path("", views.AsuntoLista.as_view(), name="lista"),
    path("asuntos/nuevo/", views.AsuntoCrear.as_view(), name="crear"),
    path("asuntos/<int:pk>/", views.AsuntoDetalle.as_view(), name="detalle"),
    path("asuntos/<int:pk>/editar/", views.AsuntoEditar.as_view(), name="editar"),
    path("asuntos/<int:pk>/cancelar/", views.AsuntoCancelar.as_view(), name="cancelar"),
    path(
        "asuntos/<int:pk>/procedimiento/",
        views.ProcedimientoEditar.as_view(),
        name="procedimiento",
    ),
    path("asuntos/<int:pk>/conclusion/", views.ConclusionEditar.as_view(), name="conclusion"),
    path(
        "asuntos/<int:pk>/conclusion/quitar/",
        views.conclusion_quitar,
        name="conclusion_quitar",
    ),
    # Personas
    path(
        A + "personas/<str:tipo>/nueva/",
        views.IntervinienteCrear.as_view(),
        name="persona_crear",
    ),
    path(
        A + "personas/<int:pk>/editar/",
        views.IntervinienteEditar.as_view(),
        name="persona_editar",
    ),
    path(
        A + "personas/<int:pk>/quitar/",
        views.IntervinienteEliminar.as_view(),
        name="persona_eliminar",
    ),
    # Delitos
    path(A + "delitos/nuevo/", views.DelitoCrear.as_view(), name="delito_crear"),
    path(A + "delitos/<int:pk>/editar/", views.DelitoEditar.as_view(), name="delito_editar"),
    path(A + "delitos/<int:pk>/quitar/", views.DelitoEliminar.as_view(), name="delito_eliminar"),
    # Invitaciones
    path(A + "invitaciones/nueva/", views.InvitacionCrear.as_view(), name="invitacion_crear"),
    path(
        A + "invitaciones/<int:pk>/editar/",
        views.InvitacionEditar.as_view(),
        name="invitacion_editar",
    ),
    path(
        A + "invitaciones/<int:pk>/quitar/",
        views.InvitacionEliminar.as_view(),
        name="invitacion_eliminar",
    ),
    # Sesiones
    path(A + "sesiones/nueva/", views.SesionCrear.as_view(), name="sesion_crear"),
    path(A + "sesiones/<int:pk>/editar/", views.SesionEditar.as_view(), name="sesion_editar"),
    path(A + "sesiones/<int:pk>/quitar/", views.SesionEliminar.as_view(), name="sesion_eliminar"),
    # Acuerdo y su cumplimiento
    path(A + "acuerdo/nuevo/", views.AcuerdoCrear.as_view(), name="acuerdo_crear"),
    path(A + "acuerdo/editar/", views.AcuerdoEditar.as_view(), name="acuerdo_editar"),
    path(A + "acuerdo/quitar/", views.AcuerdoEliminar.as_view(), name="acuerdo_eliminar"),
    path(A + "acuerdo/cumplimiento/", views.CumplimientoEditar.as_view(), name="cumplimiento"),
    path(A + "seguimiento/nueva/", views.AccionCrear.as_view(), name="accion_crear"),
    path(A + "seguimiento/<int:pk>/editar/", views.AccionEditar.as_view(), name="accion_editar"),
    path(
        A + "seguimiento/<int:pk>/quitar/",
        views.AccionEliminar.as_view(),
        name="accion_eliminar",
    ),
    path("bitacora/", views.bitacora, name="bitacora"),
]
