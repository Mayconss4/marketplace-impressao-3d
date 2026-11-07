from django.urls import path

from . import views

app_name = "contas"

urlpatterns = [
    path("cadastro/", views.cadastro, name="cadastro"),
    path("minha-conta/dados/", views.dados_conta, name="dados"),
    path("minha-conta/senha/", views.TrocaSenhaView.as_view(), name="senha"),
    path("minha-conta/enderecos/", views.enderecos, name="enderecos"),
    path("minha-conta/enderecos/novo/", views.endereco_form, name="endereco_novo"),
    path("minha-conta/enderecos/<int:pk>/editar/", views.endereco_form, name="endereco_editar"),
    path("minha-conta/enderecos/<int:pk>/excluir/", views.endereco_excluir, name="endereco_excluir"),
]
