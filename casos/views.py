from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, ProtectedError, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from cuentas.models import EventoAcceso

from .forms import (
    AccionSeguimientoForm,
    AcuerdoForm,
    AsuntoForm,
    CancelarAsuntoForm,
    ConclusionForm,
    CumplimientoForm,
    DelitoForm,
    IntervinienteForm,
    InvitacionForm,
    ProcedimientoForm,
    SesionForm,
)
from .models import (
    DIAS_HABILES_PARA_INVITAR,
    AccionSeguimiento,
    Acuerdo,
    Asunto,
    Delito,
    Interviniente,
    Invitacion,
    Sesion,
)


def asuntos_visibles(usuario):
    return (
        Asunto.visibles_para(usuario)
        .con_estatus()
        .select_related(
            "unidad_origen", "municipio_origen", "sede", "creado_por", "facilitador", "acuerdo"
        )
    )


class ConUsuario:
    """Pasa al formulario quién lo está llenando."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs


class FormularioGenerico:
    """Pantalla de captura dibujada a partir de las secciones del formulario."""

    template_name = "casos/formulario.html"
    titulo = ""
    nota = ""
    mensaje = "Cambios guardados."

    def get_context_data(self, **kwargs):
        return super().get_context_data(titulo=self.titulo, nota=self.nota, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, self.mensaje)
        return super().form_valid(form)


# --------------------------------------------------------------------------
# Asuntos
# --------------------------------------------------------------------------


class AsuntoLista(ListView):
    template_name = "casos/asunto_lista.html"
    context_object_name = "asuntos"
    paginate_by = 25

    def get_queryset(self):
        asuntos = asuntos_visibles(self.request.user)
        self.busqueda = self.request.GET.get("q", "").strip()
        self.estatus = self.request.GET.get("estatus", "")
        if self.estatus not in Asunto.Estatus.values:
            self.estatus = ""
        if self.busqueda:
            coincidencias = Asunto.objects.filter(
                Q(folio__icontains=self.busqueda)
                | Q(carpeta_investigacion__icontains=self.busqueda)
                | Q(nuc__icontains=self.busqueda)
                | Q(intervinientes__nombre__icontains=self.busqueda)
                | Q(intervinientes__primer_apellido__icontains=self.busqueda)
                | Q(intervinientes__segundo_apellido__icontains=self.busqueda)
            ).values("pk")
            asuntos = asuntos.filter(pk__in=coincidencias)
        if self.estatus:
            asuntos = asuntos.filter(estatus_codigo=self.estatus)
        return asuntos.annotate(
            n_victimas=Count(
                "intervinientes",
                filter=Q(intervinientes__tipo=Interviniente.Tipo.VICTIMA),
                distinct=True,
            ),
            n_imputados=Count(
                "intervinientes",
                filter=Q(intervinientes__tipo=Interviniente.Tipo.IMPUTADO),
                distinct=True,
            ),
            n_delitos=Count("delitos", distinct=True),
        ).order_by("-fecha_ingreso", "-id")

    def get_context_data(self, **kwargs):
        filtros = {
            clave: valor
            for clave, valor in (("q", self.busqueda), ("estatus", self.estatus))
            if valor
        }
        return super().get_context_data(
            busqueda=self.busqueda,
            estatus=self.estatus,
            opciones_estatus=Asunto.Estatus.choices,
            extra=urlencode(filtros) + "&" if filtros else "",
            **kwargs,
        )


class AsuntoCrear(ConUsuario, CreateView):
    form_class = AsuntoForm
    template_name = "casos/asunto_form.html"

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        respuesta = super().form_valid(form)
        messages.success(
            self.request, "Asunto registrado. Ahora agrega a las personas y los delitos."
        )
        return respuesta

    def get_success_url(self):
        return reverse("casos:detalle", args=[self.object.pk])


class AsuntoDetalle(DetailView):
    template_name = "casos/asunto_detalle.html"
    context_object_name = "asunto"

    def get_queryset(self):
        return asuntos_visibles(self.request.user)

    def get_context_data(self, **kwargs):
        asunto = self.object
        personas = list(asunto.intervinientes.all())
        acuerdo = asunto.acuerdo_o_nada
        return super().get_context_data(
            victimas=[p for p in personas if p.tipo == Interviniente.Tipo.VICTIMA],
            imputados=[p for p in personas if p.tipo == Interviniente.Tipo.IMPUTADO],
            delitos=asunto.delitos.select_related("victima", "lugar_municipio").prefetch_related(
                "imputados"
            ),
            invitaciones=asunto.invitaciones.select_related("persona"),
            sesiones=asunto.sesiones.prefetch_related("asistentes"),
            acuerdo=acuerdo,
            acciones=acuerdo.acciones.all() if acuerdo else [],
            plazo_invitacion=DIAS_HABILES_PARA_INVITAR,
            puede_editar=asunto.editable_por(self.request.user),
            **kwargs,
        )


class DelAsunto:
    """Para pantallas que editan el propio asunto (su clave va en la URL)."""

    context_object_name = "asunto"

    def get_queryset(self):
        return asuntos_visibles(self.request.user)

    def get_object(self, queryset=None):
        asunto = super().get_object(queryset)
        if not asunto.editable_por(self.request.user):
            raise PermissionDenied
        return asunto

    def get_success_url(self):
        return reverse("casos:detalle", args=[self.object.pk])


class AsuntoEditar(ConUsuario, DelAsunto, UpdateView):
    form_class = AsuntoForm
    template_name = "casos/asunto_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Cambios guardados.")
        return super().form_valid(form)


class AsuntoCancelar(UpdateView):
    """Solo supervisión cancela. El asunto queda visible pero bloqueado."""

    form_class = CancelarAsuntoForm
    template_name = "casos/asunto_cancelar.html"
    context_object_name = "asunto"

    def get_queryset(self):
        if not self.request.user.puede_supervisar:
            raise PermissionDenied
        return Asunto.objects.filter(cancelado=False)

    def form_valid(self, form):
        form.instance.cancelado = True
        messages.success(self.request, "Asunto cancelado.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("casos:detalle", args=[self.object.pk])


class ProcedimientoEditar(FormularioGenerico, DelAsunto, UpdateView):
    form_class = ProcedimientoForm
    titulo = "Procedimiento"
    nota = "Se llena conforme avanza el asunto: ningún dato es obligatorio."


class ConclusionEditar(FormularioGenerico, DelAsunto, UpdateView):
    """Conclusión anticipada, sin acuerdo. No aplica si ya hay un acuerdo."""

    form_class = ConclusionForm
    titulo = "Concluir sin acuerdo"
    nota = (
        "Al concluir el mecanismo ya no se podrán registrar más invitaciones, "
        "sesiones ni acuerdo."
    )
    mensaje = "Conclusión registrada."

    def get_object(self, queryset=None):
        asunto = super().get_object(queryset)
        if not asunto.admite_seguimiento or asunto.acuerdo_o_nada:
            raise PermissionDenied
        return asunto


@require_POST
def conclusion_quitar(request, pk):
    """Reabre un mecanismo concluido sin acuerdo. Solo supervisión."""
    if not request.user.puede_supervisar:
        raise PermissionDenied
    asunto = get_object_or_404(Asunto, pk=pk, cancelado=False)
    asunto.fecha_conclusion = None
    asunto.causa_conclusion = asunto.causa_conclusion_otra = ""
    asunto.save()
    messages.success(request, "Mecanismo reabierto.")
    return redirect("casos:detalle", pk=asunto.pk)


# --------------------------------------------------------------------------
# Registros que cuelgan de un asunto
# --------------------------------------------------------------------------


class DeUnAsunto:
    """Carga el asunto de la URL y exige que el usuario pueda editarlo."""

    def dispatch(self, request, *args, **kwargs):
        self.asunto = get_object_or_404(asuntos_visibles(request.user), pk=kwargs["asunto_pk"])
        if not self.asunto.editable_por(request.user):
            raise PermissionDenied
        return self.requisito_previo() or super().dispatch(request, *args, **kwargs)

    def requisito_previo(self):
        """Las vistas hijas pueden devolver aquí una redirección para no continuar."""
        return None

    def rechazar(self, mensaje):
        messages.warning(self.request, mensaje)
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        return super().get_context_data(asunto=self.asunto, **kwargs)

    def get_success_url(self):
        return reverse("casos:detalle", args=[self.asunto.pk])


class ConAsuntoEnFormulario:
    """Para formularios que limitan sus opciones a las personas del asunto."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["asunto"] = self.asunto
        return kwargs


