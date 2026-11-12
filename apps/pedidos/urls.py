from django.urls import path

from . import views

app_name = "pedidos"

urlpatterns = [
    path("carrinho/", views.carrinho, name="carrinho"),
    path("carrinho/adicionar/<int:produto_pk>/", views.adicionar, name="adicionar"),
    path("carrinho/itens/<int:pk>/", views.atualizar_item, name="atualizar_item"),
    path("carrinho/finalizar/", views.checkout, name="checkout"),
    path("minha-conta/pedidos/", views.lista, name="lista"),
    path("minha-conta/pedidos/<int:pk>/", views.detalhe, name="detalhe"),
    path("minha-conta/pedidos/<int:pk>/cancelar/", views.cancelar, name="cancelar"),
]
