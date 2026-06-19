# Asincronía, WebSockets y Sistemas Reactivos

**Python para Backend**
**Javier Villegas — 14 de mayo 2026**

---

## ¿Qué construiremos en esta sesión?

Al terminar tendremos el sistema de encomiendas con capacidades en tiempo real:

1. **Notificaciones push:** cuando una encomienda cambia de estado, todos los clientes conectados reciben la actualización al instante.
2. **Dashboard live:** los contadores (activas, en tránsito, con retraso) se actualizan automáticamente sin recargar la página.
3. **Progreso de tareas:** el endpoint `bulk_create` reporta el avance de creación masiva en tiempo real.
4. **Feed de actividad:** cualquier empleado conectado ve todos los cambios del sistema en un feed en vivo.

---

## Parte 1 — Asincronía y WebSockets

### Programación Síncrona vs Asíncrona

En la programación síncrona, cada operación bloquea la ejecución hasta completarse. En la programación asíncrona, mientras una operación espera (BD, red, archivo), Python puede atender otras solicitudes.

La diferencia principal radica en el orden y el bloqueo de tareas: el código síncrono ejecuta instrucciones secuencialmente (una tras otra), bloqueando el flujo hasta finalizar, mientras que el asíncrono permite iniciar tareas independientes sin esperar a que terminen, mejorando la eficiencia y evitando bloqueo.

La programación asíncrona es un paradigma que permite una mejor concurrencia — la ejecución simultánea de múltiples subprocesos. En Python, el módulo `asyncio` ofrece esta capacidad. Varias tareas pueden ejecutarse simultáneamente en un único subproceso, que se programa en un único núcleo de la CPU.

Aunque Python admite el multithreading, la concurrencia está limitada por el **Global Interpreter Lock (GIL)**. El GIL garantiza que solo un hilo pueda adquirir el bloqueo a la vez. La programación asíncrona no resuelve la limitación del GIL, pero permite una mejor concurrencia.

Con el multiprocesamiento, la programación de tareas la realiza el sistema operativo. Con el multihilo, el intérprete de Python se encarga de la programación. En la programación asíncrona de Python, la programación la realiza el **bucle de eventos** (event loop). Los desarrolladores pueden especificar en su código cuándo una tarea cede voluntariamente la CPU — por esta razón también se denomina **multitarea cooperativa**.

---

### El Event Loop — el motor de la asincronía

El event loop es un bucle que monitorea qué corrutinas están listas para ejecutarse. Cuando una corrutina llega a un `await`, cede el control al event loop. El event loop ejecuta otra corrutina disponible y vuelve a la primera cuando su operación de I/O ha terminado.

```
# Total tiempo síncrono:   A + B + C = 300ms + 300ms + 300ms = 900ms
# Total tiempo asíncrono:  max(A,B,C) = 300ms
```

```python
import asyncio

async def consultar_encomiendas():
    # await le dice al event loop: 'pausa aqui y atiende a otros'
    await asyncio.sleep(0.3)   # simula la query a la BD
    return 'encomiendas ok'

async def consultar_clientes():
    await asyncio.sleep(0.3)
    return 'clientes ok'

async def consultar_rutas():
    await asyncio.sleep(0.3)
    return 'rutas ok'

async def main():
    # gather las lanza TODAS A LA VEZ y espera que terminen
    enc, cli, rut = await asyncio.gather(
        consultar_encomiendas(),
        consultar_clientes(),
        consultar_rutas(),
    )
    print(enc, cli, rut)

asyncio.run(main())   # crea el event loop, ejecuta main, lo cierra
```

---

### Corrutinas — funciones que pueden pausarse

Una corrutina es una función declarada con `async def`. A diferencia de una función normal, una corrutina puede suspenderse en puntos específicos (marcados con `await`) y retomar la ejecución exactamente donde se dejó.

**Diferencia fundamental:**

```python
# ── Función normal ────────────────────────────────────────────────
def obtener_encomienda_sync(codigo: str):
    import time
    time.sleep(0.5)  # BLOQUEA: nadie más puede ejecutarse
    return Encomienda.objects.get(codigo=codigo)

# El hilo esta BLOQUEADO 500ms. Nada más puede ejecutarse.


# ── Corrutina ──────────────────────────────────────────────────────
async def obtener_encomienda_async(codigo: str):
    # await: el event loop puede atender otros requests mientras espera
    enc = await Encomienda.objects.aget(codigo=codigo)
    return enc

# Llamada (solo funciona desde dentro de una función async):
enc = await obtener_encomienda_async('ENC-2026-001')
# El event loop CEDE el control mientras espera la BD.
# Otros requests pueden procesarse durante ese tiempo.


# ── Llamar una corrutina desde código síncrono ───────────────────
import asyncio
enc = asyncio.run(obtener_encomienda_async('ENC-2026-001'))
# asyncio.run() crea un event loop temporal, ejecuta la corrutina y lo cierra
```

**Corrutina completa del proyecto (`envios/async_services.py`):**

```python
import asyncio
import httpx
from django.utils import timezone

async def verificar_estado_transportista(codigo: str) -> dict:
    """
    Corrutina que consulta la API del transportista.
    Puede pausarse mientras espera la respuesta HTTP.
    """
    url = f'https://api.transportista.pe/v1/track/{codigo}'
    try:
        async with httpx.AsyncClient() as client:
            # await: se pausa aqui. El event loop atiende otros requests.
            response = await client.get(url, timeout=5.0)
            data = response.json()
            return {
                'codigo':      codigo,
                'encontrado':  True,
                'estado_ext':  data.get('status'),
                'ubicacion':   data.get('location'),
                'timestamp':   timezone.now().isoformat(),
            }
    except httpx.TimeoutException:
        return {'codigo': codigo, 'encontrado': False, 'error': 'timeout'}
    except httpx.ConnectError:
        return {'codigo': codigo, 'encontrado': False, 'error': 'conexion'}


async def actualizar_estados_en_transito() -> list:
    """
    Actualiza el estado de todas las encomiendas en tránsito
    consultando la API del transportista en paralelo.
    """
    # 1. Obtener encomiendas en tránsito (query async)
    encomiendas = await Encomienda.objects.en_transito().alist()

    if not encomiendas:
        return []

    # 2. Consultar el transportista para TODAS en paralelo
    #     Sin async: 50 enc * 1s = 50 segundos
    #     Con async: ~1 segundo (todas en paralelo)
    resultados = await asyncio.gather(
        *[verificar_estado_transportista(enc.codigo) for enc in encomiendas],
        return_exceptions=True
    )

    # 3. Procesar los resultados
    actualizadas = []
    for enc, resultado in zip(encomiendas, resultados):
        if isinstance(resultado, Exception):
            continue   # ignorar errores individuales

        if resultado.get('encontrado') and resultado.get('estado_ext') == 'DELIVERED':
            enc.estado = 'EN'
            enc.fecha_entrega_real = timezone.now().date()
            await enc.asave()
            actualizadas.append(enc.codigo)

    return actualizadas
```

---

