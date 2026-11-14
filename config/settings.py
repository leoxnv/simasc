"""Configuración de SIMASC.

Todo lo que cambia entre una fiscalía y otra se lee de variables de entorno
(o del archivo `.env` en la raíz del proyecto). Ver `.env.example`.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _cargar_env(ruta):
    """Lee pares CLAVE=valor de un archivo .env sin pisar el entorno real."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip("\"'"))


_cargar_env(BASE_DIR / ".env")


def _bool(nombre, default=False):
    return os.environ.get(nombre, str(int(default))).lower() in {"1", "true", "si", "sí", "yes"}


DEBUG = _bool("SIMASC_DEBUG")

SECRET_KEY = os.environ.get("SIMASC_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "Falta SIMASC_SECRET_KEY. Copia .env.example a .env y genera una clave."
    )

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("SIMASC_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("SIMASC_ORIGENES_CSRF", "").split(",") if o.strip()
]

# Nombre de la institución que opera esta instalación (se muestra en pantalla).
INSTITUCION = os.environ.get("SIMASC_INSTITUCION", "Fiscalía")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.forms",
    "simple_history",
    "cuentas",
    "catalogos",
    "casos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Todas las pantallas exigen sesión iniciada, salvo las marcadas como públicas.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Registra en la bitácora qué usuario hizo cada cambio.
    "simple_history.middleware.HistoryRequestMiddleware",
]
if not DEBUG:
    # En el servidor, WhiteNoise sirve los archivos de `collectstatic`.
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.contexto.institucion",
            ],
        },
    },
]

FORM_RENDERER = "config.formularios.Renderizador"

WSGI_APPLICATION = "config.wsgi.application"

# SQLite por omisión; para PostgreSQL basta definir
# SIMASC_DATABASE_URL=postgres://usuario:clave@servidor:5432/simasc
DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get(
            "SIMASC_DATABASE_URL", f"sqlite:///{BASE_DIR / 'datos' / 'simasc.sqlite3'}"
        ),
        conn_max_age=600,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "cuentas.Usuario"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "casos:lista"
LOGOUT_REDIRECT_URL = "login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# La sesión se cierra tras 30 minutos sin actividad o al cerrar el navegador.
SESSION_COOKIE_AGE = int(os.environ.get("SIMASC_MINUTOS_SESION", "30")) * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Con HTTPS (producción) las cookies solo viajan cifradas.
_HTTPS = _bool("SIMASC_HTTPS")
SESSION_COOKIE_SECURE = _HTTPS
CSRF_COOKIE_SECURE = _HTTPS
SECURE_SSL_REDIRECT = _HTTPS
SECURE_HSTS_SECONDS = 31536000 if _HTTPS else 0
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if _HTTPS else None

LANGUAGE_CODE = "es-mx"
TIME_ZONE = os.environ.get("SIMASC_ZONA_HORARIA", "America/Mexico_City")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
