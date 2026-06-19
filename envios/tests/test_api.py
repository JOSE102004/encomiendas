import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse as django_reverse

def reverse(viewname, *args, **kwargs):
    if 'kwargs' not in kwargs:
        kwargs['kwargs'] = {}
    if 'version' not in kwargs['kwargs']:
        kwargs['kwargs']['version'] = 'v1'
    return django_reverse(viewname, *args, **kwargs)

from envios.models import Encomienda
from config.choices import EstadoEnvio
from .factories import (
    UserFactory, ClienteFactory, RutaFactory,
    EmpleadoFactory, EncomiendaFactory,
)

@pytest.mark.django_db
class TestAutenticacion:
    def test_sin_token_devuelve_401(self, api_client):
        response = api_client.get(reverse('encomienda-list'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_invalido_devuelve_401(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION='Bearer tokeninvalido')
        response = api_client.get(reverse('encomienda-list'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_con_token_valido_devuelve_200(self, auth_client):
        response = auth_client.get(reverse('encomienda-list'))
        assert response.status_code == status.HTTP_200_OK

@pytest.mark.django_db
class TestListadoEncomiendas:
    def setup_method(self):
        self.user = UserFactory()
        self.empleado = EmpleadoFactory(email=self.user.email)
        self.ruta = RutaFactory()
        self.cliente1 = ClienteFactory()
        self.cliente2 = ClienteFactory()
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
        )

    def test_lista_respuesta_paginada(self):
        EncomiendaFactory(
            remitente=self.cliente1, destinatario=self.cliente2,
            ruta=self.ruta, empleado_registro=self.empleado
        )
        response = self.client.get(reverse('encomienda-list'))
        assert response.status_code == status.HTTP_200_OK
        for campo in ['count', 'next', 'previous', 'results']:
            assert campo in response.data
        assert response.data['count'] == 1

    def test_filtro_por_estado(self):
        enc_pe = EncomiendaFactory(estado='PE', ruta=self.ruta,
            remitente=self.cliente1, destinatario=self.cliente2,
            empleado_registro=self.empleado)
        enc_tr = EncomiendaFactory(estado='TR', ruta=self.ruta,
            remitente=self.cliente1, destinatario=self.cliente2,
            empleado_registro=self.empleado)
        response = self.client.get(reverse('encomienda-list') + '?estado=PE')
        codigos = [r['codigo'] for r in response.data['results']]
        assert enc_pe.codigo in codigos
        assert enc_tr.codigo not in codigos

    def test_busqueda_por_codigo(self):
        enc = EncomiendaFactory(codigo='ENC-2026-BUSCAR', ruta=self.ruta,
            remitente=self.cliente1, destinatario=self.cliente2,
            empleado_registro=self.empleado)
        response = self.client.get(reverse('encomienda-list') + '?search=BUSCAR')
        assert response.data['count'] == 1
        assert response.data['results'][0]['codigo'] == 'ENC-2026-BUSCAR'

@pytest.mark.django_db
class TestCrearEncomienda:
    def setup_method(self):
        self.user = UserFactory()
        self.empleado = EmpleadoFactory(email=self.user.email)
        self.cliente1 = ClienteFactory()
        self.cliente2 = ClienteFactory()
        self.ruta = RutaFactory(precio_base=Decimal('25.00'))
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
        )
        self.data_valida = {
            'codigo': 'ENC-2026-TEST', 'descripcion': 'Paquete de prueba',
            'peso_kg': '3.50', 'remitente': self.cliente1.pk,
            'destinatario': self.cliente2.pk,
            'ruta': self.ruta.pk, 'costo_envio': '25.00',
        }

    def test_crear_exitoso_devuelve_201(self):
        response = self.client.post(
            reverse('encomienda-list'), self.data_valida, format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['codigo'] == 'ENC-2026-TEST'
        assert response.data['estado'] == 'PE'
        assert Encomienda.objects.filter(codigo='ENC-2026-TEST').exists()

    def test_crear_asigna_empleado_del_token(self):
        self.client.post(
            reverse('encomienda-list'), self.data_valida, format='json'
        )
        enc = Encomienda.objects.get(codigo='ENC-2026-TEST')
        assert enc.empleado_registro.email == self.user.email

    def test_remitente_igual_destinatario_devuelve_400(self):
        data = {**self.data_valida, 'destinatario': self.cliente1.pk}
        response = self.client.post(
            reverse('encomienda-list'), data, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'destinatario' in response.data['detail'] or 'non_field_errors' in response.data['detail']

    def test_peso_negativo_devuelve_400_con_campo(self):
        data = {**self.data_valida, 'peso_kg': '-1.00'}
        response = self.client.post(
            reverse('encomienda-list'), data, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'peso_kg' in response.data['detail']

    def test_codigo_sin_prefijo_devuelve_400(self):
        data = {**self.data_valida, 'codigo': 'PKG-2026-001'}
        response = self.client.post(
            reverse('encomienda-list'), data, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'codigo' in response.data['detail']

    def test_sin_auth_no_crea_y_devuelve_401(self, api_client):
        response = api_client.post(
            reverse('encomienda-list'), self.data_valida, format='json'
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert not Encomienda.objects.filter(codigo='ENC-2026-TEST').exists()

@pytest.mark.django_db
class TestCambiarEstado:
    """Tests del endpoint POST /api/v1/encomiendas/{pk}/cambiar_estado/"""

    def setup_method(self):
        self.user = UserFactory()
        self.empleado = EmpleadoFactory(email=self.user.email)
        self.enc = EncomiendaFactory(
            empleado_registro=self.empleado, estado='PE'
        )
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
        )

    def test_cambiar_estado_exitoso_actualiza_bd_y_crea_historial(self):
        url = reverse('encomienda-cambiar-estado', kwargs={'pk': self.enc.pk})
        data = {'estado': 'TR', 'observacion': 'Recogido en agencia Lima'}
        response = self.client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['estado'] == 'TR'
        self.enc.refresh_from_db()
        assert self.enc.estado == EstadoEnvio.EN_TRANSITO
        assert self.enc.historial.count() == 1
        h = self.enc.historial.first()
        assert h.estado_anterior == 'PE'
        assert h.estado_nuevo == 'TR'
        assert h.observacion == 'Recogido en agencia Lima'

    def test_cambiar_al_mismo_estado_devuelve_400(self):
        url = reverse('encomienda-cambiar-estado', kwargs={'pk': self.enc.pk})
        response = self.client.post(url, {'estado': 'PE'}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.enc.refresh_from_db()
        assert self.enc.historial.count() == 0

    def test_sin_campo_estado_devuelve_400(self):
        url = reverse('encomienda-cambiar-estado', kwargs={'pk': self.enc.pk})
        response = self.client.post(url, {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    def test_encomienda_inexistente_devuelve_404(self):
        url = reverse('encomienda-cambiar-estado', kwargs={'pk': 99999})
        response = self.client.post(url, {'estado': 'TR'}, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
class TestAccionesPersonalizadas:
    """Tests de con_retraso, pendientes y estadisticas"""

    def setup_method(self):
        from django.utils import timezone
        from datetime import timedelta
        self.user = UserFactory()
        self.empleado = EmpleadoFactory(email=self.user.email)
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
        )
        ayer = timezone.now().date() - timedelta(days=1)
        self.enc_retraso = EncomiendaFactory(
            estado='TR',
            empleado_registro=self.empleado
        )
        # Bypassing clean() validation using .update()
        Encomienda.objects.filter(pk=self.enc_retraso.pk).update(fecha_entrega_est=ayer)
        self.enc_retraso.refresh_from_db()
        self.enc_normal = EncomiendaFactory(
            estado='PE', empleado_registro=self.empleado
        )

    def test_con_retraso_solo_devuelve_retrasadas(self):
        response = self.client.get(reverse('encomienda-con-retraso'))
        assert response.status_code == status.HTTP_200_OK
        codigos = [r['codigo'] for r in response.data]
        assert self.enc_retraso.codigo in codigos
        assert self.enc_normal.codigo not in codigos

    def test_pendientes_solo_devuelve_pendientes(self):
        response = self.client.get(reverse('encomienda-pendientes'))
        assert response.status_code == status.HTTP_200_OK
        codigos = [r['codigo'] for r in response.data]
        assert self.enc_normal.codigo in codigos
        assert self.enc_retraso.codigo not in codigos

    def test_estadisticas_devuelve_todos_los_contadores(self):
        response = self.client.get(reverse('encomienda-estadisticas'))
        assert response.status_code == status.HTTP_200_OK
        for campo in ['total_activas','en_transito','con_retraso','entregadas_hoy']:
            assert campo in response.data
        assert response.data['con_retraso'] == 1

@pytest.mark.django_db
class TestVersionado:
    """Tests de versionado v1 vs v2"""

    def setup_method(self):
        self.user = UserFactory()
        EmpleadoFactory(email=self.user.email)
        EncomiendaFactory()
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
        )

    def test_v1_responde_200_con_cabecera(self):
        response = self.client.get('/api/v1/encomiendas/')
        assert response.status_code == status.HTTP_200_OK
        assert response['X-API-Version'] == 'v1'

    def test_v2_responde_200_con_cabecera(self):
        response = self.client.get('/api/v2/encomiendas/')
        assert response.status_code == status.HTTP_200_OK
        assert response['X-API-Version'] == 'v2'

    def test_v2_incluye_campo_meta(self):
        response = self.client.get('/api/v2/encomiendas/')
        primer = response.data['results'][0]
        assert 'meta' in primer
        assert primer['meta']['version'] == 'v2'

    def test_v3_no_permitida_devuelve_404(self):
        response = self.client.get('/api/v3/encomiendas/')
        assert response.status_code == status.HTTP_404_NOT_FOUND