### `await` — el punto de suspensión

La palabra clave `await` tiene dos efectos: suspende la corrutina actual y devuelve el control al event loop, y extrae el resultado de la corrutina cuando termina. Sólo puede aparecer dentro de una función declarada con `async def`.

```python
# await puede usarse con:

# 1. Otras corrutinas
enc = await obtener_encomienda_async('ENC-001')

# 2. Métodos ORM async de Django 4.1+
enc   = await Encomienda.objects.aget(pk=1)
count = await Encomienda.objects.activas().acount()
await enc.asave()

# 3. Clientes HTTP async (httpx)
response = await client.get('https://api.transportista.pe/track/ENC-001')

# 4. asyncio.sleep (sin bloquear)
await asyncio.sleep(5)   # espera 5s sin bloquear el event loop

# 5. asyncio.gather (múltiples corrutinas en paralelo)
a, b, c = await asyncio.gather(f1(), f2(), f3())

# 6. asyncio.wait_for (con timeout)
resultado = await asyncio.wait_for(mi_corrutina(), timeout=3.0)

# ── Lo que NO se puede await ─────────────────────────────────────

# Funciones normales (no son corrutinas)
# await time.sleep(1)             # ERROR: time.sleep no es awaitable

# Queryset síncrono directo
# await Encomienda.objects.all()  # ERROR: no es awaitable
```

---

### `asyncio.gather` — paralelismo en el proyecto

La función `asyncio.gather()` toma múltiples corrutinas y las ejecuta todas a la vez. El resultado es una lista con los resultados en el mismo orden de los argumentos.

**Lab 1 — Dashboard con 4 queries en paralelo** (`envios/views_async.py`):

```python
import asyncio
from django.http import JsonResponse
from django.utils import timezone
from .models import Encomienda

async def dashboard_stats_async(request):
    """
    Endpoint async que calcula las estadísticas del dashboard.
    ANTES (síncrono): 4 queries secuenciales = 4 * 10ms = 40ms
    AHORA (async):    4 queries en paralelo  = max(10ms) = 10ms
    """
    if not request.user.is_authenticated:
        from django.http import HttpResponse
        return HttpResponse(status=401)

    hoy = timezone.now().date()

    # Las 4 queries corren EN PARALELO
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
```

**Verificación masiva en paralelo (`envios/async_services.py`):**

```python
import asyncio
import httpx
from .models import Encomienda

async def verificar_una(session: httpx.AsyncClient, codigo: str) -> dict:
    """Verifica UNA encomienda. Se ejecuta en paralelo con las demás."""
    try:
        r = await session.get(
            f'https://api.transportista.pe/track/{codigo}',
            timeout=5.0
        )
        return {'codigo': codigo, 'ok': True, 'data': r.json()}
    except httpx.TimeoutException:
        return {'codigo': codigo, 'ok': False, 'error': 'timeout'}
    except Exception as e:
        return {'codigo': codigo, 'ok': False, 'error': str(e)}


async def verificar_lote_completo() -> dict:
    """
    Verifica TODAS las encomiendas en tránsito en paralelo.

    SÍNCRONO:   50 encomiendas * 1s por consulta = 50 SEGUNDOS
    ASÍNCRONO:  todas en paralelo               = ~1 SEGUNDO
    """
    encomiendas = await Encomienda.objects.en_transito().alist()

    if not encomiendas:
        return {'verificadas': 0, 'resultados': []}

    print(f'Verificando {len(encomiendas)} encomiendas en paralelo...')

    async with httpx.AsyncClient() as session:
        tareas = [
            verificar_una(session, enc.codigo)
            for enc in encomiendas
        ]
        resultados = await asyncio.gather(*tareas, return_exceptions=True)

    exitosas = [r for r in resultados if isinstance(r, dict) and r['ok']]
    fallidas  = [r for r in resultados if isinstance(r, dict) and not r['ok']]
    errores   = [r for r in resultados if isinstance(r, Exception)]

    return {
        'verificadas': len(encomiendas),
        'exitosas':    len(exitosas),
        'fallidas':    len(fallidas),
        'errores':     len(errores),
        'resultados':  resultados,
    }
```

---

### `asyncio.create_task` — lanzar en segundo plano

A diferencia de `await` que espera a que una corrutina termine, `asyncio.create_task()` la lanza en segundo plano y continúa la ejecución inmediatamente.

```python
import asyncio

async def enviar_notificacion_email(enc, nuevo_estado: str):
    """Envía un email de notificación. Puede tardar 500ms."""
    await asyncio.sleep(0.5)
    print(f'Email enviado: {enc.codigo} -> {nuevo_estado}')


async def cambiar_estado_vista(request, pk: int):
    """
    Vista async que cambia el estado y lanza notificaciones
    en background sin hacer esperar al cliente.
    """
    enc          = await Encomienda.objects.aget(pk=pk)
    nuevo_estado = request.data.get('estado')

    # Paso 1: cambiar el estado (CRÍTICO - el cliente espera esto)
    enc.estado = nuevo_estado
    await enc.asave()

    # Paso 2: lanzar notificaciones en BACKGROUND (no críticas)
    asyncio.create_task(enviar_notificacion_email(enc, nuevo_estado))
    asyncio.create_task(registrar_en_log_externo(enc, nuevo_estado))

    return {'ok': True, 'estado': nuevo_estado}

# Diferencia entre await y create_task:
# CON await:       espera a que el email termine antes de responder  (+500ms)
# CON create_task: responde al cliente y el email se envía después   (+0ms)
```

---

### `asyncio.wait_for` — timeout en operaciones async

La función `asyncio.wait_for()` ejecuta una corrutina con un tiempo límite. Si la corrutina no termina en ese tiempo, lanza `asyncio.TimeoutError`.

```python
import asyncio
from .models import Encomienda

async def verificar_con_timeout(enc) -> dict:
    """
    Verifica una encomienda en la API del transportista.
    Si no responde en 3 segundos, devuelve el último estado conocido.
    """
    try:
        resultado = await asyncio.wait_for(
            verificar_api_externa(enc.codigo),
            timeout=3.0
        )
        return resultado

    except asyncio.TimeoutError:
        return {
            'codigo':      enc.codigo,
            'estado':      enc.get_estado_display(),
            'fuente':      'cache_local',
            'advertencia': 'API del transportista no disponible',
        }


async def verificar_lote_con_timeout(codigos: list) -> list:
    encomiendas = await Encomienda.objects.filter(
        codigo__in=codigos
    ).alist()

    resultados = await asyncio.gather(
        *[verificar_con_timeout(enc) for enc in encomiendas],
        return_exceptions=True
    )

    return [
        r if not isinstance(r, Exception) else {'error': str(r)}
        for r in resultados
    ]
```

---

### ORM Asíncrono de Django

Desde Django 4.1, el ORM tiene equivalentes asíncronos. El prefijo `a` identifica la versión async.

