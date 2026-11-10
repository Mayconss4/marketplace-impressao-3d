from django.urls import path

from . import views

app_name = "orcamentos"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.novo, name="novo"),
    path("<int:pk>/", views.detalhe, name="detalhe"),
    path("<int:pk>/aceitar/", views.aceitar, name="aceitar"),
    path("<int:pk>/recusar/", views.recusar, name="recusar"),
    path("<int:pk>/cancelar/", views.cancelar, name="cancelar"),
]
