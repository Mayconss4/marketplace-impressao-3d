"""Popula (ou remove) os dados FICTÍCIOS de demonstração do Checkpoint 1.

Uso:
    python manage.py popular_demo            # cria, se ainda não existirem
    python manage.py popular_demo --recriar  # remove os dados demo e cria de novo
    python manage.py popular_demo --limpar   # apenas remove os dados demo

Todos os registros demo pertencem a contas cujo username começa com ``demo_``
(e a categorias com os slugs listados em SLUGS_CATEGORIAS). A remoção atua só
sobre esses registros e é abortada se algum dado real depender deles.
CPFs/CNPJs são gerados com dígitos verificadores válidos, mas são fictícios.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalogo.models import ArquivoDigital, Categoria, ImagemProduto, Produto, VariacaoProduto
from apps.contas.models import Endereco, Usuario
from apps.core import demo_arquivos as arq
from apps.core.validadores import calcular_digito
from apps.orcamentos.models import Orcamento
from apps.pedidos.models import Carrinho, ItemCarrinho, ItemPedido, PagamentoSimulado, Pedido, StatusPedido, SubPedido
from apps.pedidos.servicos import cancelar_pedido, registrar_pedido
from apps.vendedores.models import Loja, PerfilVendedor, SolicitacaoVendedor

PREFIXO = "demo_"
SENHA_DEMO = "Demo@2026"

# (slug, nome, slug_do_pai, ativa)
CATEGORIAS = [
    ("decoracao", "Decoração", None, True),
    ("vasos", "Vasos", "decoracao", True),
    ("luminarias", "Luminárias", "decoracao", True),
    ("utilidades", "Utilidades", None, True),
    ("organizadores", "Organizadores", "utilidades", True),
    ("suportes", "Suportes", "utilidades", True),
    ("miniaturas", "Miniaturas", None, True),
    ("rpg-tabuleiro", "RPG e Tabuleiro", "miniaturas", True),
    ("pecas-tecnicas", "Peças Técnicas", None, True),
    ("engrenagens", "Engrenagens", "pecas-tecnicas", True),
    ("brinquedos", "Brinquedos", None, False),
]
SLUGS_CATEGORIAS = [c[0] for c in CATEGORIAS]


def cpf_ficticio(base9):
    d1 = calcular_digito(base9, range(10, 1, -1))
    d2 = calcular_digito(base9 + d1, range(11, 1, -1))
    return base9 + d1 + d2


def cnpj_ficticio(base12):
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = calcular_digito(base12, pesos)
    d2 = calcular_digito(base12 + d1, [6] + pesos)
    return base12 + d1 + d2


class Command(BaseCommand):
    help = "Cria ou remove os dados fictícios de demonstração (contas demo_*)."

    def add_arguments(self, parser):
        grupo = parser.add_mutually_exclusive_group()
        grupo.add_argument("--limpar", action="store_true", help="Remove os dados demo e encerra.")
        grupo.add_argument("--recriar", action="store_true", help="Remove os dados demo e cria novamente.")

    def handle(self, *args, **opcoes):
        existe = Usuario.objects.filter(username__startswith=PREFIXO).exists()
        if opcoes["limpar"] or opcoes["recriar"]:
            self.limpar()
            if opcoes["limpar"]:
                return
        elif existe:
            self.stdout.write(self.style.WARNING(
                "Os dados demonstrativos já existem; nada foi duplicado. Use --recriar para gerá-los de novo."
            ))
            return
        with transaction.atomic():
            self.popular()
        self.stdout.write(self.style.SUCCESS(f"Dados demonstrativos criados. Senha de todas as contas demo: {SENHA_DEMO}"))

    # ------------------------------------------------------------------
    # Remoção
    # ------------------------------------------------------------------
    def limpar(self):
        usuarios = Usuario.objects.filter(username__startswith=PREFIXO)
        conflitos = {
            "subpedidos de compradores reais em lojas demo": SubPedido.objects.filter(
                loja__vendedor__usuario__in=usuarios
            ).exclude(pedido__comprador__in=usuarios),
            "orçamentos de compradores reais para vendedores demo": Orcamento.objects.filter(
                vendedor__usuario__in=usuarios
            ).exclude(comprador__in=usuarios),
            "solicitações reais analisadas por contas demo": SolicitacaoVendedor.objects.filter(
                analisado_por__in=usuarios
            ).exclude(usuario__in=usuarios),
            "pagamentos reais confirmados por contas demo": PagamentoSimulado.objects.filter(
                confirmado_por__in=usuarios
            ).exclude(subpedido__pedido__comprador__in=usuarios),
        }
        for descricao, qs in conflitos.items():
            if qs.exists():
                raise CommandError(f"Remoção abortada: existem {descricao}. Nenhum dado foi apagado.")

        arquivos = []  # (storage, nome) apagados só após o commit
        with transaction.atomic():
            pedidos = Pedido.objects.filter(comprador__in=usuarios)
            PagamentoSimulado.objects.filter(subpedido__pedido__in=pedidos).delete()
            ItemPedido.objects.filter(subpedido__pedido__in=pedidos).delete()
            SubPedido.objects.filter(pedido__in=pedidos).delete()
            pedidos.delete()

            for orcamento in Orcamento.objects.filter(comprador__in=usuarios):
                arquivos.append((orcamento.arquivo_3d.storage, orcamento.arquivo_3d.name))
                orcamento.delete()

            Carrinho.objects.filter(comprador__in=usuarios).delete()

            produtos = Produto.objects.filter(loja__vendedor__usuario__in=usuarios)
            for imagem in ImagemProduto.objects.filter(produto__in=produtos):
                arquivos.append((imagem.imagem.storage, imagem.imagem.name))
            for arquivo in ArquivoDigital.objects.filter(produto__in=produtos):
                arquivos.append((arquivo.arquivo.storage, arquivo.arquivo.name))
            ItemCarrinho.objects.filter(produto__in=produtos).delete()
            produtos.delete()

            for loja in Loja.objects.filter(vendedor__usuario__in=usuarios):
                arquivos.append((loja.logotipo.storage, loja.logotipo.name))
                loja.delete()
            PerfilVendedor.objects.filter(usuario__in=usuarios).delete()
            SolicitacaoVendedor.objects.filter(usuario__in=usuarios).delete()
            total_usuarios = usuarios.count()
            usuarios.delete()

            # Categorias demo: das mais profundas para as raízes, só se não estiverem em uso.
            removidas = 0
            for slug in reversed(SLUGS_CATEGORIAS):
                categoria = Categoria.objects.filter(slug=slug).first()
                if categoria and not categoria.produtos.exists() and not categoria.subcategorias.exists():
                    categoria.delete()
                    removidas += 1

            def apagar_arquivos():
                for storage, nome in arquivos:
                    if nome and storage.exists(nome):
                        storage.delete(nome)

            transaction.on_commit(apagar_arquivos)

        self.stdout.write(self.style.SUCCESS(
            f"Dados demonstrativos removidos ({total_usuarios} contas, {removidas} categorias, {len(arquivos)} arquivos)."
        ))

    # ------------------------------------------------------------------
    # Criação
    # ------------------------------------------------------------------
    def _usuario(self, sufixo, nome, sobrenome, **extra):
        usuario = Usuario(
            username=PREFIXO + sufixo,
            first_name=nome,
            last_name=sobrenome,
            email=f"{sufixo}@exemplo.invalid",
            **extra,
        )
        usuario.set_password(SENHA_DEMO)
        usuario.full_clean()
        usuario.save()
        return usuario

    def _endereco(self, usuario, apelido, logradouro, numero, bairro, cidade, uf, cep):
        endereco = Endereco(
            usuario=usuario, apelido=apelido, destinatario=usuario.get_full_name(), telefone="(35) 99999-0000",
            cep=cep, logradouro=logradouro, numero=numero, bairro=bairro, cidade=cidade, uf=uf,
        )
        endereco.full_clean()
        endereco.save()
        return endereco

    def _solicitacao(self, usuario, tipo, documento, razao, loja):
        solicitacao = SolicitacaoVendedor(
            usuario=usuario, tipo_pessoa=tipo, documento=documento,
            nome_razao_social=razao, telefone="(35) 3829-0000", nome_loja=loja,
        )
        solicitacao.full_clean()
        solicitacao.save()
        return solicitacao

    def _loja(self, perfil, nome, descricao, sigla, cor, ativa=True):
        loja = Loja(vendedor=perfil, nome=nome, descricao=descricao, ativa=ativa)
        loja.logotipo.save(f"{sigla.lower()}.png", arq.logotipo(sigla, cor, f"{sigla.lower()}.png"), save=False)
        loja.full_clean()
        loja.save()
        return loja

    def _produto(self, loja, categoria, nome, descricao, tipo, preco, cor, ativo=True, variacoes=(), arquivos=()):
        produto = Produto(
            loja=loja, categoria=self.categorias[categoria], nome=nome, descricao=descricao,
            tipo=tipo, preco_base=Decimal(preco), ativo=ativo,
        )
        produto.full_clean()
        produto.save()
        for indice in range(2 if tipo == Produto.Tipo.FISICO else 1):
            imagem = ImagemProduto(produto=produto, principal=indice == 0, ordem=indice, texto_alternativo=nome)
            nome_img = f"{produto.pk}-{indice}.png"
            imagem.imagem.save(nome_img, arq.imagem_produto(nome, cor, nome_img, indice), save=False)
            imagem.full_clean()
            imagem.save()
        criadas = []
        for material, cor_var, dimensoes, ajuste, estoque in variacoes:
            variacao = VariacaoProduto(
                produto=produto, material=material, cor=cor_var, dimensoes=dimensoes,
                ajuste_preco=Decimal(ajuste), estoque=estoque,
            )
            variacao.full_clean()
            variacao.save()
            criadas.append(variacao)
        for gerador, nome_arquivo, descricao_arquivo in arquivos:
            arquivo = ArquivoDigital(produto=produto, descricao=descricao_arquivo)
            arquivo.arquivo.save(nome_arquivo, gerador(nome_arquivo), save=False)
            arquivo.full_clean()
            arquivo.save()
        produto.variacoes_demo = criadas
        return produto

    def _orcamento(self, comprador, vendedor, material, cor, dimensoes, quantidade, observacoes):
        orcamento = Orcamento(
            comprador=comprador, vendedor=vendedor, quantidade=quantidade,
            material=material, cor=cor, dimensoes=dimensoes, observacoes=observacoes,
        )
        nome = f"peca-{comprador.username}-{material.lower()}.stl"
        orcamento.arquivo_3d.save(nome, arq.stl_cubo(nome), save=False)
        orcamento.full_clean()
        orcamento.save()
        return orcamento

    def popular(self):
        out = self.stdout.write

        # Contas -------------------------------------------------------
        admin = self._usuario("admin", "Admin", "Demonstração", is_staff=True, is_superuser=True)
        ana = self._usuario("ana", "Ana", "Ribeiro")
        bruno = self._usuario("bruno", "Bruno", "Tavares")
        carla = self._usuario("carla", "Carla", "Mendes")
        oficina = self._usuario("oficina", "Otávio", "Fernandes")
        filamentos = self._usuario("filamentos", "Fernanda", "Lima")
        atelie = self._usuario("atelie", "Igor", "Pacheco")
        diego = self._usuario("diego", "Diego", "Souza")
        elisa = self._usuario("elisa", "Elisa", "Moraes")
        out("  contas criadas")

        # Endereços ----------------------------------------------------
        end_ana_casa = self._endereco(ana, "Casa", "Rua das Acácias", "120", "Centro", "Lavras", "MG", "37200-000")
        self._endereco(ana, "Trabalho", "Av. Doutor Sílvio Menicucci", "1001", "Aquenta Sol", "Lavras", "MG", "37200-001")
        self._endereco(bruno, "Casa", "Rua Ficticia Um", "45", "Jardim Exemplo", "Belo Horizonte", "MG", "30110-000")
        end_carla = self._endereco(carla, "Casa", "Rua Ficticia Dois", "300", "Vila Modelo", "São Paulo", "SP", "01001-000")
        end_oficina = self._endereco(oficina, "Casa", "Rua Ficticia Três", "77", "Centro", "Varginha", "MG", "37002-000")

        # Solicitações de vendedor (aprovadas, pendente e recusada) ------
        sol_oficina = self._solicitacao(oficina, "PF", cpf_ficticio("900100200"), "Otávio Fernandes", "Oficina Camadas")
        sol_filamentos = self._solicitacao(
            filamentos, "PJ", cnpj_ficticio("900100200001"), "Filamento e Cia Impressões Ltda.", "Filamento & Cia"
        )
        sol_atelie = self._solicitacao(atelie, "PF", cpf_ficticio("900100300"), "Igor Pacheco", "Ateliê Resina Fina")
        self._solicitacao(diego, "PF", cpf_ficticio("900100400"), "Diego Souza", "Diego Makers")
        self._solicitacao(elisa, "PJ", cnpj_ficticio("900100500001"), "Elisa Protótipos ME", "Protótipos Elisa").recusar(admin)
        for solicitacao in (sol_oficina, sol_filamentos, sol_atelie):
            solicitacao.aprovar(admin)
        out("  solicitações de vendedor analisadas")

        # Lojas --------------------------------------------------------
        loja_oficina = self._loja(
            PerfilVendedor.objects.get(usuario=oficina), "Oficina Camadas",
            "Peças decorativas e utilitárias impressas em PLA e PETG, com acabamento manual.", "OC", "#ea580c",
        )
        loja_filamentos = self._loja(
            PerfilVendedor.objects.get(usuario=filamentos), "Filamento & Cia",
            "Miniaturas em resina, peças técnicas e modelos digitais prontos para imprimir.", "FC", "#0f766e",
        )
        loja_atelie = self._loja(
            PerfilVendedor.objects.get(usuario=atelie), "Ateliê Resina Fina",
            "Bustos e esculturas em resina. Loja temporariamente inativa.", "AR", "#7c3aed", ativa=False,
        )

        # Categorias ---------------------------------------------------
        self.categorias = {}
        for slug, nome, pai, ativa in CATEGORIAS:
            categoria, _ = Categoria.objects.get_or_create(
                slug=slug, defaults={"nome": nome, "pai": self.categorias.get(pai), "ativa": ativa}
            )
            self.categorias[slug] = categoria
        out("  lojas e categorias criadas")

        # Produtos -----------------------------------------------------
        F, D = Produto.Tipo.FISICO, Produto.Tipo.DIGITAL
        vaso = self._produto(
            loja_oficina, "vasos", "Vaso Geométrico Low-Poly",
            "Vaso facetado para plantas pequenas e suculentas. Impermeabilizado internamente.", F, "59.90", "#f97316",
            variacoes=[("PLA", "Branco", "Pequeno (12 cm)", "0", 15), ("PLA", "Terracota", "Pequeno (12 cm)", "0", 4),
                       ("PETG", "Preto", "Grande (20 cm)", "25.00", 0)],
        )
        luminaria = self._produto(
            loja_oficina, "luminarias", "Luminária Lua",
            "Luminária com textura lunar e base em madeira. Acompanha LED quente.", F, "129.90", "#eab308",
            variacoes=[("PLA", "Branco", "15 cm", "0", 6), ("PLA", "Branco", "20 cm", "40.00", 2)],
        )
        organizador = self._produto(
            loja_oficina, "organizadores", "Organizador de Mesa Hexagonal",
            "Módulos hexagonais encaixáveis para canetas, clipes e ferramentas.", F, "45.00", "#3b82f6",
            variacoes=[("PLA", "Cinza", "Padrão", "0", 30), ("PLA", "Azul", "Padrão", "-5.00", 12)],
        )
        vaso_stl = self._produto(
            loja_oficina, "vasos", "Modelo Digital: Vaso Espiral",
            "Arquivo STL otimizado para impressão em modo vaso (espiral contínua).", D, "18.00", "#fb923c",
            arquivos=[(arq.stl_cubo, "vaso-espiral.stl", "Modelo principal")],
        )
        self._produto(
            loja_oficina, "suportes", "Suporte para Headset",
            "Suporte de mesa com passa-cabo. Anúncio pausado pelo vendedor.", F, "39.90", "#64748b", ativo=False,
            variacoes=[("PETG", "Preto", "Padrão", "0", 7)],
        )
        miniaturas = self._produto(
            loja_filamentos, "rpg-tabuleiro", "Kit Miniaturas Masmorra",
            "Conjunto com 6 miniaturas de criaturas em resina, prontas para pintura.", F, "89.90", "#14b8a6",
            variacoes=[("Resina", "Cinza", "28 mm", "0", 8), ("Resina", "Cinza", "32 mm", "15.00", 3)],
        )
        engrenagem = self._produto(
            loja_filamentos, "engrenagens", "Engrenagem Helicoidal M1",
            "Engrenagem helicoidal módulo 1 com 32 dentes, para projetos de mecânica e robótica.", F, "24.50", "#0ea5e9",
            variacoes=[("PETG", "Preto", "32 dentes", "0", 50), ("Nylon", "Natural", "32 dentes", "12.00", 5)],
        )
        gavetas = self._produto(
            loja_filamentos, "organizadores", "Pacote Digital: Gavetas Modulares",
            "Pacote com gavetas e trilhos modulares em STL e 3MF, com perfis de fatiamento.", D, "32.00", "#10b981",
            arquivos=[(arq.stl_cubo, "gaveta-modular.stl", "Gaveta"), (arq.tmf_cubo, "gaveta-modular.3mf", "Projeto 3MF"),
                      (arq.obj_cubo, "trilho.obj", "Trilho em OBJ")],
        )
        self._produto(
            loja_filamentos, "suportes", "Modelo CAD: Suporte de Celular Articulado",
            "Arquivo STEP editável para adaptar o suporte a qualquer aparelho.", D, "12.90", "#6366f1",
            arquivos=[(arq.step_demo, "suporte-celular.step", "Modelo CAD")],
        )
        self._produto(
            loja_atelie, "decoracao", "Busto Clássico em Resina",
            "Busto decorativo de 18 cm. Indisponível enquanto a loja estiver inativa.", F, "149.00", "#a855f7",
            variacoes=[("Resina", "Branco", "18 cm", "0", 2)],
        )
        out("  produtos, variações, imagens e arquivos digitais criados")

        # Carrinhos ----------------------------------------------------
        for comprador, itens in (
            (ana, [(vaso, vaso.variacoes_demo[0], 2), (vaso_stl, None, 1)]),
            (bruno, [(engrenagem, engrenagem.variacoes_demo[0], 4)]),
            (carla, []),
        ):
            carrinho = Carrinho.objects.create(comprador=comprador)
            for produto, variacao, quantidade in itens:
                item = ItemCarrinho(carrinho=carrinho, produto=produto, variacao=variacao, quantidade=quantidade)
                item.full_clean()
                item.save()

        # Pedidos ------------------------------------------------------
        p1 = registrar_pedido(
            ana,
            [(vaso, vaso.variacoes_demo[1], 1), (luminaria, luminaria.variacoes_demo[0], 1), (miniaturas, miniaturas.variacoes_demo[0], 1), (gavetas, None, 1)],
            end_ana_casa,
        )
        p1.status = StatusPedido.EM_ANDAMENTO
        p1.save(update_fields=["status"])
        sub_oficina = p1.subpedidos.get(loja=loja_oficina)
        sub_oficina.status = StatusPedido.EM_ANDAMENTO
        sub_oficina.save(update_fields=["status"])
        sub_oficina.pagamento.confirmar(oficina, "Confirmação manual do vendedor (simulada).")

        p2 = registrar_pedido(bruno, [(vaso_stl, None, 1)])  # somente digital: sem endereço
        p2.status = StatusPedido.CONCLUIDO
        p2.save(update_fields=["status"])
        sub = p2.subpedidos.get()
        sub.status = StatusPedido.CONCLUIDO
        sub.save(update_fields=["status"])
        sub.pagamento.confirmar(admin, "Confirmação manual do administrador (simulada).")

        registrar_pedido(carla, [(organizador, organizador.variacoes_demo[1], 2)], end_carla)

        # O vendedor da Oficina Camadas também compra, como comprador, de outra loja.
        p4 = registrar_pedido(oficina, [(engrenagem, engrenagem.variacoes_demo[0], 3)], end_oficina)
        cancelar_pedido(oficina, p4)  # cancelado pelo comprador: estoque devolvido
        out("  carrinhos, pedidos, subpedidos e pagamentos simulados criados")

        # Orçamentos (todos os estados) --------------------------------
        perfil_oficina = PerfilVendedor.objects.get(usuario=oficina)
        perfil_filamentos = PerfilVendedor.objects.get(usuario=filamentos)
        self._orcamento(ana, perfil_oficina, "PETG", "Preto", "8 x 4 x 2 cm", 2,
                        "Peça de reposição para o suporte da prateleira.")
        respondido = self._orcamento(bruno, perfil_filamentos, "Nylon", "Natural", "Ø 40 mm", 4,
                                     "Engrenagens para um braço robótico.")
        respondido.responder(filamentos, Decimal("35.00"), "Prazo de 5 dias úteis após o aceite.")
        aceito = self._orcamento(ana, perfil_filamentos, "Resina", "Cinza", "Altura 75 mm", 1,
                                 "Miniatura personalizada a partir do meu modelo.")
        aceito.responder(filamentos, Decimal("120.00"), "Inclui suportes removidos e lixamento.")
        aceito.aceitar(ana, end_ana_casa)  # gera o pedido automaticamente
        recusado = self._orcamento(carla, perfil_oficina, "PLA", "Verde", "15 x 15 x 10 cm", 1,
                                   "Caixa organizadora com tampa.")
        recusado.responder(oficina, Decimal("95.00"), "Prazo de 3 dias úteis.")
        recusado.recusar(carla)
        self._orcamento(bruno, perfil_oficina, "PLA", "Amarelo", "10 cm", 3, "Chaveiros personalizados.").cancelar(bruno)
        self._orcamento(oficina, perfil_filamentos, "Resina", "Transparente", "5 x 5 x 5 cm", 10,
                        "Pedido do vendedor Otávio atuando como comprador.")
        out("  orçamentos criados (pendente, respondido, aceito com pedido, recusado e cancelado)")