| Método síncrono | Método asíncrono | Ejemplo en el proyecto |
|---|---|---|
| `Model.objects.get()` | `await Model.objects.aget()` | `await Encomienda.objects.aget(pk=1)` |
| `Model.objects.create()` | `await Model.objects.acreate()` | `await Encomienda.objects.acreate(...)` |
| `queryset.first()` | `await qs.afirst()` | `await Encomienda.objects.activas().afirst()` |
| `queryset.count()` | `await queryset.acount()` | `await Encomienda.objects.con_retraso().acount()` |
| `queryset.exists()` | `await queryset.aexists()` | `await Encomienda.objects.filter(codigo=c).aexists()` |
| `obj.save()` | `await obj.asave()` | `enc.estado = 'TR'; await enc.asave()` |
| `obj.delete()` | `await obj.adelete()` | `await enc.adelete()` |
| `list(queryset)` | `await queryset.alist()` | `await Encomienda.objects.en_transito().alist()` |
| `for obj in queryset:` | `async for obj in queryset:` | `async for enc in Encomienda.objects.all():` |

**Iteración async y `sync_to_async`:**

```python
# ── async for: iterar un queryset sin bloquear el event loop ────────
async def procesar_encomiendas_en_transito():
    encomiendas_retrasadas = []

    async for enc in Encomienda.objects.en_transito().select_related('ruta'):
        if enc.tiene_retraso:
            encomiendas_retrasadas.append(enc)

    if encomiendas_retrasadas:
        await asyncio.gather(
            *[notificar_retraso(enc) for enc in encomiendas_retrasadas]
        )

    return len(encomiendas_retrasadas)


# ── sync_to_async: si Django < 4.1 o el ORM no tiene método async ──
from asgiref.sync import sync_to_async

@sync_to_async
def get_encomiendas_activas():
    return list(Encomienda.objects.activas().con_relaciones())

# Uso:
encomiendas = await get_encomiendas_activas()

# Alternativa en línea (sin decorador):
encomiendas = await sync_to_async(
    lambda: list(Encomienda.objects.activas().con_relaciones())
)()
```

---

### Errores Comunes y Cómo Evitarlos

| Error | Causa | Solución |
|---|---|---|
| `SyntaxError: await outside async` | Usar `await` en función sin `async def` | Declarar la función con `async def` |
| `RuntimeError: Event loop is closed` | Llamar `asyncio.run()` dentro de una corrutina | Usar `await` directamente |
| `SynchronousOnlyOperation` | Llamar ORM sync desde contexto async | Usar `aget()`, `acount()` o `sync_to_async` |
| Task fue destruida pero está pendiente | `create_task()` sin guardar la referencia | `task = asyncio.create_task(...)` y guardarla |
| La corrutina nunca se ejecutó | Llamar una corrutina sin `await` ni `create_task` | Siempre `await` o `create_task` una corrutina |

```python
# ── Error 1: ORM síncrono en contexto async ─────────────────────
async def vista_mal(request):
    encs = list(Encomienda.objects.all())  # SynchronousOnlyOperation

async def vista_bien(request):
    encs = await Encomienda.objects.alist()  # correcto


# ── Error 2: await en función síncrona ───────────────────────────
def funcion_sync():
    enc = await Encomienda.objects.aget(pk=1)  # SyntaxError

async def funcion_async():
    enc = await Encomienda.objects.aget(pk=1)  # correcto


# ── Error 3: asyncio.run() dentro de una corrutina ───────────────
async def vista(request):
    enc = asyncio.run(obtener_encomienda(1))  # RuntimeError

async def vista_correcta(request):
    enc = await obtener_encomienda(1)  # correcto


# ── Error 4: corrutina sin await ─────────────────────────────────
async def vista(request):
    enc = Encomienda.objects.aget(pk=1)  # devuelve corrutina, no objeto

async def vista_correcta(request):
    enc = await Encomienda.objects.aget(pk=1)  # objeto real


# ── Error 5: Task destruida antes de terminar ────────────────────
_tasks = set()
async def vista_bien(request):
    task = asyncio.create_task(enviar_email(enc))
    _tasks.add(task)                   # evitar que el GC la destruya
    task.add_done_callback(_tasks.discard)  # limpiar al terminar
```

---

### Resumen — Guía Rápida de Async/Await

```
Declarar una corrutina:       async def mi_funcion():
Esperar una corrutina:        resultado = await mi_corrutina()
Ejecutar varias en paralelo:  a, b = await asyncio.gather(f1(), f2())
Lanzar en background:         asyncio.create_task(mi_corrutina())
Con timeout:                  await asyncio.wait_for(f(), timeout=3.0)
Desde código síncrono:        asyncio.run(mi_corrutina())
ORM async:                    await Encomienda.objects.aget(pk=1)
ORM async count:              await Encomienda.objects.activas().acount()
ORM async guardar:            enc.estado = 'TR'; await enc.asave()
ORM async iterar:             async for enc in Encomienda.objects.all():
Convertir sync a async:       @sync_to_async / sync_to_async(lambda: ...)()
```

**Archivos nuevos en el proyecto:**
- `envios/async_services.py` — `verificar_lote_completo`, `verificar_con_timeout`
- `envios/views_async.py` — `dashboard_stats_async`, `cambiar_estado_vista`

---

## Parte 2 — Introducción a WebSockets

WebSocket es un protocolo de comunicación que permite una conexión bidireccional, persistente y en tiempo real entre un navegador (cliente) y un servidor. A diferencia de HTTP, que requiere una petición por cada respuesta, WebSocket mantiene la conexión abierta, permitiendo el intercambio instantáneo de datos sin necesidad de constantes peticiones nuevas.

**Aspectos clave de WebSocket:**

- **Comunicación Bidireccional:** Tanto el cliente como el servidor pueden enviarse mensajes en cualquier momento.
- **Tiempo Real:** Ideal para aplicaciones que requieren actualizaciones inmediatas — chats, juegos online, marcadores deportivos.
- **Conexión Persistente:** Se establece un "handshake" inicial y la conexión permanece abierta (full-duplex).
- **Eficiencia:** Reduce la latencia y la sobrecarga de datos en comparación con HTTP.
- **Compatibilidad:** Funciona sobre los puertos estándar 80 y 443.

---

### La analogía: teléfono vs walkie-talkie

| HTTP (cartas) | WebSocket (teléfono) |
|---|---|
| El cliente escribe y envía una carta (request) | Ambos marcan el número y establecen la llamada |
| El servidor lee y responde con otra carta | Cualquiera puede hablar en cualquier momento |
| La carta llega y la comunicación termina | La línea se mantiene abierta mientras dure la sesión |
| Para saber si hay respuesta, hay que preguntar de nuevo | El servidor puede hablar sin que el cliente lo solicite |
| Cada carta tiene su propio sobre con dirección (headers) | Solo un «over» al inicio para abrir la línea (handshake) |

---

### El problema: HTTP polling vs WebSocket push

#### El problema del polling con HTTP

El polling HTTP (sondeo) es una técnica donde un cliente pregunta repetidamente a un servidor si hay nuevos datos a intervalos regulares.

