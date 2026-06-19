import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User

@pytest.fixture
def api_client():
    """Cliente de API sin autenticacion"""
    return APIClient()

from envios.models import Empleado

@pytest.fixture
def user(db):
    """Usuario de prueba"""
    u = User.objects.create_user(
        username='test_empleado',
        email='empleado@encomiendas.pe',
        password='test1234',
    )
    Empleado.objects.create(
        codigo='EMP-TEST',
        nombres='Test',
        apellidos='Empleado',
        email=u.email,
        estado=1,
        fecha_ingreso='2026-01-01'
    )
    return u

@pytest.fixture
def auth_client(api_client, user):
    """Cliente de API con JWT valido"""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
    )
    return api_client
