from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import EventoAcceso


def _ip(request):
    return request.META.get("REMOTE_ADDR") if request else None


@receiver(user_logged_in)
def registrar_entrada(sender, request, user, **kwargs):
    EventoAcceso.objects.create(
        tipo=EventoAcceso.Tipo.ENTRADA,
        usuario=user,
        nombre_usuario=user.get_username(),
        ip=_ip(request),
    )


@receiver(user_logged_out)
def registrar_salida(sender, request, user, **kwargs):
    if user is None:
        return
    EventoAcceso.objects.create(
        tipo=EventoAcceso.Tipo.SALIDA,
        usuario=user,
        nombre_usuario=user.get_username(),
        ip=_ip(request),
    )


@receiver(user_login_failed)
def registrar_fallido(sender, credentials, request=None, **kwargs):
    EventoAcceso.objects.create(
        tipo=EventoAcceso.Tipo.FALLIDO,
        nombre_usuario=str(credentials.get("username", ""))[:150],
        ip=_ip(request),
    )