**Problemas principales:**
- **Desperdicio de Recursos:** El cliente realiza constantes peticiones HTTP, incluso cuando no hay datos nuevos.
- **Latencia Artificial:** Existe un retraso entre el momento en que los datos cambian y el momento en que el cliente realiza la siguiente petición.
- **Problemas de Escalabilidad:** Con muchos usuarios, miles de peticiones vacías por segundo pueden saturar el servidor.
- **Sobrecarga de Cabeceras HTTP:** Cada petición lleva cabeceras HTTP con datos innecesarios.

```python
# Lo que pasa con polling HTTP en el sistema de encomiendas:
#
# 10:00:00 - Navegador pregunta: GET /api/v1/encomiendas/1/ -> PE (Pendiente)
# 10:00:05 - Navegador pregunta: GET /api/v1/encomiendas/1/ -> PE (sin cambio)
# 10:00:10 - Navegador pregunta: GET /api/v1/encomiendas/1/ -> PE (sin cambio)
# 10:00:18 - Luis cambia el estado a TR en el sistema
# 10:00:20 - Navegador pregunta: GET /api/v1/encomiendas/1/ -> TR (!)
#
# Problemas:
# 1. Demora de hasta 5 segundos para enterarse del cambio
# 2. Con 50 empleados conectados: 50 requests cada 5s = 600 req/min
# 3. La mayoría de esos 600 requests devuelven 'sin cambio' (desperdicio)

# Implementación típica del polling (JavaScript):
setInterval(async () => {
    const r = await fetch('/api/v1/encomiendas/1/');
    const data = await r.json();
    if (data.estado !== estadoAnterior) {
        actualizarUI(data.estado);
        estadoAnterior = data.estado;
    }
}, 5000); // cada 5 segundos

# Con WebSocket: 0 requests hasta que algo cambia
```

#### La solución: WebSocket push

```python
# Lo que ocurre con WebSocket en el sistema de encomiendas:
#
# 10:00:00 - Navegador abre UN WebSocket: ws://localhost/ws/encomiendas/
# 10:00:00 - Servidor acepta la conexión (101 Switching Protocols)
# 10:00:00 - Servidor envía las estadísticas iniciales
#
# ... la conexión está ABIERTA, no se consume red ...
#
# 10:00:18 - Luis cambia ENC-2026-001 de PE a TR
# 10:00:18 - El modelo llama a channel_layer.group_send()
# 10:00:18 - TODOS los navegadores conectados reciben instantáneamente:
#            {tipo: 'estado_cambio', codigo: 'ENC-2026-001',
#             estado_anterior: 'PE', estado_nuevo: 'TR',
#             empleado: 'Mendoza Cruz, Luis'}
#
# Ventajas:
# 1. Notificación en <100ms
# 2. 0 requests adicionales hasta el próximo cambio
# 3. El servidor solo envía cuando hay algo que enviar
```

---

### El ciclo de vida de una conexión WebSocket

#### Fase 1: El Handshake

```
# ── PASO 1: El cliente envía una petición HTTP con cabeceras especiales
GET /ws/encomiendas/ HTTP/1.1
Host: localhost:8000
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13

# ── PASO 2: El servidor acepta y responde 101
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=

# ── PASO 3: La conexión ya no es HTTP ───────────────────────────
```

```python
# envios/consumers.py
class EncomiendaConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add('encomiendas_global', self.channel_name)
        await self.accept()

        stats = await self.get_estadisticas()
        await self.send(text_data=json.dumps({
            'tipo':    'conectado',
            'mensaje': f'Bienvenido, {user.username}',
            'stats':   stats,
        }))
```

#### Fase 2: Comunicación bidireccional

```python
# ── Mensajes del cliente al servidor (receive) ───────────────────
async def receive(self, text_data):
    data = json.loads(text_data)
    if data['tipo'] == 'ping':
        await self.send(text_data=json.dumps({'tipo': 'pong'}))


# ── Mensajes del servidor al cliente (push) ──────────────────────
async def encomienda_estado_cambio(self, event):
    """Handler: recibe del channel layer y reenvía al navegador"""
    await self.send(text_data=json.dumps({
        'tipo':           'estado_cambio',
        'encomienda_id':  event['encomienda_id'],
        'codigo':         event['codigo'],
        'estado_anterior': event['estado_anterior'],
        'estado_nuevo':   event['estado_nuevo'],
        'empleado':       event['empleado'],
        'timestamp':      event['timestamp'],
    }))
```

#### Fase 3: El cierre ordenado

```python
# ── Cierre desde el servidor ─────────────────────────────────────
async def disconnect(self, close_code):
    """Se llama cuando el cliente cierra la conexión"""
    await self.channel_layer.group_discard(
        'encomiendas_global',
        self.channel_name
    )

# ── Cierre desde el cliente (JavaScript) ─────────────────────────
# ws.close(1000, 'Usuario cerró la pestaña');
# ws.onclose = function(event) {
#     if (event.code === 4001) {
#         window.location.href = '/accounts/login/';
#     } else if (event.code !== 1000) {
#         setTimeout(() => location.reload(), 3000);
#     }
# };
```

**Frames WebSocket:**

| Tipo de frame | Uso en el proyecto |
|---|---|
| Text frame (0x1) | Mensajes JSON del sistema (estado_cambio, stats, ping/pong) |
| Binary frame (0x2) | No usado (para imágenes o archivos binarios) |
| Close frame (0x8) | Cierre de conexión con código y razón |
| Ping frame (0x9) | Django Channels envía pings automáticos |
| Pong frame (0xA) | El cliente responde automáticamente a los pings |

---

### La API JavaScript del WebSocket

**Los 4 eventos del WebSocket:**

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/encomiendas/');

// ── onopen: conexión establecida ─────────────────────────────────
ws.onopen = function(event) {
    console.log('Conectado!');
    document.getElementById('ws-badge').textContent = 'EN VIVO';
    document.getElementById('ws-badge').classList.add('text-success');
    ws.send(JSON.stringify({ tipo: 'solicitar_stats' }));
};

// ── onmessage: mensaje recibido del servidor ──────────────────────
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);

    switch(data.tipo) {
        case 'conectado':
            actualizarDashboard(data.stats);
            break;

        case 'estado_cambio':
            mostrarNotificacion(data.codigo, data.estado_anterior, data.estado_nuevo, data.empleado, data.timestamp);
            actualizarFilaTabla(data.codigo, data.estado_nuevo);
            break;

        case 'stats_actualizado':
            actualizarDashboard(data.stats);
            break;

        case 'progreso':
            const pct = Math.round(data.actual / data.total * 100);
            actualizarBarra(pct, data.codigo);
            break;
    }
};

// ── onclose: conexión cerrada ─────────────────────────────────────
ws.onclose = function(event) {
    if (event.code === 4001) {
        window.location.href = '/accounts/login/';
    } else if (event.code !== 1000 && event.code !== 1001) {
        setTimeout(() => { const nuevoWs = new WebSocket(ws.url); }, 3000);
    }
};

