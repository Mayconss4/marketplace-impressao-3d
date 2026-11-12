# Marketplace 3D - Marketplace de Venda de Produtos de Impressão 3D

Trabalho da disciplina **GAC116 - Programação Web** (Projeto de Implementação com Django).
**Entrega atual:** Checkpoint 2 — aplicação concluída (apresentação em 19/11/2026).

**Integrantes**
- Maycon Henrique Soares de Sousa
- Luan Yudi Shimosaka

---

## Descrição e objetivo

Marketplace em que **vários vendedores independentes** comercializam:

- **produtos físicos** impressos em 3D, com variações de material, cor e tamanho e estoque por variação;
- **produtos digitais** (arquivos STL, 3MF, OBJ e STEP), com estoque ilimitado e arquivos privados;
- **impressões personalizadas sob orçamento**, a partir de um arquivo 3D enviado pelo comprador.

Uma mesma conta compra e, depois de aprovada por um administrador, também vende. Um pedido pode reunir
produtos de várias lojas: ele é dividido em **subpedidos por loja**, cada um com estado e pagamento
simulado próprios.


## Tecnologias e versões

| Tecnologia | Versão |
|---|---|
| Python | 3.12 (testado com 3.12.10) |
| Django | 5.2 LTS (5.2.18) |
| django-jazzmin | 3.0.5 (declara suporte ao Django 5.2) |
| Pillow | 13.0.0 (campos de imagem) |
| SQLite | embutido no Python |
| Bootstrap | 5.3.3 + Bootstrap Icons 1.11.3 (via CDN jsDelivr, com SRI) |

Dependências exatas em [requirements.txt](requirements.txt). Nenhum serviço externo, gateway de pagamento ou nuvem é usado.

## Requisitos de ambiente

- Windows com PowerShell.
- Python 3.12 instalado (verifique com `py -3.12 --version`). Para instalar: `winget install Python.Python.3.12`.
- Acesso à internet apenas para instalar dependências e carregar o Bootstrap por CDN.

## Instalação e execução (PowerShell)

```powershell
# 1. Na pasta do projeto, criar e ativar o ambiente virtual
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
# Se o PowerShell bloquear scripts: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 2. Instalar as dependências
python -m pip install -r requirements.txt

# 3. Criar o banco SQLite (db.sqlite3) e aplicar as migrações
python manage.py migrate

# 4. (Opcional) Criar seu próprio superusuário
python manage.py createsuperuser

# 5. Popular com dados demonstrativos fictícios
python manage.py popular_demo

# 6. Iniciar o servidor
python manage.py runserver
```

| Página | Endereço |
|---|---|
| Início (vitrine) | <http://127.0.0.1:8000/> |
| Catálogo com busca e filtros | <http://127.0.0.1:8000/produtos/> |
| Cadastre-se | <http://127.0.0.1:8000/cadastro/> |
| Login / logout | <http://127.0.0.1:8000/entrar/> · botão **Sair** no menu do usuário |
| Área do usuário (comprador) | <http://127.0.0.1:8000/minha-conta/> |
| Django Admin (Jazzmin) | <http://127.0.0.1:8000/admin/> |

O banco usado é o SQLite em `db.sqlite3` (configurado em `config/settings.py`); não há configuração adicional.
Em produção, defina as variáveis `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` e `DJANGO_ALLOWED_HOSTS`.

### Dados demonstrativos

O comando `popular_demo` cria dados **fictícios** e consistentes entre si. Todas as contas usam a senha
**`Demo@2026`** (somente para desenvolvimento).

| Conta | Perfil | O que demonstra |
|---|---|---|
| `demo_admin` | Administrador | Controle integral, aprovação de vendedores |
| `demo_oficina` | Vendedor PF (loja **Oficina Camadas**, ativa) e comprador | Isolamento entre vendedores; também compra de outra loja |
| `demo_filamentos` | Vendedor PJ (loja **Filamento & Cia**, ativa) | Produtos físicos e digitais, orçamentos |
| `demo_atelie` | Vendedor PF (loja **Ateliê Resina Fina**, **inativa**) | Produto ativo que não aparece na vitrine |
| `demo_ana`, `demo_bruno`, `demo_carla` | Compradores | Endereços, carrinhos, pedidos e orçamentos |
| `demo_diego` | Comprador com solicitação **pendente** | Aprovação durante a apresentação |
| `demo_elisa` | Comprador com solicitação **recusada** | Continua apenas como comprador |

