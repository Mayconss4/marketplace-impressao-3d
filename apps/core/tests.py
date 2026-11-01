"""Verificações do Checkpoint 1: admin, perfis/permissões, arquivos privados e integridade.

Executar: python manage.py test
Os dados vêm do comando ``popular_demo``, gravando mídia em pastas temporárias.
"""

import io
import shutil
import tempfile
from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.catalogo.models import ArquivoDigital, Categoria, ImagemProduto, Produto, VariacaoProduto
from apps.contas.models import Endereco, Usuario
from apps.orcamentos.models import Orcamento
from apps.pedidos.models import ItemCarrinho, Carrinho, PagamentoSimulado, SubPedido
from apps.pedidos.servicos import gerar_pedido_de_orcamento
from apps.vendedores.models import Loja, PerfilVendedor, SolicitacaoVendedor

MIDIA = tempfile.mkdtemp(prefix="mkt3d-media-")
PRIVADA = tempfile.mkdtemp(prefix="mkt3d-privada-")


@override_settings(MEDIA_ROOT=MIDIA, PRIVATE_MEDIA_ROOT=PRIVADA)
class BaseDemo(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("popular_demo", stdout=io.StringIO())
        u = Usuario.objects.get
        cls.admin = u(username="demo_admin")
        cls.ana = u(username="demo_ana")
        cls.carla = u(username="demo_carla")
        cls.oficina = u(username="demo_oficina")
        cls.filamentos = u(username="demo_filamentos")
        cls.diego = u(username="demo_diego")
        cls.loja_oficina = Loja.objects.get(nome="Oficina Camadas")
        cls.loja_filamentos = Loja.objects.get(nome="Filamento & Cia")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MIDIA, ignore_errors=True)
        shutil.rmtree(PRIVADA, ignore_errors=True)


