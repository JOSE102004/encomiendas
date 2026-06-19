import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class DashboardConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = 'dashboard'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        stats = await self.get_stats()
        await self.send(text_data=json.dumps({
            'tipo': 'stats_iniciales',
            'stats': stats,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def dashboard_actualizar(self, event):
        """Recibe del channel layer y reenvía al navegador"""
        await self.send(text_data=json.dumps({
            'tipo':  'stats_actualizado',
            'stats': event['stats'],
        }))

    @database_sync_to_async
    def get_stats(self):
        from .models import Encomienda
        from django.utils import timezone
        hoy = timezone.now().date()
        return {
            'activas':        Encomienda.objects.activas().count(),
            'en_transito':    Encomienda.objects.en_transito().count(),
            'con_retraso':    Encomienda.objects.con_retraso().count(),
            'entregadas_hoy': Encomienda.objects.filter(
                estado='EN', fecha_entrega_real=hoy
            ).count(),
        }

class EncomiendaConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = 'encomiendas_global'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        stats = await self.get_estadisticas()
        await self.send(text_data=json.dumps({
            'tipo':    'conectado',
            'usuario': user.username,
            'stats':   stats,
        }))

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'tipo': 'error', 'mensaje': 'JSON inválido'
            }))
            return

        tipo = data.get('tipo')

        if tipo == 'ping':
            await self.send(text_data=json.dumps({'tipo': 'pong'}))

        elif tipo == 'solicitar_stats':
            stats = await self.get_estadisticas()
            await self.send(text_data=json.dumps({
                'tipo': 'stats', 'stats': stats
            }))

        elif tipo == 'suscribir_encomienda':
            enc_id = data.get('encomienda_id')
            if enc_id:
                await self.channel_layer.group_add(
                    f'encomienda_{enc_id}',
                    self.channel_name
                )

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def encomienda_estado_cambio(self, event):
        await self.send(text_data=json.dumps({
            'tipo':           'estado_cambio',
            'encomienda_id':  event.get('encomienda_id'),
            'codigo':         event.get('codigo'),
            'estado_anterior': event.get('estado_anterior'),
            'estado_nuevo':   event.get('estado_nuevo'),
            'empleado':       event.get('empleado'),
            'timestamp':      event.get('timestamp'),
        }))

    @database_sync_to_async
    def get_estadisticas(self):
        from .models import Encomienda
        return {
            'activas':     Encomienda.objects.activas().count(),
            'en_transito': Encomienda.objects.en_transito().count(),
            'con_retraso': Encomienda.objects.con_retraso().count(),
        }

class EncomiendaDetalleConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.pk = self.scope['url_route']['kwargs']['pk']
        self.group_name = f'encomienda_{self.pk}'
        
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def encomienda_estado_cambio(self, event):
        await self.send(text_data=json.dumps({
            'tipo':           'estado_cambio',
            'encomienda_id':  event.get('encomienda_id'),
            'codigo':         event.get('codigo'),
            'estado_anterior': event.get('estado_anterior'),
            'estado_nuevo':   event.get('estado_nuevo'),
            'empleado':       event.get('empleado'),
            'timestamp':      event.get('timestamp'),
        }))
