# Roteiro de apresentação — Checkpoint 1

**Duração sugerida:** 12–15 minutos. **Preparação (antes da aula):**

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py popular_demo --recriar
python manage.py runserver
```

Deixe abertas três janelas do navegador (uma delas anônima), para alternar perfis sem sair da conta:

| Janela | Conta | Senha | Perfil |
|---|---|---|---|
| 1 | `demo_admin` | `Demo@2026` | Administrador |
| 2 | `demo_oficina` | `Demo@2026` | Vendedor aprovado (loja *Oficina Camadas*) e comprador |
| 3 (anônima) | `demo_ana` | `Demo@2026` | Somente comprador |

> Legenda: ✅ **concluído e demonstrável** · 🧩 **apenas modelado/preparado** (interface no Checkpoint 2).

---

## 1. Tema (1 min)
- Marketplace de impressão 3D com **vários vendedores independentes**: produtos físicos impressos, arquivos digitais (STL, 3MF, OBJ, STEP) e **orçamentos** de impressão personalizada.
- Uma mesma conta compra e, após aprovação, vende.

## 2. Arquitetura Django (1 min)
- Projeto `config/` + 6 apps em `apps/`, padrão MVT, SQLite, Django 5.2 LTS, Jazzmin, Bootstrap 5.3.
- Usuário personalizado (`AUTH_USER_MODEL = contas.Usuario`) desde a primeira migração.

## 3. Organização dos apps (1 min)
Mostrar a árvore no editor: `contas` → `vendedores` → `catalogo` → `orcamentos` → `pedidos`, e `core` (home, login, arquivos privados, seed). Dependências em **uma só direção**.

## 4. Modelagem do banco (2 min)
- Abrir `docs/diagrama-er.md` (renderizado no GitHub/VS Code). 17 tabelas próprias.
- Destacar: **snapshot** de endereço e de preço no pedido; `DecimalField` em todo valor monetário; `PROTECT` no histórico.

## 5. Relacionamentos principais (1 min)
- Usuário 1–1 PerfilVendedor 1–1 Loja (exatamente uma loja por vendedor).
- Pedido 1–N SubPedido (um por loja) 1–N ItemPedido; SubPedido 1–1 PagamentoSimulado.
- Orçamento 1–1 ItemPedido (**impede pedido duplicado** da mesma proposta).
- Categoria → Categoria pai (árvore, sem ciclos).

## 6. Jazzmin ✅ (1 min) — janela 1
- Login do painel com logotipo, cores laranja/grafite, menu lateral agrupado e com ícones, busca global (Produtos/Lojas), alternância claro/escuro do Jazzmin.
- Formulários em abas (ex.: abrir um Produto: abas Identificação, Comercial, Imagens, Variações).

## 7. Filtros e buscas ✅ (2 min) — janela 1
- **Produtos:** filtros *Tipo*, *Disponibilidade* (mostra "Busto Clássico" bloqueado por loja inativa), *Estoque* (Esgotado/Baixo/Ilimitado), *Categoria com subcategorias* (escolher "Decoração" traz Vasos e Luminárias), *Faixa de preço*, *Loja*, datas. Buscar "vaso".
- **Categorias:** listagem em árvore com caminho "Decoração → Vasos"; filtro *Nível*.
- **Pedidos:** filtro *Lojas no pedido = Várias lojas* (pedido da Ana com 2 subpedidos), *Origem = Orçamento aceito*, *Entrega = Somente digital*.
- **Usuários:** filtro *Perfil funcional* (comprador, vendedor, solicitante pendente, administrador).

## 8. Aprovação de vendedor ✅ (2 min) — janelas 1 e 3
1. Janela 3: entrar no site como **`demo_diego`** e tentar `/admin/` → bloqueado (é só comprador, solicitação pendente).
2. Janela 1: *Solicitações de vendedor* → filtrar *Pendente* → selecionar Diego → ação **Aprovar**. Mostrar que o registro analisado vira somente leitura.
3. Janela 3: atualizar `/admin/` → Diego agora entra com o menu de vendedor, sem enxergar registros de terceiros; em *Lojas* pode criar **uma** loja (o nome vem preenchido da solicitação) e, só depois dela, cadastrar produtos.
4. Mostrar a solicitação **recusada** de `demo_elisa`: a conta continua compradora.

## 9. Produtos e variações ✅ (2 min) — janela 2 (`demo_oficina`)
- Lista mostra **somente** produtos da Oficina Camadas; filtro de loja nem aparece.
- Abrir *Vaso Geométrico*: variações com material/cor/dimensão, ajuste ±, preço final e estoque.
- Tentar ajuste **-100,00** → erro "preço final ficaria negativo". Tentar duplicar "PLA / branco / Pequeno (12 cm)" → erro de combinação duplicada.
- Marcar duas imagens como principais → erro "Marque apenas uma imagem como principal" (o banco também impede).
- Abrir *Modelo Digital: Vaso Espiral*: sem aba de variações; arquivo com cadeado (download protegido).

## 10. Pedidos e orçamentos ✅/🧩 (2 min)
- Janela 2: *Subpedidos* → só os da própria loja; abrir um e mostrar itens com preço congelado, dados de entrega do comprador e pagamento simulado. Ação **Confirmar pagamento simulado**.
- Janela 2: *Orçamentos* → abrir o **pendente** da Ana → informar preço unitário → status vira *Respondido* e o total é calculado.
- Janela 1: orçamento **Aceito** → link para o pedido gerado automaticamente.
- 🧩 Aceite/recusa pelo comprador, carrinho e checkout: regras e serviços prontos no modelo; telas no Checkpoint 2.

## 11. Permissões ✅ (1 min)
- Janela 2: digitar na URL o ID de um produto da *Filamento & Cia* → o admin responde que o registro não existe.
- Acessar `/admin/contas/usuario/` como vendedor → **403**.
- Janela 3 (`demo_ana`): `/admin/` → redireciona ao login do painel. Copiar o link de um arquivo privado (da janela 1) e abrir como `demo_carla` → **403**; deslogado → tela de login.
- Mencionar a suíte: `python manage.py test apps` (24 testes de admin, perfis, arquivos e integridade).

## 12. Complexidade e Checkpoint 2 (1 min)
- Complexidade: 17 entidades com 40+ restrições no banco, transações atômicas, isolamento entre vendedores no servidor, mídia privada, snapshots históricos.
- Checkpoint 2 (🧩): cadastro público, área do comprador (endereços, carrinho, checkout, histórico, aceite de orçamento, downloads digitais), painel comercial fora do admin.