class AcessoAdminTests(BaseDemo):
    def test_comprador_nao_acessa_admin(self):
        for usuario in (self.ana, self.diego):  # comprador e solicitante pendente
            self.client.force_login(usuario)
            resposta = self.client.get(reverse("admin:index"))
            self.assertEqual(resposta.status_code, 302)
            self.assertIn(reverse("admin:login"), resposta["Location"])

    def test_admin_abre_todas_as_listagens_com_cada_filtro(self):
        self.client.force_login(self.admin)
        for model, model_admin in admin.site._registry.items():
            url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
            resposta = self.client.get(url)
            self.assertEqual(resposta.status_code, 200, url)
            self.assertContains(resposta, "jazzmin", msg_prefix=url)  # tema Jazzmin ativo
            # Aplica cada opção de cada filtro e uma busca textual
            for spec in resposta.context["cl"].filter_specs:
                for escolha in list(spec.choices(resposta.context["cl"]))[1:]:
                    consulta = escolha["query_string"]
                    self.assertEqual(self.client.get(url + consulta).status_code, 200, url + consulta)
            if model_admin.search_fields:
                self.assertEqual(self.client.get(url, {"q": "demo"}).status_code, 200)

    def test_admin_abre_formularios_de_edicao(self):
        self.client.force_login(self.admin)
        for model in admin.site._registry:
            obj = model._default_manager.first()
            if obj is None:
                continue
            url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_change", args=[obj.pk])
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_vendedor_ve_somente_os_proprios_registros(self):
        self.client.force_login(self.oficina)
        casos = {
            "catalogo_produto": Produto.objects.filter(loja=self.loja_oficina),
            "catalogo_variacaoproduto": VariacaoProduto.objects.filter(produto__loja=self.loja_oficina),
            "vendedores_loja": Loja.objects.filter(pk=self.loja_oficina.pk),
            "pedidos_subpedido": SubPedido.objects.filter(loja=self.loja_oficina),
            "pedidos_pagamentosimulado": PagamentoSimulado.objects.filter(subpedido__loja=self.loja_oficina),
            "orcamentos_orcamento": Orcamento.objects.filter(vendedor__usuario=self.oficina),
        }
        for nome, esperado in casos.items():
            resposta = self.client.get(reverse(f"admin:{nome}_changelist"))
            self.assertEqual(resposta.status_code, 200, nome)
            self.assertEqual(
                set(resposta.context["cl"].result_list.values_list("pk", flat=True)),
                set(esperado.values_list("pk", flat=True)),
                nome,
            )

    def test_vendedor_nao_abre_registro_de_terceiro_pelo_id(self):
        self.client.force_login(self.oficina)
        produto_alheio = Produto.objects.filter(loja=self.loja_filamentos).first()
        sub_alheio = SubPedido.objects.filter(loja=self.loja_filamentos).first()
        for nome, obj in (("catalogo_produto", produto_alheio), ("pedidos_subpedido", sub_alheio),
                          ("vendedores_loja", self.loja_filamentos)):
            resposta = self.client.get(reverse(f"admin:{nome}_change", args=[obj.pk]))
            self.assertEqual(resposta.status_code, 302, nome)  # admin redireciona: "não existe"
            # Exclusão negada: 302 (registro "inexistente" para ele) ou 403 (sem permissão)
            self.assertIn(self.client.post(reverse(f"admin:{nome}_delete", args=[obj.pk])).status_code, (302, 403))
        self.assertTrue(Produto.objects.filter(pk=produto_alheio.pk).exists())

    def test_vendedor_sem_acesso_a_modelos_administrativos(self):
        self.client.force_login(self.oficina)
        for nome in ("contas_usuario", "contas_endereco", "vendedores_solicitacaovendedor", "pedidos_pedido", "pedidos_carrinho"):
            self.assertEqual(self.client.get(reverse(f"admin:{nome}_changelist")).status_code, 403, nome)
        # Categorias: só consulta
        self.assertEqual(self.client.get(reverse("admin:catalogo_categoria_changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:catalogo_categoria_add")).status_code, 403)
        # Não pode criar segunda loja
        self.assertEqual(self.client.get(reverse("admin:vendedores_loja_add")).status_code, 403)

    def test_produto_criado_por_vendedor_fica_na_loja_dele_mesmo_forjando_post(self):
        self.client.force_login(self.oficina)
        categoria = Categoria.objects.get(slug="vasos")
        dados = {
            "nome": "Produto de teste", "descricao": "x", "categoria": categoria.pk, "tipo": "digital",
            "preco_base": "10.00", "ativo": "on", "loja": self.loja_filamentos.pk,  # tentativa de forjar a loja
        }
        for prefixo in ("imagens", "variacoes", "arquivos"):
            dados.update({f"{prefixo}-TOTAL_FORMS": "0", f"{prefixo}-INITIAL_FORMS": "0"})
        resposta = self.client.post(reverse("admin:catalogo_produto_add"), dados)
        self.assertEqual(resposta.status_code, 302, getattr(resposta, "context", None) and resposta.context["adminform"].form.errors)
        self.assertEqual(Produto.objects.get(nome="Produto de teste").loja, self.loja_oficina)

    def _post_produto(self, produto, nova_variacao=None, todas_principais=False):
        """Reenvia o formulário do produto como o navegador faria, com alterações opcionais."""
        url = reverse("admin:catalogo_produto_change", args=[produto.pk])
        contexto = self.client.get(url).context
        form = contexto["adminform"].form
        dados = {k: getattr(v, "pk", v) for k, v in form.initial.items() if k in form.fields and v is not None}
        dados["ativo"] = "on"
        for inline in contexto["inline_admin_formsets"]:
            formset, prefixo = inline.formset, inline.formset.prefix
            total = len(formset.initial_forms)
            dados[f"{prefixo}-INITIAL_FORMS"] = str(total)
            for i, f in enumerate(formset.initial_forms):
                dados[f"{prefixo}-{i}-id"] = f.instance.pk
                for nome in f.fields:
                    if nome in ("id", "produto", "imagem", "DELETE"):
                        continue
                    valor = getattr(f.instance, nome)
                    if valor is not False:
                        dados[f"{prefixo}-{i}-{nome}"] = "on" if valor is True else valor
                if prefixo == "imagens" and todas_principais:
                    dados[f"{prefixo}-{i}-principal"] = "on"
            if prefixo == "variacoes" and nova_variacao:
                dados.update({f"{prefixo}-{total}-{k}": v for k, v in nova_variacao.items()})
                total += 1
            dados[f"{prefixo}-TOTAL_FORMS"] = str(total)
        return self.client.post(url, dados)

    def test_inline_do_produto_valida_variacoes_e_imagem_principal(self):
        self.client.force_login(self.oficina)
        produto = Produto.objects.get(nome="Vaso Geométrico Low-Poly")
        existente = produto.variacoes.first()
        casos = [
            {"nova_variacao": {"material": existente.material.lower(), "cor": existente.cor.upper(),
                               "dimensoes": existente.dimensoes, "ajuste_preco": "0", "estoque": "1"}},
            {"nova_variacao": {"material": "PLA", "cor": "Rosa", "dimensoes": "X", "ajuste_preco": "-100", "estoque": "1"}},
            {"todas_principais": True},
        ]
        for kwargs in casos:
            resposta = self._post_produto(produto, **kwargs)
            self.assertEqual(resposta.status_code, 200, kwargs)  # formulário reexibido com erro, sem 500
        self.assertEqual(produto.variacoes.count(), 3)
        self.assertEqual(produto.imagens.filter(principal=True).count(), 1)
        self.assertEqual(self._post_produto(produto).status_code, 302)  # envio válido continua salvando

    def test_vendedor_responde_orcamento_pendente(self):
        self.client.force_login(self.oficina)
        orcamento = Orcamento.objects.get(vendedor__usuario=self.oficina, status="pendente")
        url = reverse("admin:orcamentos_orcamento_change", args=[orcamento.pk])
        resposta = self.client.post(url, {"preco_unitario_proposto": "22.50", "detalhes_proposta": "Prazo 2 dias."})
        self.assertEqual(resposta.status_code, 302)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, "respondido")
        self.assertEqual(orcamento.valor_total_proposto, Decimal("45.00"))

    def test_aprovacao_pelo_admin_e_proibicao_de_autoaprovacao(self):
        pendente = SolicitacaoVendedor.objects.get(usuario=self.diego)
        with self.assertRaises(Exception):
            pendente.aprovar(self.oficina)  # vendedor não aprova
        self.client.force_login(self.admin)
        self.client.post(
            reverse("admin:vendedores_solicitacaovendedor_changelist"),
            {"action": "aprovar_solicitacoes", "_selected_action": [pendente.pk]},
        )
        self.diego.refresh_from_db()
        self.assertTrue(PerfilVendedor.objects.filter(usuario=self.diego).exists())
        self.assertTrue(self.diego.is_staff and not self.diego.is_superuser)
        self.assertTrue(self.diego.groups.filter(name="Vendedores").exists())


