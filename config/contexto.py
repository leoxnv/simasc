from django.conf import settings


def institucion(request):
    return {"INSTITUCION": settings.INSTITUCION}