// ── onerror: error de red ─────────────────────────────────────────
ws.onerror = function(error) {
    console.error('Error WebSocket:', error);
};
```

**Códigos de cierre:**

| Código | Nombre | Cuándo ocurre |
|---|---|---|
| 1000 | Normal closure | El empleado cerró sesión voluntariamente |
| 1001 | Going away | El empleado cerró la pestaña |
| 1006 | Abnormal closure | Perdió la conexión a internet |
| 1011 | Internal error | Error no controlado en un consumer |
| 4001 | No autorizado | El usuario no está autenticado (personalizado) |
| 4002 | Sesión expirada | El token JWT expiró (personalizado) |

---

### Resumen — Conceptos Clave de WebSockets

```
Qué es: protocolo de comunicación bidireccional y persistente sobre TCP.

Diferencia con HTTP:
  HTTP:      el cliente pregunta, el servidor responde, la conexión se cierra.
  WebSocket: la conexión queda abierta, cualquiera puede enviar mensajes.

El handshake:
  1. Cliente envía GET con Upgrade: websocket
  2. Servidor responde 101 Switching Protocols
  3. La conexión TCP ya no habla HTTP, habla WebSocket frames
  4. Django Channels llama a connect() del consumer

Los 4 eventos del cliente JavaScript:
  onopen:    la conexión se estableció correctamente
  onmessage: llegó un mensaje del servidor (event.data = JSON string)
  onclose:   la conexión se cerró (event.code indica el motivo)
  onerror:   error de red (seguido siempre de onclose)

En el proyecto de encomiendas:
  ws://localhost:8000/ws/encomiendas/        <- notificaciones globales
  ws://localhost:8000/ws/encomiendas/{pk}/   <- una encomienda específica
  ws://localhost:8000/ws/dashboard/          <- estadísticas en tiempo real
```

---

## Parte 3 — Ejemplo Completo: Dashboard en Tiempo Real

### Qué hace este ejemplo

1. El navegador abre una conexión WebSocket al cargar el dashboard.
2. El servidor (Django Channels) acepta la conexión y envía las estadísticas iniciales.
3. Cuando cualquier empleado cambia el estado de una encomienda, el modelo notifica al channel layer.
4. Channels distribuye la notificación a TODOS los navegadores conectados.
5. Cada navegador actualiza los contadores y muestra un toast sin recargar la página.

### Paso 1 — Template del dashboard

```html
{% extends 'base.html' %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
  <h2>Dashboard</h2>
  <span id="ws-badge" class="badge bg-secondary">Conectando...</span>
</div>

<div class="row g-3 mb-4">
  <div class="col-md-3">
    <div class="card shadow-sm">
      <div class="card-body text-center">
        <div class="fs-2 fw-bold text-primary" id="stat-activas">{{ stats.activas }}</div>
        <div class="text-muted">Activas</div>
      </div>
    </div>
  </div>
  <!-- ... más tarjetas ... -->
</div>

<div class="card shadow-sm">
  <div class="card-header">Feed de actividad</div>
  <ul class="list-group list-group-flush" id="feed-lista">
    <li class="list-group-item text-muted">Esperando eventos...</li>
  </ul>
</div>
{% endblock %}
```

```javascript
{% block extra_js %}
<script>
const WS_URL = 'ws://' + window.location.host + '/ws/dashboard/';
let ws;

function conectarWebSocket() {
    ws = new WebSocket(WS_URL);

    ws.onopen = function() {
        document.getElementById('ws-badge').textContent = 'EN VIVO';
        document.getElementById('ws-badge').className = 'badge bg-success';
    };

    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);

        if (data.tipo === 'stats_iniciales' || data.tipo === 'stats_actualizado') {
            actualizarContador('stat-activas',     data.stats.activas);
            actualizarContador('stat-en-transito', data.stats.en_transito);
            actualizarContador('stat-retraso',     data.stats.con_retraso);
            actualizarContador('stat-entregadas',  data.stats.entregadas_hoy);
        }

        if (data.tipo === 'estado_cambio') {
            agregarAlFeed(data);
            mostrarToast(data);
        }
    };

    ws.onclose = function(event) {
        document.getElementById('ws-badge').textContent = 'Desconectado';
        document.getElementById('ws-badge').className = 'badge bg-danger';
        if (event.code !== 1000) {
            setTimeout(conectarWebSocket, 3000);
        }
    };
}

document.addEventListener('DOMContentLoaded', conectarWebSocket);
</script>
{% endblock %}
```

### Paso 2 — Vista del dashboard

```python
# envios/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from .models import Encomienda

@login_required
def dashboard(request):
    hoy = timezone.now().date()
    context = {
        'stats': {
            'activas':        Encomienda.objects.activas().count(),
            'en_transito':    Encomienda.objects.en_transito().count(),
            'con_retraso':    Encomienda.objects.con_retraso().count(),
            'entregadas_hoy': Encomienda.objects.filter(
                estado='EN', fecha_entrega_real=hoy
            ).count(),
        }
    }
    return render(request, 'envios/dashboard.html', context)
```

### Paso 3 — Consumer del dashboard

```python
# envios/consumers.py
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
```

### Paso 4 — El modelo notifica al cambiar el estado

```python
# envios/models.py
def _notificar_cambio_estado(self, estado_anterior, estado_nuevo, empleado):
    from django.utils import timezone
    channel_layer = get_channel_layer()

    mensaje = {
        'encomienda_id':    self.pk,
        'codigo':           self.codigo,
        'estado_anterior':  estado_anterior,
        'estado_nuevo':     estado_nuevo,
        'empleado':         str(empleado),
        'timestamp':        timezone.now().isoformat(),
    }

    # Notificar al grupo global
    async_to_sync(channel_layer.group_send)(
        'encomiendas_global',
        {'type': 'encomienda_estado_cambio', **mensaje}
    )

    # Notificar al dashboard con estadísticas actualizadas
    stats = {
        'activas':     Encomienda.objects.activas().count(),
        'en_transito': Encomienda.objects.en_transito().count(),
        'con_retraso': Encomienda.objects.con_retraso().count(),
    }
    async_to_sync(channel_layer.group_send)(
        'dashboard',
        {'type': 'dashboard_actualizar', 'stats': stats}
    )
```

### Flujo completo de notificación WebSocket

```
1. Empleado usa la API REST: POST /api/v1/encomiendas/1/cambiar_estado/
2. El ViewSet llama a enc.cambiar_estado('TR', empleado, obs)
3. El modelo guarda en BD y registra en HistorialEstado
4. El modelo llama a _notificar_cambio_estado():
   channel_layer.group_send('encomiendas_global', {...})
   channel_layer.group_send('dashboard', {stats: {...}})
5. Django Channels distribuye a todos los consumers conectados
6. Cada consumer envía el mensaje a su WebSocket
7. El navegador recibe en onmessage y actualiza la UI
   - Contador se anima y actualiza
   - Toast aparece con la notificación
   - Feed muestra el nuevo evento

