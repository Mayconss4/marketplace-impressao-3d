"""Verificações do Checkpoint 2: cadastro, área do usuário final, catálogo, carrinho,
checkout, pedidos, orçamentos, downloads digitais e solicitação de vendedor.

Executar: python manage.py test apps
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.catalogo.models import ArquivoDigital, Produto, VariacaoProduto
from apps.contas.models import Endereco, Usuario
from apps.orcamentos.models import Orcamento
from apps.pedidos.models import Carrinho, ItemCarrinho, PagamentoSimulado, Pedido, StatusPedido
from apps.vendedores.models import SolicitacaoVendedor

from .tests import BaseDemo


def _variacao(produto, cor):
    return VariacaoProduto.objects.get(produto__nome=produto, cor=cor)


class CadastroLoginTests(BaseDemo):
    def test_cadastro_cria_comprador_e_ja_entra_logado(self):
        self.assertContains(self.client.get(reverse("core:home")), "Cadastre-se")
        dados = {
            "username": "novo_cliente", "first_name": "Novo", "last_name": "Cliente",
            "email": "Novo@Exemplo.invalid", "password1": "SenhaForte#2026", "password2": "SenhaForte#2026",
        }
        resposta = self.client.post(reverse("contas:cadastro"), dados)
        self.assertRedirects(resposta, reverse("core:painel"))
        usuario = Usuario.objects.get(username="novo_cliente")
        self.assertEqual(usuario.email, "novo@exemplo.invalid")
        self.assertFalse(usuario.is_staff or usuario.is_superuser)
        self.assertEqual(usuario.perfis, ["Comprador"])
        self.assertEqual(self.client.get(reverse("core:painel")).status_code, 200)

    def test_cadastro_rejeita_email_repetido_e_senhas_diferentes(self):
        dados = {
            "username": "outra_ana", "first_name": "Ana", "email": self.ana.email.upper(),
            "password1": "SenhaForte#2026", "password2": "OutraSenha#2026",
        }
        resposta = self.client.post(reverse("contas:cadastro"), dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("email", resposta.context["form"].errors)
        self.assertIn("password2", resposta.context["form"].errors)
        self.assertFalse(Usuario.objects.filter(username="outra_ana").exists())

    def test_area_do_usuario_exige_login(self):
        rotas = ["core:painel", "pedidos:lista", "pedidos:carrinho", "pedidos:checkout", "contas:enderecos",
                 "contas:dados", "contas:senha", "orcamentos:lista", "orcamentos:novo", "vendedores:solicitacao"]
        for rota in rotas:
            resposta = self.client.get(reverse(rota))
            self.assertEqual(resposta.status_code, 302, rota)
            self.assertIn(reverse("core:login"), resposta["Location"])
        self.client.force_login(self.ana)
        for rota in rotas:
            self.assertIn(self.client.get(reverse(rota)).status_code, (200, 302), rota)

    def test_troca_de_senha(self):
        self.client.force_login(self.carla)
        resposta = self.client.post(reverse("contas:senha"), {
            "old_password": "Demo@2026", "new_password1": "NovaSenha#2026", "new_password2": "NovaSenha#2026",
        })
        self.assertRedirects(resposta, reverse("contas:dados"))
        self.carla.refresh_from_db()
        self.assertTrue(self.carla.check_password("NovaSenha#2026"))


class EnderecoTests(BaseDemo):
    def _dados(self, **extra):
        dados = {"apelido": "Sítio", "destinatario": "Carla Mendes", "telefone": "(35) 99999-0000", "cep": "37200-000",
                 "logradouro": "Estrada Ficticia", "numero": "S/N", "bairro": "Zona Rural", "cidade": "Lavras", "uf": "MG"}
        dados.update(extra)
        return dados

    def test_crud_de_enderecos(self):
        self.client.force_login(self.carla)
        self.assertRedirects(self.client.post(reverse("contas:endereco_novo"), self._dados()), reverse("contas:enderecos"))
        endereco = Endereco.objects.get(usuario=self.carla, apelido="Sítio")
        self.client.post(reverse("contas:endereco_editar", args=[endereco.pk]), self._dados(numero="10"))
        endereco.refresh_from_db()
        self.assertEqual(endereco.numero, "10")
        self.client.post(reverse("contas:endereco_excluir", args=[endereco.pk]))
        self.assertFalse(Endereco.objects.filter(pk=endereco.pk).exists())

    def test_apelido_repetido_e_isolamento(self):
        self.client.force_login(self.carla)
        resposta = self.client.post(reverse("contas:endereco_novo"), self._dados(apelido="casa"))
        self.assertIn("apelido", resposta.context["form"].errors)
        endereco_ana = Endereco.objects.filter(usuario=self.ana).first()
        self.assertEqual(self.client.get(reverse("contas:endereco_editar", args=[endereco_ana.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("contas:endereco_excluir", args=[endereco_ana.pk])).status_code, 404)


class CatalogoTests(BaseDemo):
    def test_filtros_busca_e_detalhe(self):
        url = reverse("catalogo:lista")
        nomes = lambda resposta: {p.nome for p in resposta.context["pagina"].object_list}  # noqa: E731
        decoracao = nomes(self.client.get(url, {"categoria": "decoracao"}))
        self.assertIn("Vaso Geométrico Low-Poly", decoracao)  # subcategoria Vasos
        self.assertIn("Luminária Lua", decoracao)
        self.assertNotIn("Busto Clássico em Resina", decoracao)  # loja inativa
        self.assertTrue(all("Digital" in n or "CAD" in n for n in nomes(self.client.get(url, {"tipo": "digital"}))))
        self.assertEqual(nomes(self.client.get(url, {"q": "engrenagem"})), {"Engrenagem Helicoidal M1"})
        self.assertEqual(self.client.get(url, {"ordem": "menor_preco", "pagina": "99"}).status_code, 200)

        vaso = Produto.objects.get(nome="Vaso Geométrico Low-Poly")
        self.assertContains(self.client.get(reverse("catalogo:detalhe", args=[vaso.pk])), "Terracota")
        inativo = Produto.objects.get(nome="Suporte para Headset")
        self.assertEqual(self.client.get(reverse("catalogo:detalhe", args=[inativo.pk])).status_code, 404)


class CarrinhoCheckoutTests(BaseDemo):
    def test_adicionar_atualizar_e_remover(self):
        self.client.force_login(self.carla)
        lua = VariacaoProduto.objects.get(produto__nome="Luminária Lua", dimensoes="15 cm")
        url = reverse("pedidos:adicionar", args=[lua.produto_id])
        self.client.post(url, {"variacao": lua.pk, "quantidade": 2})
        self.client.post(url, {"variacao": lua.pk, "quantidade": 1})
        item = ItemCarrinho.objects.get(carrinho__comprador=self.carla)
        self.assertEqual(item.quantidade, 3)

        resposta = self.client.post(url, {"variacao": lua.pk, "quantidade": 50}, follow=True)
        self.assertContains(resposta, "Estoque insuficiente")
        item.refresh_from_db()
        self.assertEqual(item.quantidade, 3)

        self.client.post(reverse("pedidos:atualizar_item", args=[item.pk]), {"quantidade": 1})
        item.refresh_from_db()
        self.assertEqual(item.quantidade, 1)
        self.client.post(reverse("pedidos:atualizar_item", args=[item.pk]), {"acao": "remover"})
        self.assertFalse(ItemCarrinho.objects.filter(pk=item.pk).exists())

    def test_digital_quantidade_um_e_sem_autocompra(self):
        digital = Produto.objects.get(nome="Pacote Digital: Gavetas Modulares")
        self.client.force_login(self.carla)
        for _ in range(2):
            self.client.post(reverse("pedidos:adicionar", args=[digital.pk]))
        self.assertEqual(ItemCarrinho.objects.get(carrinho__comprador=self.carla, produto=digital).quantidade, 1)

        self.client.force_login(self.oficina)
        vaso = Produto.objects.get(nome="Vaso Geométrico Low-Poly")
        resposta = self.client.post(
            reverse("pedidos:adicionar", args=[vaso.pk]), {"variacao": vaso.variacoes.first().pk}, follow=True
        )
        self.assertContains(resposta, "sua própria loja")
        self.assertFalse(ItemCarrinho.objects.filter(carrinho__comprador=self.oficina, produto=vaso).exists())

    def test_checkout_gera_pedido_por_loja_baixa_estoque_e_esvazia_carrinho(self):
        self.client.force_login(self.ana)
        variacao = _variacao("Vaso Geométrico Low-Poly", "Branco")
        estoque_antes = variacao.estoque
        endereco = Endereco.objects.get(usuario=self.ana, apelido="Casa")

        resposta = self.client.post(reverse("pedidos:checkout"))  # físico sem endereço
        self.assertContains(resposta, "Selecione um endereço")
        self.assertEqual(Carrinho.objects.get(comprador=self.ana).itens.count(), 2)

        resposta = self.client.post(reverse("pedidos:checkout"), {"endereco": endereco.pk})
        pedido = Pedido.objects.filter(comprador=self.ana).latest("pk")
        self.assertRedirects(resposta, reverse("pedidos:detalhe", args=[pedido.pk]))
        self.assertEqual(pedido.entrega_logradouro, endereco.logradouro)
        self.assertEqual(pedido.subpedidos.count(), 1)
        self.assertEqual(pedido.valor_total, pedido.subpedidos.get().pagamento.valor)
        variacao.refresh_from_db()
        self.assertEqual(variacao.estoque, estoque_antes - 2)
        self.assertFalse(Carrinho.objects.get(comprador=self.ana).itens.exists())

    def test_checkout_somente_digital_dispensa_endereco(self):
        self.client.force_login(self.bruno)
        Carrinho.objects.get(comprador=self.bruno).itens.all().delete()
        digital = Produto.objects.get(nome="Pacote Digital: Gavetas Modulares")
        self.client.post(reverse("pedidos:adicionar", args=[digital.pk]))
        self.client.post(reverse("pedidos:checkout"))
        pedido = Pedido.objects.filter(comprador=self.bruno).latest("pk")
        self.assertFalse(pedido.possui_entrega)


class PedidoTests(BaseDemo):
    def test_cancelamento_devolve_estoque_e_cancela_subpedidos(self):
        pedido = Pedido.objects.get(comprador=self.carla)
        variacao = _variacao("Organizador de Mesa Hexagonal", "Azul")
        estoque_antes = variacao.estoque

        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse("pedidos:detalhe", args=[pedido.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("pedidos:cancelar", args=[pedido.pk])).status_code, 404)

        self.client.force_login(self.carla)
        self.assertContains(self.client.get(reverse("pedidos:detalhe", args=[pedido.pk])), "Cancelar pedido")
        self.client.post(reverse("pedidos:cancelar", args=[pedido.pk]))
        pedido.refresh_from_db()
        variacao.refresh_from_db()
        self.assertEqual(pedido.status, StatusPedido.CANCELADO)
        self.assertFalse(pedido.subpedidos.exclude(status=StatusPedido.CANCELADO).exists())
        self.assertEqual(variacao.estoque, estoque_antes + 2)

    def test_pedido_em_andamento_ou_pago_nao_cancela(self):
        self.client.force_login(self.ana)
        em_andamento = Pedido.objects.filter(comprador=self.ana, status=StatusPedido.EM_ANDAMENTO).first()
        resposta = self.client.post(reverse("pedidos:cancelar", args=[em_andamento.pk]), follow=True)
        self.assertContains(resposta, "Somente pedidos pendentes")
        self.assertEqual(Pedido.objects.get(pk=em_andamento.pk).status, StatusPedido.EM_ANDAMENTO)

    def test_download_digital_liberado_apos_pagamento_confirmado(self):
        gaveta = ArquivoDigital.objects.filter(produto__nome="Pacote Digital: Gavetas Modulares").first()
        espiral = ArquivoDigital.objects.get(produto__nome="Modelo Digital: Vaso Espiral")

        self.client.force_login(self.bruno)  # comprou o Vaso Espiral, pagamento confirmado
        self.assertEqual(self.client.get(espiral.arquivo.url).status_code, 200)
        self.assertEqual(self.client.get(gaveta.arquivo.url).status_code, 403)

        self.client.force_login(self.ana)  # comprou as Gavetas, pagamento ainda pendente
        self.assertEqual(self.client.get(gaveta.arquivo.url).status_code, 403)
        pagamento = PagamentoSimulado.objects.get(
            subpedido__pedido__comprador=self.ana, subpedido__itens__produto=gaveta.produto
        )
        pagamento.confirmar(self.filamentos)
        self.assertEqual(self.client.get(gaveta.arquivo.url).status_code, 200)
        pedido = pagamento.subpedido.pedido
        self.assertContains(self.client.get(reverse("pedidos:detalhe", args=[pedido.pk])), gaveta.nome_arquivo)


class OrcamentoTests(BaseDemo):
    def test_comprador_envia_orcamento_com_arquivo(self):
        self.client.force_login(self.carla)
        perfil = self.loja_filamentos.vendedor
        arquivo = SimpleUploadedFile("suporte.stl", b"solid suporte\nendsolid suporte\n")
        resposta = self.client.post(reverse("orcamentos:novo"), {
            "vendedor": perfil.pk, "arquivo_3d": arquivo, "quantidade": 2,
            "material": "PETG", "cor": "Preto", "dimensoes": "5 x 5 cm", "observacoes": "",
        })
        orcamento = Orcamento.objects.filter(comprador=self.carla).latest("pk")
        self.assertRedirects(resposta, reverse("orcamentos:detalhe", args=[orcamento.pk]))
        self.assertEqual(orcamento.status, Orcamento.Status.PENDENTE)
        self.assertEqual(self.client.get(orcamento.arquivo_3d.url).status_code, 200)

        invalido = SimpleUploadedFile("foto.png", b"png")
        resposta = self.client.post(reverse("orcamentos:novo"), {
            "vendedor": perfil.pk, "arquivo_3d": invalido, "quantidade": 1, "material": "PLA", "cor": "Azul", "dimensoes": "1 cm",
        })
        self.assertIn("arquivo_3d", resposta.context["form"].errors)

    def test_vendedor_nao_pede_orcamento_a_si_mesmo(self):
        self.client.force_login(self.oficina)
        form = self.client.get(reverse("orcamentos:novo")).context["form"]
        self.assertNotIn(self.loja_oficina.vendedor, form.fields["vendedor"].queryset)

    def test_aceite_gera_pedido_e_recusa_cancelamento(self):
        respondido = Orcamento.objects.get(comprador=self.bruno, status=Orcamento.Status.RESPONDIDO)
        endereco = Endereco.objects.get(usuario=self.bruno)

        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse("orcamentos:detalhe", args=[respondido.pk])).status_code, 404)

        self.client.force_login(self.bruno)
        resposta = self.client.post(reverse("orcamentos:aceitar", args=[respondido.pk]), {"endereco": endereco.pk})
        respondido.refresh_from_db()
        self.assertEqual(respondido.status, Orcamento.Status.ACEITO)
        self.assertRedirects(resposta, reverse("pedidos:detalhe", args=[respondido.pedido_gerado.pk]))
        self.assertEqual(respondido.pedido_gerado.valor_total, respondido.valor_total_proposto)

        # Já aceito: não pode ser cancelado nem gerar outro pedido.
        self.client.post(reverse("orcamentos:cancelar", args=[respondido.pk]))
        self.client.post(reverse("orcamentos:aceitar", args=[respondido.pk]), {"endereco": endereco.pk})
        respondido.refresh_from_db()
        self.assertEqual(respondido.status, Orcamento.Status.ACEITO)
        self.assertEqual(Pedido.objects.filter(subpedidos__itens__orcamento=respondido).count(), 1)

        pendente = Orcamento.objects.get(comprador=self.ana, status=Orcamento.Status.PENDENTE)
        self.client.force_login(self.ana)
        self.client.post(reverse("orcamentos:recusar", args=[pendente.pk]))  # pendente não se recusa
        pendente.refresh_from_db()
        self.assertEqual(pendente.status, Orcamento.Status.PENDENTE)
        self.client.post(reverse("orcamentos:cancelar", args=[pendente.pk]))
        pendente.refresh_from_db()
        self.assertEqual(pendente.status, Orcamento.Status.CANCELADO)


class SolicitacaoVendedorTests(BaseDemo):
    def test_comprador_solicita_e_nao_duplica(self):
        self.client.force_login(self.carla)
        url = reverse("vendedores:solicitacao")
        resposta = self.client.post(url, {"tipo_pessoa": "PF", "documento": "111.111.111-11", "nome_razao_social": "Carla",
                                          "telefone": "(11) 98888-7777", "nome_loja": "Carla 3D"})
        self.assertIn("documento", resposta.context["form"].errors)  # CPF inválido

        resposta = self.client.post(url, {"tipo_pessoa": "PF", "documento": "529.982.247-25", "nome_razao_social": "Carla Mendes",
                                          "telefone": "(11) 98888-7777", "nome_loja": "Carla 3D"})
        self.assertRedirects(resposta, url)
        solicitacao = SolicitacaoVendedor.objects.get(usuario=self.carla)
        self.assertEqual(solicitacao.status, SolicitacaoVendedor.Status.PENDENTE)
        self.assertEqual(solicitacao.documento, "52998224725")
        self.assertContains(self.client.get(url), "pendente")
        self.assertIsNone(self.client.get(url).context["form"])
        self.carla.refresh_from_db()
        self.assertFalse(self.carla.is_staff)


class PaginasTests(BaseDemo):
    def test_todas_as_telas_abrem_para_cada_perfil(self):
        produtos = Produto.objects.disponiveis()
        publicas = [reverse("core:home"), reverse("catalogo:lista"), reverse("contas:cadastro"), reverse("core:login")]
        publicas += [reverse("catalogo:detalhe", args=[p.pk]) for p in produtos if p.preco_minimo() is not None]
        for url in publicas:
            self.assertEqual(self.client.get(url).status_code, 200, url)

        for usuario in (self.ana, self.bruno, self.carla, self.oficina, self.diego, self.admin):
            self.client.force_login(usuario)
            # Cadastro e login redirecionam quem já está logado.
            urls = [url for url in publicas if url not in (reverse("contas:cadastro"), reverse("core:login"))] + [
                reverse(rota) for rota in ("core:painel", "pedidos:carrinho", "pedidos:lista", "orcamentos:lista",
                                           "orcamentos:novo", "contas:enderecos", "contas:endereco_novo",
                                           "contas:dados", "contas:senha", "vendedores:solicitacao")
            ]
            urls += [reverse("pedidos:detalhe", args=[p.pk]) for p in Pedido.objects.filter(comprador=usuario)]
            urls += [reverse("orcamentos:detalhe", args=[o.pk]) for o in Orcamento.objects.filter(comprador=usuario)]
            for endereco in usuario.enderecos.all():
                urls += [reverse("contas:endereco_editar", args=[endereco.pk]), reverse("contas:endereco_excluir", args=[endereco.pk])]
            if Carrinho.objects.filter(comprador=usuario, itens__isnull=False).exists():
                urls.append(reverse("pedidos:checkout"))
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 200, f"{usuario.username} {url}")
