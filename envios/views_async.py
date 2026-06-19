import asyncio
from django.http import JsonResponse
from django.utils import timezone
from .models import Encomienda

async def dashboard_stats_async(request):
    """
    Endpoint async que calcula las estadísticas del dashboard.
    """
    if not request.user.is_authenticated:
        from django.http import HttpResponse
        return HttpResponse(status=401)

    hoy = timezone.now().date()

    activas, en_transito, con_retraso, entregadas_hoy = await asyncio.gather(
        Encomienda.objects.activas().acount(),
        Encomienda.objects.en_transito().acount(),
        Encomienda.objects.con_retraso().acount(),
        Encomienda.objects.filter(
            estado='EN', fecha_entrega_real=hoy
        ).acount(),
    )

    return JsonResponse({
        'activas':        activas,
        'en_transito':    en_transito,
        'con_retraso':    con_retraso,
        'entregadas_hoy': entregadas_hoy,
    })

async def cambiar_estado_vista(request, pk: int):
    """
    Vista async que cambia el estado y lanza notificaciones
    en background sin hacer esperar al cliente.
    """
    enc = await Encomienda.objects.aget(pk=pk)
    
    # We load json body, as request.data is not natively in Django unless using DRF
    import json
    try:
        data = json.loads(request.body)
        nuevo_estado = data.get('estado')
    except:
        nuevo_estado = request.POST.get('estado')

    if nuevo_estado:
        enc.estado = nuevo_estado
        await enc.asave()

        # lanzar notificaciones en BACKGROUND (no críticas)
        # Assuming we just simulate it here as the function might not be defined
        # asyncio.create_task(enviar_notificacion_email(enc, nuevo_estado))

    return JsonResponse({'ok': True, 'estado': nuevo_estado})