class InterfacePublicaTests(BaseDemo):
    def test_home_lista_apenas_produtos_disponiveis(self):
        resposta = self.client.get(reverse("core:home"))
        self.assertEqual(resposta.status_code, 200)
        nomes = {p.nome for p in resposta.context["produtos"]}
        self.assertIn("Luminária Lua", nomes)
        self.assertNotIn("Suporte para Headset", nomes)  # anúncio inativo
        self.assertNotIn("Busto Clássico em Resina", nomes)  # loja inativa
        self.assertNotContains(resposta, "arquivos-privados")

    def test_login_e_logout(self):
        resposta = self.client.post(reverse("core:login"), {"username": "demo_ana", "password": "Demo@2026"})
        self.assertRedirects(resposta, reverse("core:home"))
        self.assertContains(self.client.get(reverse("core:home")), "Sair")
        self.assertRedirects(self.client.post(reverse("core:logout")), reverse("core:home"))


class ArquivosPrivadosTests(BaseDemo):
    def test_arquivo_de_orcamento(self):
        orcamento = Orcamento.objects.filter(comprador=self.ana, vendedor__usuario=self.oficina).first()
        url = orcamento.arquivo_3d.url
        self.assertTrue(url.startswith("/arquivos-privados/"))
        self.assertEqual(self.client.get(url).status_code, 302)  # anônimo → login
        for usuario, esperado in ((self.carla, 403), (self.filamentos, 403), (self.ana, 200), (self.oficina, 200), (self.admin, 200)):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(url).status_code, esperado, usuario.username)

    def test_arquivo_digital_so_para_dono_e_admin(self):
        arquivo = ArquivoDigital.objects.filter(produto__loja=self.loja_oficina).first()
        for usuario, esperado in ((self.ana, 403), (self.filamentos, 403), (self.oficina, 200), (self.admin, 200)):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(arquivo.arquivo.url).status_code, esperado, usuario.username)

    def test_midia_publica_nao_expoe_arquivo_privado(self):
        arquivo = ArquivoDigital.objects.first()
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f"/media/{arquivo.arquivo.name}").status_code, 404)