Todo esto ocurre en < 100ms desde el cambio hasta la actualización
en todos los navegadores conectados, sin ninguna recarga de página.
```

**Archivos del ejemplo:**

| Archivo | Acción |
|---|---|
| `templates/envios/dashboard.html` | Estructura HTML + bloque `extra_js` |
| `envios/views.py` | Vista `dashboard()` con stats iniciales |
| `envios/urls.py` | Ruta del dashboard |
| `envios/consumers.py` | `DashboardConsumer` (ya implementado) |
| `envios/models.py` | `_notificar_cambio_estado()` (ya implementado) |
| `envios/routing.py` | URL `ws/dashboard/` (ya implementado) |
| `config/asgi.py` | `ProtocolTypeRouter` (ya implementado) |
| `config/settings.py` | `CHANNEL_LAYERS`, daphne (ya implementado) |
| `docker-compose.yml` | Servicio redis (ya implementado) |

---

## Parte 4 — Django Channels

Django Channels es un proyecto oficial que amplía las capacidades de Django para manejar protocolos asíncronos y de larga duración, como WebSockets, MQTT y otros protocolos de mensajería.

### Arquitectura de Django Channels

Django Channels extiende Django añadiendo una capa asíncrona sobre ASGI. Introduce tres conceptos nuevos: **consumers** (equivalente de las vistas), el **channel layer** (bus de mensajes entre consumers), y los **grupos** (conjuntos de consumers que reciben el mismo mensaje).

**Conceptos clave:**

| Concepto | Equivalente en Django | Descripción en el proyecto |
|---|---|---|
| Consumer | Vista (View) | Clase que maneja una conexión WebSocket: connect, receive, disconnect |
| Channel | Hilo de ejecución | Canal único de comunicación. Cada cliente tiene uno |
| Group | Sala / canal público | Conjunto de channels. `encomiendas_global` incluye a todos los empleados |
| Channel Layer | Base de datos | Bus de mensajes (Redis) que conecta consumers de distintos servidores |
| Scope | Request object | Diccionario con información de la conexión: usuario, URL, headers |
| ASGI | WSGI | Protocolo asíncrono que reemplaza a WSGI para soportar WebSockets |

---

### Tipos de Consumer

#### `AsyncWebsocketConsumer` — el consumer principal

```python
# envios/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

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
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def encomienda_estado_cambio(self, event):
        """
        Se llama cuando alguien hace:
            channel_layer.group_send('encomiendas_global', {
                'type': 'encomienda_estado_cambio',
                ...datos...
            })
        IMPORTANTE: 'type' usa puntos en lugar de underscores:
          'encomienda.estado.cambio' -> encomienda_estado_cambio()
        """
        await self.send(text_data=json.dumps({
            'tipo':           'estado_cambio',
            'encomienda_id':  event['encomienda_id'],
            'codigo':         event['codigo'],
            'estado_anterior': event['estado_anterior'],
            'estado_nuevo':   event['estado_nuevo'],
            'empleado':       event['empleado'],
            'timestamp':      event['timestamp'],
        }))

    @database_sync_to_async
    def get_estadisticas(self):
        from .models import Encomienda
        return {
            'activas':     Encomienda.objects.activas().count(),
            'en_transito': Encomienda.objects.en_transito().count(),
            'con_retraso': Encomienda.objects.con_retraso().count(),
        }
```

#### `AsyncJsonWebsocketConsumer` — sin `json.loads/dumps` manual

```python
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class EncomiendaJsonConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close(code=4001)
            return
        self.group_name = 'encomiendas_global'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        stats = await self.get_estadisticas()
        await self.send_json({'tipo': 'conectado', 'stats': stats})

    async def receive_json(self, content, **kwargs):
        # content ya es un dict, no hay que hacer json.loads()
        tipo = content.get('tipo')
        if tipo == 'ping':
            await self.send_json({'tipo': 'pong'})
        elif tipo == 'solicitar_stats':
            stats = await self.get_estadisticas()
            await self.send_json({'tipo': 'stats', 'stats': stats})

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
```

---

### El Channel Layer en Profundidad

El channel layer es la capa de mensajería que conecta consumers entre sí, incluso si están en distintos procesos o servidores. Redis actúa como intermediario.

**Las 4 operaciones del channel layer:**

```python
from channels.layers import get_channel_layer
channel_layer = get_channel_layer()

# 1. group_add: unir un channel a un grupo (en connect())
await channel_layer.group_add(
    'encomiendas_global',
    self.channel_name
)

# 2. group_discard: quitar un channel de un grupo (en disconnect())
await channel_layer.group_discard(
    'encomiendas_global',
    self.channel_name
)

# 3. group_send: enviar un mensaje a TODOS los channels del grupo
await channel_layer.group_send(
    'encomiendas_global',
    {
        'type':          'encomienda_estado_cambio',  # -> handler
        'encomienda_id': enc.pk,
        'codigo':        enc.codigo,
        'estado_anterior': anterior,
        'estado_nuevo':  nuevo,
        'empleado':      str(empleado),
        'timestamp':     timezone.now().isoformat(),
    }
)

# 4. send: enviar a UN channel específico
await channel_layer.send(
    'specific.channel.name',
    {'type': 'chat.message', 'message': 'Hola'}
)
```

**Llamar al channel layer desde código síncrono (el modelo):**

```python
# envios/models.py
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

class Encomienda(models.Model):

    def _notificar_websocket(self, estado_anterior, estado_nuevo, empleado):
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        mensaje = {
            'type':           'encomienda_estado_cambio',
            'encomienda_id':  self.pk,
            'codigo':         self.codigo,
            'estado_anterior': estado_anterior,
            'estado_nuevo':   estado_nuevo,
            'empleado':       str(empleado),
            'timestamp':      timezone.now().isoformat(),
        }

        async_to_sync(channel_layer.group_send)('encomiendas_global', mensaje)
        async_to_sync(channel_layer.group_send)(f'encomienda_{self.pk}', mensaje)

        stats = {
            'activas':     Encomienda.objects.activas().count(),
            'en_transito': Encomienda.objects.en_transito().count(),
            'con_retraso': Encomienda.objects.con_retraso().count(),
        }
        async_to_sync(channel_layer.group_send)(
            'dashboard',
            {'type': 'dashboard_actualizar', 'stats': stats}
        )
```

---

### Routing — Cómo Channels Enruta Conexiones

```python
# envios/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/encomiendas/$',
            consumers.EncomiendaConsumer.as_asgi(),
            name='ws-encomiendas'),

    re_path(r'^ws/encomiendas/(?P<pk>\d+)/$',
            consumers.EncomiendaDetalleConsumer.as_asgi(),
            name='ws-encomienda-detalle'),

    re_path(r'^ws/dashboard/$',
            consumers.DashboardConsumer.as_asgi(),
            name='ws-dashboard'),
]
```

```python
# config/asgi.py
import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from envios.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
```

---

### Autenticación y Permisos en WebSockets

**Autenticación por JWT — middleware personalizado:**

```python
# channels_middleware.py
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from urllib.parse import parse_qs

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token_string):
    try:
        token   = AccessToken(token_string)
        user_id = token['user_id']
        return User.objects.get(pk=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    El token llega como parámetro de la URL:
    ws://localhost:8000/ws/encomiendas/?token=eyJhbGci...
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            query_string = scope.get('query_string', b'').decode('utf-8')
            params     = parse_qs(query_string)
            token_list   = params.get('token', [])

            if token_list:
                scope['user'] = await get_user_from_token(token_list[0])
            else:
                scope['user'] = AnonymousUser()

        return await self.inner(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))
