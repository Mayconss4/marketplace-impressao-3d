from .models import ItemCarrinho


def carrinho(request):
    """Quantidade de itens no carrinho, exibida no menu de todas as páginas."""
    if not request.user.is_authenticated:
        return {}
    return {"qtd_itens_carrinho": ItemCarrinho.objects.filter(carrinho__comprador=request.user).count()}