Também são criadas 11 categorias (incluindo subcategorias e uma inativa), 10 produtos, 13 variações,
imagens e logotipos gerados pelo próprio comando, 5 arquivos digitais privados, 6 orçamentos (todos os estados),
3 carrinhos e 5 pedidos (um com subpedidos de duas lojas, um somente digital, um gerado por orçamento aceito)
com pagamentos simulados pendentes e confirmados. CPFs/CNPJs têm dígitos verificadores válidos, mas são gerados
artificialmente; e-mails usam o domínio reservado `exemplo.invalid`.

```powershell
python manage.py popular_demo            # cria; se já existirem, não duplica nada
python manage.py popular_demo --recriar  # remove os dados demo e cria de novo
python manage.py popular_demo --limpar   # remove somente os dados demo
```

A remoção atua **apenas** sobre contas cujo username começa com `demo_`, seus registros e as categorias demo
que não estejam em uso. Se algum dado real depender dos dados demo (por exemplo, um pedido real feito numa loja demo),
a remoção é abortada sem apagar nada. Os arquivos enviados são apagados do disco somente após a confirmação
da transação.

## Estrutura do projeto

```
marketplace-impressao-3d/
├── manage.py
├── requirements.txt
├── config/                  # settings (SQLite, Jazzmin, mídia pública/privada) e URLs raiz
├── apps/
│   ├── core/                # home, painel do usuário, login, arquivos privados, utilitários do admin,
│   │   │                    # validadores, armazenamento privado, testes (tests.py e tests_area_usuario.py)
│   │   └── management/commands/popular_demo.py
│   ├── contas/              # Usuario (AbstractUser), Endereco; cadastro, dados, senha e endereços
│   ├── vendedores/          # SolicitacaoVendedor, PerfilVendedor, Loja, grupo "Vendedores"; solicitação pelo site
│   ├── catalogo/            # Categoria, Produto, VariacaoProduto, ImagemProduto, ArquivoDigital; vitrine pública
│   ├── orcamentos/          # Orcamento; envio e decisão pelo comprador
│   └── pedidos/             # Carrinho, ItemCarrinho, Pedido, SubPedido, ItemPedido, PagamentoSimulado,
│                            # serviços transacionais (servicos.py), carrinho/checkout/pedidos
├── templates/
│   ├── base.html            # layout, menu responsivo, alternância de tema
│   ├── area_conta.html      # layout da área do usuário (menu lateral)
│   ├── includes/            # card de produto, campos de formulário, badges, estado vazio
│   ├── core/                # home, painel "Minha conta"
│   ├── registration/        # login
│   ├── contas/              # cadastro, dados, senha, endereços (CRUD)
│   ├── catalogo/            # lista com filtros e detalhe do produto
│   ├── pedidos/             # carrinho, checkout, lista e detalhe de pedidos
│   ├── orcamentos/          # lista, novo, detalhe (aceitar/recusar/cancelar)
│   └── vendedores/          # solicitação de vendedor / minha loja
├── static/                  # logo, CSS do site e do admin, JS (tema e formulário de produto)
├── docs/
│   ├── diagrama-er.md       # diagrama ER em Mermaid + políticas de exclusão e restrições
│   ├── roteiro-apresentacao.md   # roteiro do Checkpoint 1
│   └── roteiro-checkpoint2.md    # roteiro do Checkpoint 2 (passo a passo de validação)
├── media/                   # (gerada) mídia PÚBLICA: imagens de produtos e logotipos
└── private_media/           # (gerada) mídia PRIVADA: arquivos digitais e de orçamentos
```

### Organização dos apps

As dependências seguem **uma única direção**, sem referências circulares:
`contas` → `vendedores` → `catalogo` → `orcamentos` → `pedidos`. O app `core` reúne o que é transversal
(páginas públicas, validadores de CPF/CNPJ/telefone/formatos 3D, armazenamento privado, mixin de isolamento do admin).
Cada app de domínio tem seus próprios `views.py`, `urls.py` (com namespace) e `forms.py` (padrão MVT).

## Modelagem

