import pytest
import json
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from config.asgi import application
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async

User = get_user_model()

from envios.consumers import EncomiendaConsumer

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestEncomiendaConsumer:

    async def test_conexion_sin_autenticacion(self):
        """Sin autenticar: el servidor debe rechazar con código 4001"""
        from django.contrib.auth.models import AnonymousUser
        communicator = WebsocketCommunicator(EncomiendaConsumer.as_asgi(), '/ws/encomiendas/')
        communicator.scope['user'] = AnonymousUser()
        connected, code = await communicator.connect()
        assert not connected
        assert code == 4001
        await communicator.disconnect()

    async def test_ping_pong(self):
        """El consumer responde pong al recibir ping"""
        # Creando un usuario de prueba directamente
        user = await database_sync_to_async(User.objects.create_user)(
            username='testuser', email='test@example.com', password='testpassword'
        )
        communicator = WebsocketCommunicator(EncomiendaConsumer.as_asgi(), '/ws/encomiendas/')
        communicator.scope['user'] = user

        await communicator.connect()
        await communicator.receive_json_from(timeout=2)  # bienvenida

        await communicator.send_json_to({'tipo': 'ping'})
        response = await communicator.receive_json_from(timeout=2)
        assert response['tipo'] == 'pong'

        await communicator.disconnect()

    async def test_notificacion_via_channel_layer(self):
        """El consumer recibe y reenvía mensajes del channel layer"""
        user = await database_sync_to_async(User.objects.create_user)(
            username='testuser2', email='test2@example.com', password='testpassword'
        )
        communicator = WebsocketCommunicator(EncomiendaConsumer.as_asgi(), '/ws/encomiendas/')
        communicator.scope['user'] = user

        await communicator.connect()
        await communicator.receive_json_from(timeout=2)  # bienvenida

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            'encomiendas_global',
            {
                'type':           'encomienda_estado_cambio',
                'encomienda_id':  1,
                'codigo':         'ENC-2026-001',
                'estado_anterior': 'PE',
                'estado_nuevo':   'TR',
                'empleado':       'Mendoza Cruz, Luis',
                'timestamp':      '2026-05-14T10:00:00Z',
            }
        )

        response = await communicator.receive_json_from(timeout=3)
        assert response['tipo']         == 'estado_cambio'
        assert response['codigo']       == 'ENC-2026-001'
        assert response['estado_nuevo'] == 'TR'

        await communicator.disconnect()
