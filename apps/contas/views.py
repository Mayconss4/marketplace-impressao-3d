from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from apps.core.forms import FormularioTrocaSenha

from .forms import FormularioCadastro, FormularioDadosConta, FormularioEndereco


def _destino_seguro(request, padrao):
    destino = request.POST.get("next") or request.GET.get("next")
    if destino and url_has_allowed_host_and_scheme(destino, {request.get_host()}, request.is_secure()):
        return destino
    return padrao


def cadastro(request):
    if request.user.is_authenticated:
        return redirect("core:painel")
    form = FormularioCadastro(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Bem-vindo(a), {usuario.first_name}! Sua conta foi criada.")
        return redirect(_destino_seguro(request, "core:painel"))
    return render(request, "contas/cadastro.html", {"form": form})


@login_required
def dados_conta(request):
    form = FormularioDadosConta(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Dados atualizados.")
        return redirect("contas:dados")
    return render(request, "contas/dados.html", {"form": form})


class TrocaSenhaView(auth_views.PasswordChangeView):
    form_class = FormularioTrocaSenha
    template_name = "contas/senha.html"
    success_url = reverse_lazy("contas:dados")

    def form_valid(self, form):
        messages.success(self.request, "Senha alterada com sucesso.")
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Endereços (CRUD do comprador; cada um só enxerga os próprios)
# ---------------------------------------------------------------------------
@login_required
def enderecos(request):
    return render(request, "contas/enderecos.html", {"enderecos": request.user.enderecos.all()})


@login_required
def endereco_form(request, pk=None):
    endereco = get_object_or_404(request.user.enderecos, pk=pk) if pk else None
    form = FormularioEndereco(request.POST or None, instance=endereco, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Endereço salvo.")
        return redirect(_destino_seguro(request, "contas:enderecos"))
    return render(request, "contas/endereco_form.html", {"form": form, "endereco": endereco})


@login_required
def endereco_excluir(request, pk):
    endereco = get_object_or_404(request.user.enderecos, pk=pk)
    if request.method == "POST":
        endereco.delete()  # pedidos antigos mantêm a cópia do endereço
        messages.success(request, "Endereço excluído.")
        return redirect("contas:enderecos")
    return render(request, "contas/endereco_excluir.html", {"endereco": endereco})