17 entidades próprias. Diagrama completo, cardinalidades, políticas `on_delete` e restrições em
[docs/diagrama-er.md](docs/diagrama-er.md). Destaques:

- **Usuário personalizado** (`AUTH_USER_MODEL = "contas.Usuario"`) com nome e e-mail obrigatórios e e-mail único sem diferenciar maiúsculas.
- **Vendedor**: a `SolicitacaoVendedor` (PF/CPF ou PJ/CNPJ validados) só vira `PerfilVendedor` pela aprovação do administrador; cada perfil tem no máximo **uma** `Loja`.
- **Categorias hierárquicas** com bloqueio de ciclos; listagem em árvore no admin.
- **Produto físico**: preço final = preço base + ajuste da variação (nunca negativo); estoque por variação (nunca negativo); combinação material/cor/dimensão única. Um produto físico só aparece na vitrine quando tem ao menos uma variação.
- **Produto digital**: sem variações, estoque ilimitado, quantidade fixa em 1 no carrinho e no pedido; arquivos em armazenamento privado.
- **Imagens**: várias por produto, no máximo uma principal (índice único parcial no banco).
- **Orçamento**: estados Pendente → Respondido → Aceito/Recusado, ou Cancelado; o vendedor propõe **preço unitário** (total = unitário × quantidade). O aceite gera o pedido na mesma transação, e o vínculo 1–1 com o item do pedido impede pedidos duplicados.
- **Pedido → SubPedido (por loja) → ItemPedido**, com estados independentes (Pendente, Em andamento, Concluído, Cancelado). Nome, variação, preço e endereço ficam **copiados** no pedido para preservar o histórico.
- **PagamentoSimulado**: um por subpedido, Pendente/Confirmado, confirmação manual registrando quem e quando. Não há transação financeira real.
- Valores monetários sempre em `DecimalField`; operações que gravam vários registros usam `transaction.atomic`.

## Perfis e permissões

| Perfil | Como é definido | Acesso |
|---|---|---|
| **Administrador** | `is_superuser` | Tudo no painel: usuários, aprovações, lojas, categorias, produtos, pedidos; consulta orçamentos e pagamentos. |
| **Vendedor** | `PerfilVendedor` criado pela aprovação + grupo `Vendedores` + `is_staff` (só para entrar no painel) | Própria loja, próprios produtos/variações/imagens/arquivos, orçamentos destinados a ele (responde os pendentes), próprios subpedidos e pagamentos simulados; categorias apenas para consulta. |
| **Comprador** | Qualquer conta ativa (inclusive criada em *Cadastre-se*) | Área do usuário no site (`/minha-conta/`): pedidos, orçamentos, carrinho, endereços, dados e senha, solicitação de vendedor. **Não** acessa o painel. |

O isolamento é aplicado **no servidor**, não só ocultando menus: os ModelAdmins filtram `get_queryset`
(listas, buscas, autocomplete e acesso direto por ID), revalidam a posse em `has_view/change/delete_permission`,
limitam as opções de chaves estrangeiras e definem a loja do vendedor em `save_model`, ignorando valores
forjados no POST. O vendedor não acessa usuários, solicitações, pedidos principais (que podem conter outras
lojas) nem carrinhos, e não altera permissões de ninguém. Pedidos, subpedidos e pagamentos não podem ser
excluídos pelo painel (histórico).

**Arquivos privados**: ficam em `private_media/`, fora da pasta pública, e são servidos apenas por
`/arquivos-privados/...`, que exige login e verifica a autorização: arquivos de orçamento → comprador,
vendedor destinatário e administrador; arquivos de produto digital → vendedor dono, administrador e o **comprador,
depois que o pagamento simulado do subpedido for confirmado**.

## Django Admin (Jazzmin)

- Identidade visual própria: nome "Marketplace 3D", logotipo, tema *flatly* com acentos laranja, modo claro/escuro automático, CSS complementar.
- Menu lateral ordenado por domínio com ícones; busca global por Produtos e Lojas; formulários em abas.
- **Filtros**: situação e tipo de pessoa da solicitação; status da loja; categoria (incluindo subcategorias); nível da categoria; tipo, status e disponibilidade do produto; condição de estoque (esgotado, baixo, ilimitado, físico sem variação); faixa de preço; loja/vendedor (só para o administrador); status de orçamentos e se já geraram pedido; status de pedidos, subpedidos e pagamentos; pedidos com várias lojas, origem (catálogo/orçamento) e tipo de entrega; perfil funcional do usuário; carrinho vazio; datas de criação/atualização.
- **Buscas textuais** em usuários, solicitações, lojas, categorias, produtos, variações, orçamentos, pedidos e pagamentos.
- **Ações**: aprovar/recusar solicitações, ativar/desativar lojas e anúncios, alterar status de pedidos/subpedidos, confirmar pagamento simulado.

