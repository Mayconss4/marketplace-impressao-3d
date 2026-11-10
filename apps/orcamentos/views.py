from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import FormularioAceite, FormularioOrcamento
from .models import Orcamento


def _do_comprador(request, pk):
    return get_object_or_404(
        Orcamento.objects.select_related("vendedor__loja"), pk=pk, comprador=request.user
    )


@login_required
def lista(request):
    orcamentos = Orcamento.objects.filter(comprador=request.user).select_related("vendedor__loja")
    status = request.GET.get("status", "")
    if status in Orcamento.Status.values:
        orcamentos = orcamentos.filter(status=status)
    contexto = {"orcamentos": orcamentos, "status": status, "opcoes_status": Orcamento.Status.choices}
    return render(request, "orcamentos/lista.html", contexto)


@login_required
def novo(request):
    inicial = {"vendedor": request.GET.get("vendedor"), "quantidade": 1}
    form = FormularioOrcamento(request.POST or None, request.FILES or None, comprador=request.user, initial=inicial)
    if request.method == "POST" and form.is_valid():
        orcamento = form.save()
        messages.success(request, f"Orçamento #{orcamento.pk} enviado para {orcamento.vendedor.loja.nome}.")
        return redirect("orcamentos:detalhe", orcamento.pk)
    return render(request, "orcamentos/novo.html", {"form": form})


@login_required
def detalhe(request, pk):
    orcamento = _do_comprador(request, pk)
    contexto = {"orcamento": orcamento, "form_aceite": FormularioAceite(comprador=request.user)}
    return render(request, "orcamentos/detalhe.html", contexto)


@login_required
@require_POST
def aceitar(request, pk):
    orcamento = _do_comprador(request, pk)
    form = FormularioAceite(request.POST, comprador=request.user)
    if not form.is_valid():
        messages.error(request, "Escolha um endereço de entrega válido.")
        return redirect("orcamentos:detalhe", pk)
    try:
        pedido = orcamento.aceitar(request.user, form.cleaned_data["endereco"])
    except ValidationError as erro:
        for mensagem in erro.messages:
            messages.error(request, mensagem)
        return redirect("orcamentos:detalhe", pk)
    messages.success(request, f"Proposta aceita! O pedido #{pedido.pk} foi gerado.")
    return redirect("pedidos:detalhe", pedido.pk)


def _decidir(request, pk, acao, mensagem):
    orcamento = _do_comprador(request, pk)
    try:
        getattr(orcamento, acao)(request.user)
    except ValidationError as erro:
        for texto in erro.messages:
            messages.error(request, texto)
    else:
        messages.success(request, mensagem)
    return redirect("orcamentos:detalhe", pk)


@login_required
@require_POST
def recusar(request, pk):
    return _decidir(request, pk, "recusar", "Proposta recusada.")


@login_required
@require_POST
def cancelar(request, pk):
    return _decidir(request, pk, "cancelar", "Solicitação de orçamento cancelada.")
