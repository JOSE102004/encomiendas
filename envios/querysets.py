# envios/querysets.py
from django.db import models

class EncomiendaQuerySet(models.QuerySet):

    # ── Filtros por estado ───────────────────────────
    def pendientes(self):
        return self.filter(estado='PE')

    def en_transito(self):
        return self.filter(estado='TR')

    def entregadas(self):
        return self.filter(estado='EN')

    def devueltas(self):
        return self.filter(estado='DV')

    def activas(self):
        """Pendientes + en tránsito + en destino"""
        return self.filter(estado__in=['PE', 'TR', 'DE'])

    # ── Filtros compuestos ─────────────────────────
    def por_ruta(self, ruta):
        return self.filter(ruta=ruta)

    def por_remitente(self, cliente):
        return self.filter(remitente=cliente)

    def por_destinatario(self, cliente):
        return self.filter(destinatario=cliente)

    def en_transito_por_ruta(self, ruta):
        return self.en_transito().por_ruta(ruta)

    # ── Con retraso ────────────────────────────
    def con_retraso(self):
        """Encomiendas activas cuya fecha estimada ya pasó"""
        from django.utils import timezone
        return self.activas().filter(
               fecha_entrega_est__lt=timezone.now().date()
        )

    # ── Optimización de consultas ──────────────────
    def con_relaciones(self):
        """Precarga las relaciones más usadas (evita el problema N+1)"""
        return self.select_related(
            'remitente', 'destinatario', 'ruta', 'empleado_registro'
        )


class ClienteQuerySet(models.QuerySet):

    def activos(self):
        return self.filter(estado=1)

    def de_baja(self):
        return self.filter(estado=9)

    def con_dni(self):
        return self.filter(tipo_doc='DNI')

    def buscar(self, termino):
        """Búsqueda por nombre, apellido o número de documento"""
        return self.filter(
               models.Q(nombres__icontains=termino) |
               models.Q(apellidos__icontains=termino) |
               models.Q(nro_doc__icontains=termino)
        )


class RutaQuerySet(models.QuerySet):

    def activas(self):
        return self.filter(estado=1)

    def por_origen(self, ciudad):
        return self.filter(origen__icontains=ciudad)

    def por_destino(self, ciudad):
        return self.filter(destino__icontains=ciudad)