```

---

### `database_sync_to_async` — ORM en Consumers

```python
from channels.db import database_sync_to_async

class EncomiendaConsumer(AsyncWebsocketConsumer):

    # ── Patrón 1: decorador @database_sync_to_async ──────────────
    @database_sync_to_async
    def get_encomiendas_activas(self):
        from .models import Encomienda
        return list(Encomienda.objects.activas().con_relaciones())

    # ── Patrón 2: sync_to_async inline ────────────────────────────
    async def receive(self, text_data):
        from asgiref.sync import sync_to_async
        count = await sync_to_async(
            lambda: Encomienda.objects.activas().count()
        )()

    # ── Patrón 3: ORM async nativo (Django 4.1+) ─────────────────
    async def receive(self, text_data):
        count = await Encomienda.objects.activas().acount()
        enc   = await Encomienda.objects.aget(pk=1)
        encs  = await Encomienda.objects.en_transito().alist()
        await enc.asave()
```

---

### Testing de Consumers

```python
# envios/tests/test_consumers.py
import pytest
import json
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from config.asgi import application

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestEncomiendaConsumer:

    async def test_conexion_sin_autenticacion(self):
        """Sin autenticar: el servidor debe rechazar con código 4001"""
        communicator = WebsocketCommunicator(application, '/ws/encomiendas/')
        connected, code = await communicator.connect()
        assert not connected
        assert code == 4001
        await communicator.disconnect()

    async def test_ping_pong(self):
        """El consumer responde pong al recibir ping"""
        user = await database_sync_to_async(UserFactory)()
        communicator = WebsocketCommunicator(application, '/ws/encomiendas/')
        communicator.scope['user'] = user

        await communicator.connect()
        await communicator.receive_json_from(timeout=2)  # bienvenida

        await communicator.send_json_to({'tipo': 'ping'})
        response = await communicator.receive_json_from(timeout=2)
        assert response['tipo'] == 'pong'

        await communicator.disconnect()

    async def test_notificacion_via_channel_layer(self):
        """El consumer recibe y reenvía mensajes del channel layer"""
        user = await database_sync_to_async(UserFactory)()
        communicator = WebsocketCommunicator(application, '/ws/encomiendas/')
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
```

---

### Manejo de Errores y Reconexión

**Reconexión con backoff exponencial (JavaScript):**

```javascript
class EncomiendaWebSocket {
    constructor(url) {
        this.url       = url;
        this.intentos  = 0;
        this.maxIntentos = 10;
        this.baseDelay = 1000;
    }

    conectar() {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
            this.intentos = 0;
            document.getElementById('ws-badge').textContent = 'EN VIVO';
            document.getElementById('ws-badge').className = 'badge bg-success';
        };

        this.ws.onclose = (event) => {
            if (event.code === 4001) {
                window.location.href = '/accounts/login/';
                return;
            }
            if (event.code === 1000) return;

            // Backoff exponencial: 1s, 2s, 4s, 8s, ... max 30s
            const delay = Math.min(
                this.baseDelay * Math.pow(2, this.intentos),
                30000
            );
            this.intentos++;
            if (this.intentos <= this.maxIntentos) {
                setTimeout(() => this.conectar(), delay);
            }
        };
    }

    enviar(data) {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }
}

// Uso:
const wsEnc = new EncomiendaWebSocket(
    'ws://' + window.location.host + '/ws/encomiendas/'
);
wsEnc.onMensaje = (data) => {
    if (data.tipo === 'estado_cambio') mostrarToast(data);
    if (data.tipo === 'stats_actualizado') actualizarDashboard(data.stats);
};
wsEnc.conectar();
```

---

### Entregable — Django Channels en Profundidad

Al finalizar debes poder demostrar:

**Consumers:**
1. `EncomiendaConsumer`: autenticación en `connect()`, 3 tipos de mensaje en `receive()`, `group_add/discard` en connect/disconnect, handler de grupo.
2. `EncomiendaDetalleConsumer`: grupo dinámico por pk, verificar existencia, enviar estado actual al conectarse.
3. `DashboardConsumer`: grupo `'dashboard'`, stats iniciales, handler `dashboard_actualizar`.
4. Todos los consumers usan `@database_sync_to_async` para el ORM.

**Channel Layer:**
5. `group_add/group_discard` en connect/disconnect de cada consumer.
6. `group_send` desde el modelo con `async_to_sync`.
7. Los tres grupos funcionan independientemente.

**Autenticación:**
8. `AuthMiddlewareStack` llena `self.scope['user']` para sesiones web.
9. `JWTAuthMiddleware` lee el token del query string para la API REST.
10. Conexiones sin autenticar se rechazan con código 4001.

**Testing:**
11. 4 tests con `WebsocketCommunicator`: sin auth, conectado, ping/pong, notificación via channel layer.
12. `InMemoryChannelLayer` en settings.py para tests sin Redis.

**Reconexión:**
13. El cliente JavaScript reconecta con backoff exponencial.
14. El badge cambia a `'EN VIVO'`, `'Reconectando...'` o `'Desconectado'`.
15. La reconexión NO se ejecuta para códigos 4001 (no autorizado) ni 1000 (normal).

---

## Parte 5 — Redis como Channel Layer

### ¿Qué es Redis y por qué se usa como Channel Layer?

Redis (Remote Dictionary Server) es una base de datos en memoria, de clave-valor, extremadamente rápida. Puede persistir datos en disco, soporta estructuras de datos avanzadas (listas, sets, hashes, streams) y tiene un sistema de Pub/Sub nativo que lo hace ideal como bus de mensajería.

**El problema del escalado horizontal:**

```
# ESCENARIO SIN REDIS: dos instancias del servidor
#
# Servidor A — Juan y María conectados via WebSocket
# Servidor B — Pedro conectado via WebSocket
#
# Luis cambia ENC-2026-001 (petición llega al Servidor A)
# channel_layer.group_send('encomiendas_global', ...)
#
# Sin Redis: el channel layer de A solo conoce los consumers de A
#   -> Juan recibe la notificación  [OK]
#   -> María recibe la notificación [OK]
#   -> Pedro NO recibe nada         [PROBLEMA]
#
# Con Redis: todos los servidores comparten el mismo Redis
#   -> Juan, María y Pedro reciben la notificación [OK]
```

**InMemoryChannelLayer vs RedisChannelLayer:**

| Característica | InMemoryChannelLayer | RedisChannelLayer |
|---|---|---|
| Almacenamiento | RAM del proceso Python | Redis Server (proceso separado) |
| Escala horizontal | No: cada proceso es una isla | Sí: todos comparten Redis |
| Persistencia | Se pierde al reiniciar | Configurable (RDB/AOF) |
| Velocidad | Muy rápida (misma RAM) | Rápida (~1ms de latencia) |
| Cuándo usar | Tests y desarrollo solo | Producción |

---

### Instalación y Configuración Paso a Paso

**Paso 1 — `requirements.txt`:**

```
channels==4.0.0
daphne==4.0.0
channels-redis==4.1.0
redis==5.0.1
```

**Paso 2 — `docker-compose.yml`:**

```yaml
services:
  web:
    build: .
    command: daphne -b 0.0.0.0 -p 8000 config.asgi:application
    depends_on:
      - db
      - redis
    environment:
      - REDIS_URL=redis://redis:6379/1

  db:
    image: postgres:15-alpine

  redis:
    image: redis:7-alpine
    ports:
      - '6379:6379'
    volumes:
      - redis_data:/data
      - ./redis.conf:/usr/local/etc/redis/redis.conf
    command: redis-server /usr/local/etc/redis/redis.conf
    healthcheck:
      test: ['CMD', 'redis-cli', 'ping']
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:
```

**Paso 3 — `redis.conf`:**

```
bind 0.0.0.0
port 6379
tcp-keepalive 60

