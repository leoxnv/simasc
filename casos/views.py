from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, ProtectedError, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from cuentas.models import EventoAcceso

from .forms import AsuntoForm, CancelarAsuntoForm, DelitoForm, IntervinienteForm
from .models import Asunto, Delito, Interviniente


def asuntos_visibles(usuario):
    return Asunto.visibles_para(usuario).select_related(
        "unidad_origen", "municipio_origen", "sede", "creado_por"
    )


class ConUsuario:
    """Pasa al formulario quién lo está llenando."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs


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
        extra = urlencode({"q": self.busqueda}) + "&" if self.busqueda else ""
        return super().get_context_data(busqueda=self.busqueda, extra=extra, **kwargs)


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
        return super().get_context_data(
            victimas=[p for p in personas if p.tipo == Interviniente.Tipo.VICTIMA],
            imputados=[p for p in personas if p.tipo == Interviniente.Tipo.IMPUTADO],
            delitos=asunto.delitos.select_related("victima", "lugar_municipio").prefetch_related(
                "imputados"
            ),
            puede_editar=asunto.editable_por(self.request.user),
            **kwargs,
        )


class AsuntoEditar(ConUsuario, UpdateView):
    form_class = AsuntoForm
    template_name = "casos/asunto_form.html"

    def get_queryset(self):
        return asuntos_visibles(self.request.user)

    def get_object(self, queryset=None):
        asunto = super().get_object(queryset)
        if not asunto.editable_por(self.request.user):
            raise PermissionDenied
        return asunto

    def form_valid(self, form):
        messages.success(self.request, "Cambios guardados.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("casos:detalle", args=[self.object.pk])


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


# --------------------------------------------------------------------------
# Personas y delitos de un asunto
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

    def get_context_data(self, **kwargs):
        return super().get_context_data(asunto=self.asunto, **kwargs)

    def get_success_url(self):
        return reverse("casos:detalle", args=[self.asunto.pk])


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
                "No se puede quitar: es la víctima de un delito registrado. "
                "Corrige o quita primero ese delito.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "Persona quitada del asunto.")
        return respuesta


class DelitoFormMixin(DeUnAsunto):
    form_class = DelitoForm
    template_name = "casos/delito_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["asunto"] = self.asunto
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Delito guardado.")
        return super().form_valid(form)


class DelitoCrear(DelitoFormMixin, CreateView):
    def requisito_previo(self):
        if not self.asunto.intervinientes.filter(tipo=Interviniente.Tipo.VICTIMA).exists():
            messages.warning(
                self.request,
                "Antes de registrar un delito agrega al menos una víctima u ofendido.",
            )
            return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = Delito(asunto=self.asunto)
        return kwargs


class DelitoEditar(DelitoFormMixin, UpdateView):
    def get_queryset(self):
        return self.asunto.delitos.all()


class DelitoEliminar(DeUnAsunto, DeleteView):
    template_name = "casos/confirmar_eliminar.html"

    def get_queryset(self):
        return self.asunto.delitos.all()

    def form_valid(self, form):
        messages.success(self.request, "Delito quitado del asunto.")
        return super().form_valid(form)


# --------------------------------------------------------------------------
# Bitácora (solo administración)
# --------------------------------------------------------------------------

_ACCIONES = {"+": "Creó", "~": "Modificó", "-": "Eliminó"}
_IGNORAR_EN_CAMBIOS = {"actualizado_en"}
_REGISTROS = {
    "asuntos": Asunto,
    "personas": Interviniente,
    "delitos": Delito,
}


def _legible(modelo, campo, valor):
    """Convierte claves internas (códigos, ids) en el texto que ve el usuario."""
    if isinstance(valor, list):
        return f"{len(valor)} seleccionado(s)"
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


def bitacora(request):
    if not request.user.es_administrador:
        raise PermissionDenied

    ver = request.GET.get("ver", "asuntos")
    contexto = {"ver": ver, "extra": urlencode({"ver": ver}) + "&"}
    if ver == "accesos":
        contexto["pagina"] = Paginator(
            EventoAcceso.objects.select_related("usuario"), 50
        ).get_page(request.GET.get("page"))
        return render(request, "casos/bitacora.html", contexto)

    modelo = _REGISTROS.get(ver)
    if modelo is None:
        raise Http404
    historial = modelo.history.select_related("history_user")
    if modelo is not Asunto:
        historial = historial.select_related("asunto")
    pagina = Paginator(historial, 50).get_page(request.GET.get("page"))
    filas = [
        {
            "fecha": h.history_date,
            "usuario": h.history_user,
            "accion": _ACCIONES[h.history_type],
            "tipo": h.history_type,
            "asunto": h if modelo is Asunto else h.asunto,
            "registro": str(h.instance),
            "cambios": _cambios(modelo, h),
        }
        for h in pagina
    ]
    contexto.update(pagina=pagina, filas=filas)
    return render(request, "casos/bitacora.html", contexto)
