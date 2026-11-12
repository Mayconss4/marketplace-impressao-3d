# Roteiro de apresentação — Checkpoint 2

**Duração sugerida:** 12–15 minutos. **Preparação (antes da aula):**

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py popular_demo --recriar
python manage.py runserver
```

Deixe abertas duas janelas do navegador (uma anônima) para alternar perfis sem sair da conta.
Todas as contas demo usam a senha **`Demo@2026`**.

| Conta | Perfil |
|---|---|
| `demo_admin` | Administrador |
| `demo_oficina` | Vendedor (loja *Oficina Camadas*) e comprador |
| `demo_filamentos` | Vendedor (loja *Filamento & Cia*) |
| `demo_ana` | Comprador com carrinho, pedidos e orçamentos |
| `demo_bruno` | Comprador com orçamento **respondido** e compra digital paga |

O quadro abaixo segue os critérios do Checkpoint 2 no enunciado.

---

## 1. Login, logout e cadastre-se (20%) — 3 min
1. Janela anônima, menu superior: **Cadastre-se** → preencher usuário, nome, e-mail e senha → a conta é criada e já entra
   logada em **Minha conta**. Mostrar que o perfil é só "Comprador" (menu do usuário).
2. Validações: repetir um e-mail já usado (ex.: `ana@exemplo.invalid` em maiúsculas) e senhas diferentes → erros no formulário.
3. **Sair** pelo menu do usuário → volta à vitrine. **Entrar** com `demo_ana` → cai em **Minha conta**.
4. Sem login, abrir `/minha-conta/pedidos/` → redireciona para o login (área do usuário protegida).
5. Comprador em `/admin/` → redirecionado ao login do painel (área administrativa protegida e separada).

## 2. Área do usuário final e CRUD — 4 min (janela `demo_ana`)
1. **Endereços**: criar "Sítio", editar o número, excluir (CRUD completo). Tentar repetir o apelido "Casa" → erro.
2. **Produtos** (menu): buscar "vaso"; filtrar categoria *Decoração* (traz Vasos e Luminárias); tipo *Arquivos digitais*; ordenar por preço.
3. Abrir *Luminária Lua* → escolher variação → **Adicionar ao carrinho**. Tentar quantidade acima do estoque → mensagem de estoque insuficiente.
4. **Carrinho**: alterar quantidade, remover item. Mostrar que o digital tem quantidade fixa 1.
5. **Finalizar compra** → escolher endereço → **Confirmar pedido**. Mostrar o pedido dividido por loja (subpedidos),
   com status e pagamento simulado de cada loja.
6. No pedido recém-criado: **Cancelar pedido** → subpedidos cancelados e estoque devolvido (conferir na página do produto).
7. **Meus orçamentos → Novo orçamento**: enviar um `.stl`, escolher a loja. Mostrar que um `.png` é recusado.

## 3. Fluxo completo entre perfis — 3 min
1. Janela anônima com `demo_bruno` → **Meus orçamentos** → orçamento *Respondido* → **Aceitar e gerar pedido** → abre o pedido gerado.
2. Ainda como Bruno: pedido do *Modelo Digital: Vaso Espiral* (pagamento confirmado) → botão de **download** liberado.
3. Como `demo_ana`: pedido com *Pacote Digital: Gavetas Modulares* → download **bloqueado** (pagamento pendente).
4. Janela 1 com `demo_filamentos` → painel → **Subpedidos** → ação **Confirmar pagamento simulado** no subpedido da Ana.
5. Volta à Ana → atualizar o pedido → download liberado.
6. Como `demo_oficina` (vendedor): abrir um produto da própria loja → aviso "este produto é da sua loja", sem botão de compra.

## 4. Banco de dados integrado ao ambiente administrativo (20%) — 2 min (janela `demo_admin`)
- Tudo o que foi feito no site aparece no painel: o usuário cadastrado em *Usuários* (filtro *Perfil funcional*),
  o pedido e seus subpedidos/pagamentos em *Pedidos* (filtros de status, origem, várias lojas), o orçamento em *Orçamentos*.
- **Quero vender**: com o usuário recém-cadastrado, enviar a solicitação (CPF válido, ex.: `529.982.247-25`).
  No painel, *Solicitações de vendedor* → filtro *Pendente* → ação **Aprovar**. De volta ao site, o menu mostra
  "Minha loja" e o link **Painel admin**.

## 5. Framework CSS e interface amigável (10%) — 1 min
- Bootstrap 5.3 + Bootstrap Icons; menu responsivo (reduzir a janela → menu recolhido); botão de **tema claro/escuro** no topo
  (lembrado no navegador); mensagens de sucesso/erro; estados vazios; badges de status coloridos; Jazzmin no painel com o mesmo laranja.

## 6. Documentação (10%) — 1 min
- `README.md`: nome, integrantes, descrição, tecnologias, instalação, execução, principais funcionalidades, estrutura.
- `docs/diagrama-er.md`: modelagem; este roteiro; branches `main`, `develop` e `feature/*` no GitHub.

## 7. Complexidade (40%) — 1 min
- 6 apps, 17 entidades, 40+ restrições no banco, transações atômicas (checkout, cancelamento, aceite de orçamento),
  pedido multiloja com subpedidos e pagamento por loja, mídia privada com liberação condicionada ao pagamento,
  isolamento entre vendedores no servidor, 44 testes automatizados (`python manage.py test apps`).
