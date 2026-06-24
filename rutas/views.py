from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Ruta
from .forms import RutaForm


@login_required
def ruta_list(request):
    q = request.GET.get('q')
    rutas_list = Ruta.objects.all()
    if q:
        rutas_list = rutas_list.filter(
            codigo__icontains=q
        ) | rutas_list.filter(
            origen__icontains=q
        ) | rutas_list.filter(
            destino__icontains=q
        )

    paginator = Paginator(rutas_list, 15)
    page_number = request.GET.get('page')
    rutas = paginator.get_page(page_number)
    return render(request, 'rutas/list.html', {'rutas': rutas})


@login_required
def ruta_detail(request, pk):
    ruta = get_object_or_404(Ruta, pk=pk)
    return render(request, 'rutas/detail.html', {'ruta': ruta})


@login_required
def ruta_create(request):
    if request.method == 'POST':
        form = RutaForm(request.POST)
        if form.is_valid():
            ruta = form.save()
            messages.success(request, 'Ruta creada correctamente.')
            return redirect('ruta_detail', pk=ruta.pk)
    else:
        form = RutaForm()

    return render(request, 'rutas/form.html', {'form': form})


@login_required
def ruta_edit(request, pk):
    ruta = get_object_or_404(Ruta, pk=pk)
    if request.method == 'POST':
        form = RutaForm(request.POST, instance=ruta)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ruta actualizada correctamente.')
            return redirect('ruta_detail', pk=ruta.pk)
    else:
        form = RutaForm(instance=ruta)

    return render(request, 'rutas/form.html', {'form': form, 'ruta': ruta})


@login_required
def ruta_delete(request, pk):
    ruta = get_object_or_404(Ruta, pk=pk)
    if request.method == 'POST':
        ruta.estado = 9
        ruta.save()
        messages.success(request, f'Ruta {ruta.codigo} desactivada.')
        return redirect('ruta_list')
    return render(request, 'rutas/confirm_delete.html', {'ruta': ruta})