## Principais funcionalidades

**Área pública**
- Vitrine na página inicial e **catálogo** com busca textual, filtro por categoria (inclui subcategorias), tipo e loja,
  ordenação por preço/nome/data e paginação.
- Página do produto com galeria de imagens, variações (material/cor/tamanho, preço e estoque) e produtos relacionados.
- **Cadastre-se**, **login** e **logout**; tema claro/escuro lembrado no navegador; layout responsivo (Bootstrap 5.3).

**Área do usuário final** (`/minha-conta/`, exige login)
- **Visão geral** com pedidos em aberto, propostas para decidir, itens no carrinho e atalhos.
- **Endereços**: cadastrar, listar, editar e excluir (CRUD), isolados por usuário.
- **Dados e senha**: editar nome/e-mail (e-mail único) e trocar a senha.
- **Carrinho**: adicionar (físico exige variação; digital tem quantidade fixa 1), alterar quantidade com checagem de
  estoque, remover. Vendedores não compram da própria loja.
- **Checkout**: escolha do endereço (dispensado para pedidos só digitais); gera o pedido dividido em **subpedidos por loja**,
  copia preços e endereço, baixa o estoque e cria os pagamentos simulados, tudo em uma transação.
- **Meus pedidos**: lista com filtro de status e detalhe por loja (status do subpedido e do pagamento).
  **Cancelamento** de pedido pendente: cancela todos os subpedidos e devolve o estoque (bloqueado se algum subpedido
  já andou ou teve pagamento confirmado).
- **Downloads digitais** liberados no detalhe do pedido depois que a loja confirma o pagamento simulado.
- **Meus orçamentos**: enviar arquivo 3D (STL/3MF/OBJ/STEP) a uma loja, acompanhar, **aceitar** a proposta escolhendo o
  endereço (gera o pedido), **recusar** ou **cancelar**. Ninguém pede orçamento à própria loja.
- **Quero vender**: solicitação de vendedor com CPF/CNPJ validados e acompanhamento do status. Depois de aprovado, o
  usuário vê "Minha loja" e acessa o painel do vendedor.

**Área administrativa** (`/admin/`, Jazzmin)
- Administrador: controle integral, aprovação/recusa de vendedores, categorias, lojas, produtos, pedidos, pagamentos.
- Vendedor: própria loja, produtos/variações/imagens/arquivos, orçamentos recebidos (responde com preço unitário),
  próprios subpedidos e confirmação de pagamento simulado; isolamento entre vendedores no servidor.

## Verificações

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test apps
```

São 44 testes automatizados:
- `apps/core/tests.py` (25): todas as listagens do admin com cada filtro e busca; formulários de edição; isolamento entre
  vendedores (listas, acesso por ID, POST forjado); bloqueio do comprador no painel; aprovação de vendedor; resposta
  de orçamento; validações dos inlines de produto; arquivos privados; restrições de integridade.
- `apps/core/tests_area_usuario.py` (19): cadastro, login e área protegida; troca de senha; CRUD e isolamento de
  endereços; filtros do catálogo; carrinho (estoque, digital, autocompra); checkout; cancelamento com devolução de
  estoque; liberação de downloads após o pagamento; envio, aceite, recusa e cancelamento de orçamentos;
  solicitação de vendedor; abertura de todas as telas com cada perfil.

## Controle de versão

Repositório público: <https://github.com/Mayconss4/marketplace-impressao-3d>

| Branch | Uso |
|---|---|
| `main` | versão estável entregue em cada checkpoint |
| `develop` | integração das funcionalidades |
| `feature/*` | uma branch por funcionalidade (ex.: `feature/cadastro-contas`, `feature/carrinho-checkout`), integrada em `develop` com merge |

O `.gitignore` exclui `.venv/`, `db.sqlite3`, `media/` e `private_media/`.