class IntegridadeTests(BaseDemo):
    def test_variacao_nao_pode_gerar_preco_negativo(self):
        produto = Produto.objects.get(nome="Organizador de Mesa Hexagonal")
        variacao = VariacaoProduto(produto=produto, material="PLA", cor="Rosa", dimensoes="Padrão",
                                   ajuste_preco=Decimal("-50.00"), estoque=1)
        with self.assertRaises(ValidationError):
            variacao.full_clean()

    def test_variacao_duplicada_ignorando_maiusculas(self):
        variacao = VariacaoProduto.objects.first()
        duplicada = VariacaoProduto(produto=variacao.produto, material=variacao.material.upper(),
                                    cor=variacao.cor.lower(), dimensoes=variacao.dimensoes, estoque=1)
        with self.assertRaises(ValidationError):
            duplicada.full_clean()

    def test_estoque_negativo_bloqueado_no_banco(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            VariacaoProduto.objects.filter(pk=VariacaoProduto.objects.first().pk).update(estoque=-1)

    def test_produto_digital_nao_aceita_variacao_nem_quantidade_maior_que_um(self):
        digital = Produto.objects.filter(tipo="digital").first()
        variacao = VariacaoProduto.objects.first()
        carrinho = Carrinho.objects.get(comprador=self.carla)
        for kwargs in ({"variacao": variacao, "quantidade": 1}, {"variacao": None, "quantidade": 2}):
            with self.assertRaises(ValidationError):
                ItemCarrinho(carrinho=carrinho, produto=digital, **kwargs).full_clean()

    def test_categoria_circular(self):
        raiz = Categoria.objects.get(slug="decoracao")
        raiz.pai = Categoria.objects.get(slug="vasos")
        with self.assertRaises(ValidationError):
            raiz.full_clean()

    def test_uma_unica_imagem_principal(self):
        produto = Produto.objects.get(nome="Luminária Lua")
        nova = produto.imagens.exclude(principal=True).first()
        nova.principal = True
        nova.save()  # rebaixa a anterior
        self.assertEqual(produto.imagens.filter(principal=True).count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ImagemProduto.objects.filter(produto=produto).update(principal=True)

    def test_orcamento_aceito_nao_gera_pedido_duplicado(self):
        aceito = Orcamento.objects.get(status="aceito")
        self.assertIsNotNone(aceito.pedido_gerado)
        with self.assertRaises(ValidationError):
            gerar_pedido_de_orcamento(aceito, Endereco.objects.filter(usuario=aceito.comprador).first())

    def test_pedido_preserva_endereco_apos_alteracao(self):
        pedido = self.ana.pedidos.exclude(entrega_logradouro="").first()
        endereco = pedido.endereco
        endereco.logradouro = "Rua Alterada"
        endereco.save()
        pedido.refresh_from_db()
        self.assertNotEqual(pedido.entrega_logradouro, "Rua Alterada")

    def test_pedido_multivendedor(self):
        self.assertTrue(any(p.subpedidos.count() > 1 for p in self.ana.pedidos.all()))

    def test_comando_demo_e_idempotente(self):
        total = Usuario.objects.count()
        call_command("popular_demo", stdout=io.StringIO())
        self.assertEqual(Usuario.objects.count(), total)
