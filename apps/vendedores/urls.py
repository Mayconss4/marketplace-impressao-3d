from django.urls import path

from . import views

app_name = "vendedores"

urlpatterns = [
    path("minha-conta/vender/", views.solicitacao, name="solicitacao"),
]
