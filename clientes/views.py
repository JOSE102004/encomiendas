from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Cliente
from .forms import ClienteForm


@login_required
def cliente_list(request):
    q = request.GET.get('q')
    clientes_list = Cliente.objects.all()
    if q:
        clientes_list = clientes_list.filter(
            nombres__icontains=q
        ) | clientes_list.filter(
            apellidos__icontains=q
        ) | clientes_list.filter(
            nro_doc__icontains=q
        )

    paginator = Paginator(clientes_list, 15)
    page_number = request.GET.get('page')
    clientes = paginator.get_page(page_number)
    return render(request, 'clientes/list.html', {'clientes': clientes})


@login_required
def cliente_detail(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    return render(request, 'clientes/detail.html', {'cliente': cliente})


@login_required
def cliente_create(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, 'Cliente creado correctamente.')
            return redirect('cliente_detail', pk=cliente.pk)
    else:
        form = ClienteForm()

    return render(request, 'clientes/form.html', {'form': form})


@login_required
def cliente_edit(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente actualizado correctamente.')
            return redirect('cliente_detail', pk=cliente.pk)
    else:
        form = ClienteForm(instance=cliente)

    return render(request, 'clientes/form.html', {'form': form, 'cliente': cliente})


@login_required
def cliente_delete(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        cliente.estado = 9
        cliente.save()
        messages.success(request, f'Cliente {cliente.nombre_completo} desactivado.')
        return redirect('cliente_list')
    return render(request, 'clientes/confirm_delete.html', {'cliente': cliente})
