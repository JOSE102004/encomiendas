from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Encomienda
from .forms import EncomiendaForm
from clientes.models import Cliente

@login_required
def home(request):
    """Vista para la página principal"""
    total_encomiendas = Encomienda.objects.count()
    total_clientes = Cliente.objects.count()
    envios_hoy = Encomienda.objects.filter(fecha_registro__date=timezone.now().date()).count()
    pendientes = Encomienda.objects.filter(estado='PE').count()
    
    context = {
        'total_encomiendas': total_encomiendas,
        'total_clientes': total_clientes,
        'envios_hoy': envios_hoy,
        'pendientes': pendientes,
    }
    return render(request, 'core/index.html', context)

@login_required
def encomienda_list(request):
    """Vista para listar encomiendas"""
    encomiendas_list = Encomienda.objects.all()
    
    # Filtro rápido
    q = request.GET.get('q')
    if q:
        encomiendas_list = encomiendas_list.filter(descripcion__icontains=q) | encomiendas_list.filter(codigo__icontains=q)
    
    # Paginación
    paginator = Paginator(encomiendas_list, 10)
    page_number = request.GET.get('page')
    encomiendas = paginator.get_page(page_number)
    
    return render(request, 'encomiendas/list.html', {'encomiendas': encomiendas})

@login_required
def encomienda_detail(request, pk):
    """Vista para ver el detalle de una encomienda"""
    encomienda = get_object_or_404(Encomienda, pk=pk)
    return render(request, 'encomiendas/detail.html', {'encomienda': encomienda})

@login_required
def encomienda_create(request):
    """Vista para crear una nueva encomienda"""
    if request.method == 'POST':
        form = EncomiendaForm(request.POST)
        if form.is_valid():
            encomienda = form.save()
            messages.success(request, 'Encomienda creada correctamente.')
            return redirect('encomienda_detail', pk=encomienda.pk)
    else:
        form = EncomiendaForm()
    
    return render(request, 'encomiendas/form.html', {'form': form})

@login_required
def encomienda_edit(request, pk):
    """Vista para editar una encomienda existente"""
    encomienda = get_object_or_404(Encomienda, pk=pk)
    if request.method == 'POST':
        form = EncomiendaForm(request.POST, instance=encomienda)
        if form.is_valid():
            form.save()
            messages.success(request, 'Encomienda actualizada correctamente.')
            return redirect('encomienda_detail', pk=encomienda.pk)
    else:
        form = EncomiendaForm(instance=encomienda)
    return render(request, 'encomiendas/form.html', {'form': form, 'encomienda': encomienda})

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