maxmemory 256mb
maxmemory-policy allkeys-lru

save 900 1
save 300 10
save 60 10000
dbfilename dump.rdb
dir /data

loglevel notice
logfile ''
databases 16
timeout 0
```

**Paso 4 — `config/settings.py`:**

```python
import sys

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/1')

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts':         [REDIS_URL],
            'capacity':      100,
            'expiry':        60,
            'prefix':        'encomiendas',
            'group_expiry':  86400,
        },
    },
}

# Channel Layer en memoria (solo para tests)
if 'pytest' in sys.modules or 'test' in sys.argv:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }
```

**Paso 5 — Verificación:**

```bash
docker compose down
docker compose build
docker compose up -d

# Verificar servicios
docker compose ps

# Verificar Redis
docker compose exec redis redis-cli ping
# PONG

# Verificar desde Django
docker compose exec web python manage.py shell
>>> from channels.layers import get_channel_layer
>>> from asgiref.sync import async_to_sync
>>> cl = get_channel_layer()
>>> async_to_sync(cl.group_send)('test_grupo', {'type': 'test.mensaje'})
```

---

### Opciones de Configuración del Channel Layer

| Opción | Valor por defecto | Descripción |
|---|---|---|
| `hosts` | `[('localhost', 6379)]` | Lista de URLs o tuplas de Redis |
| `prefix` | `"asgi"` | Prefijo para todas las claves en Redis |
| `expiry` | `60` | Segundos antes de que un mensaje sin leer expire |
| `group_expiry` | `86400` | Segundos antes de que un grupo inactivo expire (24h) |
| `capacity` | `100` | Max mensajes en la cola de un canal |
| `channel_capacity` | `{}` | Capacidad por canal individual |
| `symmetric_encryption_keys` | `None` | Claves para cifrar mensajes en Redis |

---

### Grupos en Redis — Cómo se Almacenan

```bash
# Ver todas las claves del proyecto
docker compose exec redis redis-cli -n 1
> KEYS encomiendas:*
1) "encomiendas:group:encomiendas_global"
2) "encomiendas:group:dashboard"
3) "encomiendas:specific.EncomiendaConsumer!a1b2c3"

# Ver cuántos empleados están conectados
> SCARD encomiendas:group:encomiendas_global
(integer) 3

# Ver los channel_names conectados
> SMEMBERS encomiendas:group:dashboard
1) "DashboardConsumer!d4e5f6"

# Ver el TTL de un grupo
> TTL encomiendas:group:encomiendas_global
(integer) 85234
```

---

### Monitoreo de Redis

**Comandos de diagnóstico:**

```bash
# Información general
docker compose exec redis redis-cli INFO

# Estadísticas por base de datos
docker compose exec redis redis-cli INFO keyspace

# Clientes conectados
docker compose exec redis redis-cli INFO clients

# Uso de memoria
docker compose exec redis redis-cli INFO memory

# Monitor en tiempo real (usar con cuidado en producción)
docker compose exec redis redis-cli MONITOR

# Latencia
docker compose exec redis redis-cli --latency
```

**Endpoint de salud del sistema:**

```python
# envios/views.py
import redis
from django.http import JsonResponse

def health_check(request):
    estado = {'postgres': False, 'redis': False, 'channels': False}

    try:
        from django.db import connection
        connection.ensure_connection()
        estado['postgres'] = True
    except Exception as e:
        estado['postgres_error'] = str(e)

    try:
        r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        info = r.info()
        estado['redis']          = True
        estado['redis_memoria']  = info.get('used_memory_human')
        estado['redis_clientes'] = info.get('connected_clients')
        estado['empleados_conectados'] = r.scard('encomiendas:group:encomiendas_global')
    except Exception as e:
        estado['redis_error'] = str(e)

    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        cl = get_channel_layer()
        async_to_sync(cl.group_send)('health_check', {'type': 'health.ping'})
        estado['channels'] = True
    except Exception as e:
        estado['channels_error'] = str(e)

    todo_ok = all([estado['postgres'], estado['redis'], estado['channels']])
    return JsonResponse(estado, status=200 if todo_ok else 503)
```

---

### Problemas Comunes y Soluciones

| Problema | Causa probable | Solución |
|---|---|---|
| `ConnectionRefusedError` al iniciar | Redis no está corriendo | `docker compose up -d redis` |
| Los consumers no reciben mensajes | Prefijo incorrecto en `CHANNEL_LAYERS` | Verificar que `'prefix'` coincide en settings y redis.conf |
| Mensajes se descartan (capacity exceeded) | Consumer muy lento o `capacity` muy bajo | Aumentar `'capacity'` |
| Grupos no se limpian (memory leak) | `group_discard()` no se llama en disconnect | Asegurarse de llamar `group_discard` en `disconnect()` |
| Redis usa demasiada memoria | Demasiados canales o mensajes pendientes | Revisar `maxmemory` y `maxmemory-policy` en redis.conf |
| Latencia alta en notificaciones | Redis en servidor distinto o sobrecargado | Colocar Redis cerca del servidor web |
| `ImproperlyConfigured` | `CHANNEL_LAYERS` no configurado | Agregar el bloque `CHANNEL_LAYERS` a settings.py |

**Diagnosnicar mensajes perdidos:**

```bash
# 1. Verificar que Redis está corriendo
docker compose exec redis redis-cli ping

# 2. Verificar desde Django
docker compose exec web python manage.py shell
>>> cl = get_channel_layer()
>>> print(cl)   # debe mostrar RedisChannelLayer

# 3. Verificar que los grupos existen en Redis
docker compose exec redis redis-cli -n 1
> KEYS encomiendas:group:*

# 4. Ver logs de Daphne en tiempo real
docker compose logs -f web
```
