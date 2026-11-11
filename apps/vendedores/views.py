from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import FormularioSolicitacao
from .models import SolicitacaoVendedor


@login_required
def solicitacao(request):
    """Comprador pede para vender; vendedor aprovado vê a situação da loja."""
    usuario = request.user
    historico = usuario.solicitacoes_vendedor.select_related("analisado_por")
    ativa = historico.filter(
        status__in=[SolicitacaoVendedor.Status.PENDENTE, SolicitacaoVendedor.Status.APROVADA]
    ).first()

    form = None
    if ativa is None:
        form = FormularioSolicitacao(request.POST or None, usuario=usuario)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Solicitação enviada! Um administrador vai analisar seus dados.")
            return redirect("vendedores:solicitacao")

    perfil = getattr(usuario, "perfil_vendedor", None)
    contexto = {
        "form": form,
        "ativa": ativa,
        "historico": historico,
        "loja": getattr(perfil, "loja", None) if perfil else None,
    }
    return render(request, "vendedores/solicitacao.html", contexto)
