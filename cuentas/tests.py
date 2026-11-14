from django.test import TestCase
from django.urls import reverse

from .models import Usuario


class PanelDeUsuariosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user(
            "admin", password="x", rol=Usuario.Rol.ADMINISTRADOR
        )

    def test_administrador_da_de_alta_un_supervisor(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("admin:cuentas_usuario_add"),
            {
                "username": "nueva",
                "first_name": "Nueva",
                "last_name": "Persona",
                "rol": "supervisor",
                "password1": "clave-larga-de-prueba-91",
                "password2": "clave-larga-de-prueba-91",
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        nueva = Usuario.objects.get(username="nueva")
        self.assertEqual(nueva.rol, Usuario.Rol.SUPERVISOR)
        self.assertTrue(nueva.check_password("clave-larga-de-prueba-91"))
        self.assertFalse(nueva.is_staff)

    def test_supervisor_no_entra_al_panel(self):
        supervisor = Usuario.objects.create_user("sup", password="x", rol=Usuario.Rol.SUPERVISOR)
        self.client.force_login(supervisor)
        respuesta = self.client.get(reverse("admin:index"))
        self.assertEqual(respuesta.status_code, 302)

    def test_createsuperuser_nace_administrador(self):
        raiz = Usuario.objects.create_superuser("raiz", password="x")
        self.assertEqual(raiz.rol, Usuario.Rol.ADMINISTRADOR)
