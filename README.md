# Marketplace 3D - Marketplace de Venda de Produtos de Impressão 3D

Trabalho da disciplina **GAC116 - Programação Web** (Projeto de Implementação com Django).
**Entrega atual:** Checkpoint 1 (apresentação em 05/11/2026).

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

- Página inicial: <http://127.0.0.1:8000/>
- Login do site: <http://127.0.0.1:8000/entrar/>
- Django Admin (Jazzmin): <http://127.0.0.1:8000/admin/>

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
│   ├── core/                # home, login, view de arquivos privados, utilitários do admin,
│   │   │                    # validadores, armazenamento privado, testes
│   │   └── management/commands/popular_demo.py
│   ├── contas/              # Usuario (AbstractUser), Endereco
│   ├── vendedores/          # SolicitacaoVendedor, PerfilVendedor, Loja, grupo "Vendedores"
│   ├── catalogo/            # Categoria, Produto, VariacaoProduto, ImagemProduto, ArquivoDigital
│   ├── orcamentos/          # Orcamento
│   └── pedidos/             # Carrinho, ItemCarrinho, Pedido, SubPedido, ItemPedido,
│                            # PagamentoSimulado e serviços transacionais (servicos.py)
├── templates/               # base.html, core/home.html, registration/login.html
├── static/                  # logo, CSS do site e do admin, JS (tema e formulário de produto)
├── docs/
│   ├── diagrama-er.md       # diagrama ER em Mermaid + políticas de exclusão e restrições
│   └── roteiro-apresentacao.md
├── media/                   # (gerada) mídia PÚBLICA: imagens de produtos e logotipos
└── private_media/           # (gerada) mídia PRIVADA: arquivos digitais e de orçamentos
```

### Organização dos apps

As dependências seguem **uma única direção**, sem referências circulares:
`contas` → `vendedores` → `catalogo` → `orcamentos` → `pedidos`. O app `core` reúne o que é transversal
(páginas públicas, validadores de CPF/CNPJ/telefone/formatos 3D, armazenamento privado, mixin de isolamento do admin).

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
| **Comprador** | Qualquer conta ativa | Login no site; **não** acessa o painel. A área do comprador é do Checkpoint 2. |

O isolamento é aplicado **no servidor**, não só ocultando menus: os ModelAdmins filtram `get_queryset`
(listas, buscas, autocomplete e acesso direto por ID), revalidam a posse em `has_view/change/delete_permission`,
limitam as opções de chaves estrangeiras e definem a loja do vendedor em `save_model`, ignorando valores
forjados no POST. O vendedor não acessa usuários, solicitações, pedidos principais (que podem conter outras
lojas) nem carrinhos, e não altera permissões de ninguém. Pedidos, subpedidos e pagamentos não podem ser
excluídos pelo painel (histórico).

**Arquivos privados**: ficam em `private_media/`, fora da pasta pública, e são servidos apenas por
`/arquivos-privados/...`, que exige login e verifica a autorização: arquivos de orçamento → comprador,
vendedor destinatário e administrador; arquivos de produto digital → vendedor dono e administrador.

## Django Admin (Jazzmin)

- Identidade visual própria: nome "Marketplace 3D", logotipo, tema *flatly* com acentos laranja, modo claro/escuro automático, CSS complementar.
- Menu lateral ordenado por domínio com ícones; busca global por Produtos e Lojas; formulários em abas.
- **Filtros**: situação e tipo de pessoa da solicitação; status da loja; categoria (incluindo subcategorias); nível da categoria; tipo, status e disponibilidade do produto; condição de estoque (esgotado, baixo, ilimitado, físico sem variação); faixa de preço; loja/vendedor (só para o administrador); status de orçamentos e se já geraram pedido; status de pedidos, subpedidos e pagamentos; pedidos com várias lojas, origem (catálogo/orçamento) e tipo de entrega; perfil funcional do usuário; carrinho vazio; datas de criação/atualização.
- **Buscas textuais** em usuários, solicitações, lojas, categorias, produtos, variações, orçamentos, pedidos e pagamentos.
- **Ações**: aprovar/recusar solicitações, ativar/desativar lojas e anúncios, alterar status de pedidos/subpedidos, confirmar pagamento simulado.

## Funcionalidades - situação no Checkpoint 1

**Concluídas e verificadas**
- Modelagem completa com migrações aplicadas e restrições no banco.
- Painel Jazzmin com ModelAdmins, inlines, filtros, buscas e ações.
- Aprovação/recusa de vendedores; criação da loja pelo vendedor aprovado.
- Isolamento entre vendedores no painel; comprador bloqueado no painel.
- Resposta de orçamento pelo vendedor; geração de pedido a partir de orçamento aceito (via modelo/serviço).
- Página inicial com produtos disponíveis, login/logout, navegação responsiva, tema claro/escuro.
- Download protegido de arquivos privados para os perfis autorizados.
- Comando de dados demonstrativos repetível e removível.

**Somente modeladas/preparadas (interface no Checkpoint 2)**
- Cadastro público de usuários e solicitação de vendedor pelo site.
- Área do comprador: endereços, carrinho, checkout (o serviço `registrar_pedido` já valida estoque, disponibilidade e endereço e baixa o estoque), histórico de pedidos, cancelamento de pedido pendente.
- Aceite/recusa/cancelamento de orçamento pelo comprador na interface (as transições existem no modelo).
- Liberação de arquivos digitais ao comprador após a conclusão da compra.
- Painel comercial do vendedor fora do Django Admin.

## Verificações

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test apps
```

A suíte em `apps/core/tests.py` (25 testes) cobre: abertura de todas as listagens do admin com cada opção
de filtro e busca; formulários de edição; isolamento entre vendedores (listas, acesso por ID, POST forjado);
bloqueio do comprador; aprovação de vendedor; resposta de orçamento; validações dos inlines de produto;
acesso a arquivos privados; e restrições de integridade.

## Publicação no GitHub

A criação do repositório e os commits são feitos manualmente pelos integrantes. O `.gitignore` já exclui
`.venv/`, `db.sqlite3`, `media/` e `private_media/`.
