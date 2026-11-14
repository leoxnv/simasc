# SIMASC

Sistema para registrar asuntos de mecanismos alternativos de solución de controversias en materia penal. Pensado para instalarse en el servidor de cada fiscalía.

Estado: **versión de prueba, en construcción.** Funciona la fase 1 (usuarios y roles, captura de asuntos con víctimas, imputados y delitos, bitácora). La fase 2 (seguimiento) ya tiene su modelo de datos, pero todavía no tiene pantallas. El plan completo está al final.

## Probarlo en tu computadora

Requiere Python 3.12 o posterior.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # y edita SIMASC_SECRET_KEY y SIMASC_DEBUG=1
.venv/bin/python manage.py migrate
.venv/bin/python manage.py crear_demo
.venv/bin/python manage.py runserver
```

Abre http://localhost:8000. Los usuarios de demostración y sus contraseñas están en `datos_demo/usuarios_demo.json`. Para crear tu propio administrador: `.venv/bin/python manage.py createsuperuser`.

Pruebas automáticas: `.venv/bin/python manage.py test`.

## Roles

| Rol | Puede |
|---|---|
| Capturista | Registrar asuntos, y ver y continuar los de su sede. |
| Supervisor | Ver y corregir todos los asuntos, cancelarlos y cambiarlos de sede. |
| Administrador | Lo anterior, más usuarios, sedes, catálogos y bitácora. |

Cada usuario se asigna a una sede desde el panel de administración. Un capturista sin sede solo ve los asuntos que él registró.

Nadie borra asuntos: se cancelan con un motivo y quedan visibles. Las personas y los delitos sí se pueden quitar de un asunto, y la bitácora guarda quién lo hizo.

## Cómo está organizado

| Carpeta | Contenido |
|---|---|
| `config/` | Configuración. Todo lo que cambia entre fiscalías se lee de `.env`. |
| `cuentas/` | Usuarios, roles y registro de accesos. |
| `catalogos/` | Listas que cada fiscalía adapta: sedes, municipios, unidades de origen. |
| `casos/` | Asuntos, intervinientes y delitos; pantallas y bitácora. |
| `templates/`, `static/` | Pantallas y estilos. No dependen de internet. |
| `docs/` | Propuesta de variables de seguimiento. |
| `datos_demo/` | Usuarios de demostración. No usar en producción. |

Las claves del diccionario de datos (M1, A2, D5…) están anotadas junto a cada campo en `casos/models.py`.

## Plan

1. **Hecho.** Usuarios, roles, captura de asuntos, bitácora.
2. **En curso.** Seguimiento: mecanismo, sesiones, acuerdo y cumplimiento (ver `docs/propuesta_seguimiento.md`). Listo el modelo de datos; faltan las pantallas.
3. Catálogos ampliados y campos adicionales por fiscalía.
4. Exportación, reportes, tablero y archivo anonimizado para el ONC.
5. Importación de históricos desde Excel.
6. Empaquetado con Docker, respaldos y manual de instalación.