class Quitar(DeUnAsunto, DeleteView):
    template_name = "casos/confirmar_eliminar.html"
    mensaje = "Registro quitado del asunto."

    def form_valid(self, form):
        messages.success(self.request, self.mensaje)
        return super().form_valid(form)


# ---- Personas ----


class IntervinienteCrear(DeUnAsunto, CreateView):
    form_class = IntervinienteForm
    template_name = "casos/interviniente_form.html"

    def dispatch(self, request, *args, **kwargs):
        if kwargs["tipo"] not in Interviniente.Tipo.values:
            raise Http404
        self.tipo = Interviniente.Tipo(kwargs["tipo"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = Interviniente(asunto=self.asunto, tipo=self.tipo)
        return kwargs

    def get_context_data(self, **kwargs):
        return super().get_context_data(tipo=self.tipo, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f"{self.tipo.label} agregado.")
        return super().form_valid(form)


class IntervinienteEditar(DeUnAsunto, UpdateView):
    form_class = IntervinienteForm
    template_name = "casos/interviniente_form.html"

    def get_queryset(self):
        return self.asunto.intervinientes.all()

    def get_context_data(self, **kwargs):
        return super().get_context_data(tipo=Interviniente.Tipo(self.object.tipo), **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Cambios guardados.")
        return super().form_valid(form)


class IntervinienteEliminar(DeUnAsunto, DeleteView):
    template_name = "casos/confirmar_eliminar.html"

    def get_queryset(self):
        return self.asunto.intervinientes.all()

    def form_valid(self, form):
        try:
            respuesta = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "No se puede quitar: es la víctima de un delito o tiene una invitación "
                "registrada. Corrige o quita primero esos registros.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "Persona quitada del asunto.")
        return respuesta


# ---- Delitos ----


class DelitoFormMixin(ConAsuntoEnFormulario, DeUnAsunto):
    form_class = DelitoForm
    template_name = "casos/delito_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Delito guardado.")
        return super().form_valid(form)


class DelitoCrear(DelitoFormMixin, CreateView):
    def requisito_previo(self):
        if not self.asunto.intervinientes.filter(tipo=Interviniente.Tipo.VICTIMA).exists():
            return self.rechazar(
                "Antes de registrar un delito agrega al menos una víctima u ofendido."
            )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = Delito(asunto=self.asunto)
        return kwargs


class DelitoEditar(DelitoFormMixin, UpdateView):
    def get_queryset(self):
        return self.asunto.delitos.all()


class DelitoEliminar(Quitar):
    mensaje = "Delito quitado del asunto."

    def get_queryset(self):
        return self.asunto.delitos.all()


# ---- Seguimiento: invitaciones, sesiones, acuerdo y su cumplimiento ----

_NO_ADMITIDO = "Un asunto no admitido o cancelado no lleva invitaciones, sesiones ni acuerdo."
_CONCLUIDO = "El mecanismo ya concluyó sin acuerdo. Supervisión puede reabrirlo."


class DeSeguimiento(FormularioGenerico, DeUnAsunto):
    """Solo los asuntos admitidos tienen seguimiento."""

    def requisito_previo(self):
        if not self.asunto.admite_seguimiento:
            return self.rechazar(_NO_ADMITIDO)


class NuevoEnMecanismoAbierto(DeSeguimiento):
    """Para dar de alta algo que solo cabe mientras el mecanismo sigue abierto."""

    def requisito_previo(self):
        if not self.asunto.admite_seguimiento:
            return self.rechazar(_NO_ADMITIDO)
        if not self.asunto.mecanismo_abierto:
            return self.rechazar(_CONCLUIDO)


class InvitacionCrear(ConAsuntoEnFormulario, NuevoEnMecanismoAbierto, CreateView):
    form_class = InvitacionForm
    titulo = "Registrar invitación"
    mensaje = "Invitación registrada."

    def requisito_previo(self):
        if not self.asunto.intervinientes.exists():
            return self.rechazar("Antes de invitar a alguien, agrégalo como persona del asunto.")
        return super().requisito_previo()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = Invitacion(asunto=self.asunto)
        return kwargs


class InvitacionEditar(ConAsuntoEnFormulario, DeSeguimiento, UpdateView):
    form_class = InvitacionForm
    titulo = "Editar invitación"

    def get_queryset(self):
        return self.asunto.invitaciones.all()


class InvitacionEliminar(Quitar):
    mensaje = "Invitación quitada."

    def get_queryset(self):
        return self.asunto.invitaciones.all()


class SesionCrear(ConAsuntoEnFormulario, NuevoEnMecanismoAbierto, CreateView):
    form_class = SesionForm
    titulo = "Registrar sesión"
    nota = (
        "Las sesiones son confidenciales: aquí solo se anota que ocurrió, "
        "quién asistió y cómo terminó, nunca lo que se dijo."
    )
    mensaje = "Sesión registrada."

    def requisito_previo(self):
        if not self.asunto.intervinientes.exists():
            return self.rechazar("Antes de registrar una sesión agrega a las personas del asunto.")
        return super().requisito_previo()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = Sesion(asunto=self.asunto)
        return kwargs


class SesionEditar(ConAsuntoEnFormulario, DeSeguimiento, UpdateView):
    form_class = SesionForm
    titulo = "Editar sesión"
    nota = SesionCrear.nota

    def get_queryset(self):
        return self.asunto.sesiones.all()


class SesionEliminar(Quitar):
    mensaje = "Sesión quitada."

    def get_queryset(self):
        return self.asunto.sesiones.all()


class DelAcuerdo:
    """El acuerdo es único por asunto: se localiza por el asunto, no por su clave."""

    def get_object(self, queryset=None):
        return get_object_or_404(Acuerdo, asunto=self.asunto)


class AcuerdoCrear(NuevoEnMecanismoAbierto, CreateView):
    form_class = AcuerdoForm
    titulo = "Registrar acuerdo"
    mensaje = "Acuerdo registrado."

    def requisito_previo(self):
        if self.asunto.acuerdo_o_nada:
            return self.rechazar("Este asunto ya tiene un acuerdo registrado.")
        return super().requisito_previo()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = Acuerdo(asunto=self.asunto)
        return kwargs


class AcuerdoEditar(DelAcuerdo, DeSeguimiento, UpdateView):
    form_class = AcuerdoForm
    titulo = "Editar acuerdo"


class CumplimientoEditar(DelAcuerdo, DeSeguimiento, UpdateView):
    form_class = CumplimientoForm
    titulo = "Cumplimiento del acuerdo"
    mensaje = "Cumplimiento actualizado."


class AcuerdoEliminar(DelAcuerdo, Quitar):
    """Quitar un acuerdo borra también su seguimiento: solo supervisión."""

    mensaje = "Acuerdo quitado."

    def requisito_previo(self):
        if not self.request.user.puede_supervisar:
            raise PermissionDenied


class DeUnAcuerdo(DeSeguimiento):
    def requisito_previo(self):
        if not self.asunto.acuerdo_o_nada:
            return self.rechazar("Primero registra el acuerdo.")
        return super().requisito_previo()

    def get_queryset(self):
        return AccionSeguimiento.objects.filter(acuerdo__asunto=self.asunto)


class AccionCrear(DeUnAcuerdo, CreateView):
    form_class = AccionSeguimientoForm
    titulo = "Registrar acción de seguimiento"
    mensaje = "Acción registrada."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = AccionSeguimiento(acuerdo=self.asunto.acuerdo)
        return kwargs


class AccionEditar(DeUnAcuerdo, UpdateView):
    form_class = AccionSeguimientoForm
    titulo = "Editar acción de seguimiento"


class AccionEliminar(Quitar):
    mensaje = "Acción quitada."

    def get_queryset(self):
        return AccionSeguimiento.objects.filter(acuerdo__asunto=self.asunto)


# --------------------------------------------------------------------------
# Bitácora (solo administración)
# --------------------------------------------------------------------------

_ACCIONES = {"+": "Creó", "~": "Modificó", "-": "Eliminó"}
_IGNORAR_EN_CAMBIOS = {"actualizado_en"}
_REGISTROS = {
    "asuntos": ("Asuntos", Asunto),
    "personas": ("Personas", Interviniente),
    "delitos": ("Delitos", Delito),
    "invitaciones": ("Invitaciones", Invitacion),
    "sesiones": ("Sesiones", Sesion),
    "acuerdos": ("Acuerdos", Acuerdo),
    "seguimiento": ("Seguimiento", AccionSeguimiento),
}
PESTANAS_BITACORA = [(clave, titulo) for clave, (titulo, _) in _REGISTROS.items()] + [
    ("accesos", "Accesos al sistema")
]


def _legible(modelo, campo, valor):
    """Convierte claves internas (códigos, ids) en el texto que ve el usuario."""
    if isinstance(valor, list):
        return f"{len(valor)} seleccionado(s)"
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if valor in (None, ""):
        return "—"
    definicion = modelo._meta.get_field(campo)
    if definicion.choices:
        return dict(definicion.flatchoices).get(valor, valor)
    if definicion.is_relation:
        return definicion.related_model.objects.filter(pk=valor).first() or valor
    return valor


def _cambios(modelo, registro):
    anterior = registro.prev_record
    if registro.history_type != "~" or anterior is None:
        return []
    return [
        {
            "campo": modelo._meta.get_field(c.field).verbose_name,
            "antes": _legible(modelo, c.field, c.old),
            "despues": _legible(modelo, c.field, c.new),
        }
        for c in registro.diff_against(anterior).changes
        if c.field not in _IGNORAR_EN_CAMBIOS
    ]


def _asunto_de(registro):
    """Asunto al que pertenece un renglón del historial (para enlazarlo)."""
    if hasattr(registro, "folio"):
        return {"id": registro.id, "folio": registro.folio}
    if hasattr(registro, "asunto_id"):
        asunto_id = registro.asunto_id
    else:
        # Acción de seguimiento: cuelga del acuerdo, que pudo haberse quitado.
        asunto_id = (
            Acuerdo.history.filter(id=registro.acuerdo_id)
            .values_list("asunto_id", flat=True)
            .first()
        )
    return Asunto.objects.filter(pk=asunto_id).values("id", "folio").first()


def bitacora(request):
    if not request.user.es_administrador:
        raise PermissionDenied

    ver = request.GET.get("ver", "asuntos")
    contexto = {
        "ver": ver,
        "pestanas": PESTANAS_BITACORA,
        "extra": urlencode({"ver": ver}) + "&",
    }
    if ver == "accesos":
        contexto["pagina"] = Paginator(
            EventoAcceso.objects.select_related("usuario"), 50
        ).get_page(request.GET.get("page"))
        return render(request, "casos/bitacora.html", contexto)

    if ver not in _REGISTROS:
        raise Http404
    modelo = _REGISTROS[ver][1]
    pagina = Paginator(modelo.history.select_related("history_user"), 50).get_page(
        request.GET.get("page")
    )
    filas = [
        {
            "fecha": h.history_date,
            "usuario": h.history_user,
            "accion": _ACCIONES[h.history_type],
            "tipo": h.history_type,
            "asunto": _asunto_de(h),
            "registro": str(h.instance),
            "cambios": _cambios(modelo, h),
        }
        for h in pagina
    ]
    contexto.update(pagina=pagina, filas=filas)
    return render(request, "casos/bitacora.html", contexto)
