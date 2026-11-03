# Diagrama entidade-relacionamento

Reflete os models implementados em `apps/*/models.py` e as migrações `0001_initial` de cada app.
Os nomes de tabela no SQLite seguem o padrão do Django (`<app>_<modelo>`, ex.: `catalogo_produto`).

Legenda de cardinalidade (Mermaid): `||` exatamente um · `|o` zero ou um · `o{` zero ou muitos.

```mermaid
erDiagram
    USUARIO ||--o{ ENDERECO : "cadastra"
    USUARIO ||--o{ SOLICITACAO_VENDEDOR : "solicita"
    USUARIO |o--o{ SOLICITACAO_VENDEDOR : "analisa (admin)"
    USUARIO ||--o| PERFIL_VENDEDOR : "habilitado como"
    SOLICITACAO_VENDEDOR ||--o| PERFIL_VENDEDOR : "aprovada origina"
    PERFIL_VENDEDOR ||--o| LOJA : "administra"

    CATEGORIA |o--o{ CATEGORIA : "pai de"
    CATEGORIA ||--o{ PRODUTO : "classifica"
    LOJA ||--o{ PRODUTO : "anuncia"
    PRODUTO ||--o{ VARIACAO_PRODUTO : "físico possui"
    PRODUTO ||--o{ IMAGEM_PRODUTO : "ilustrado por"
    PRODUTO ||--o{ ARQUIVO_DIGITAL : "digital entrega"

    USUARIO ||--o{ ORCAMENTO : "solicita"
    PERFIL_VENDEDOR ||--o{ ORCAMENTO : "recebe"

    USUARIO ||--o| CARRINHO : "possui"
    CARRINHO ||--o{ ITEM_CARRINHO : "contém"
    PRODUTO ||--o{ ITEM_CARRINHO : "selecionado em"
    VARIACAO_PRODUTO |o--o{ ITEM_CARRINHO : "escolhida em"

    USUARIO ||--o{ PEDIDO : "realiza"
    ENDERECO |o--o{ PEDIDO : "referenciado por"
    PEDIDO ||--o{ SUBPEDIDO : "dividido em"
    LOJA ||--o{ SUBPEDIDO : "atende"
    SUBPEDIDO ||--o{ ITEM_PEDIDO : "contém"
    PRODUTO |o--o{ ITEM_PEDIDO : "vendido como"
    VARIACAO_PRODUTO |o--o{ ITEM_PEDIDO : "vendida como"
    ORCAMENTO |o--o| ITEM_PEDIDO : "aceito gera"
    SUBPEDIDO ||--o| PAGAMENTO_SIMULADO : "registrado em"
    USUARIO |o--o{ PAGAMENTO_SIMULADO : "confirma"

    USUARIO {
        bigint id PK
        string username UK
        string first_name "nome (obrigatório)"
        string last_name
        string email UK "único sem diferenciar maiúsculas"
        string password "hash PBKDF2"
        bool is_staff
        bool is_superuser
        bool is_active
    }
    ENDERECO {
        bigint id PK
        bigint usuario_id FK
        string apelido "UK com usuario"
        string destinatario
        string telefone
        string cep
        string logradouro
        string numero
        string complemento
        string bairro
        string cidade
        string uf
    }
    SOLICITACAO_VENDEDOR {
        bigint id PK
        bigint usuario_id FK
        string tipo_pessoa "PF ou PJ"
        string documento "CPF 11 / CNPJ 14 dígitos"
        string nome_razao_social
        string telefone
        string nome_loja
        string status "pendente, aprovada, recusada"
        bigint analisado_por_id FK
        datetime analisado_em
    }
    PERFIL_VENDEDOR {
        bigint id PK
        bigint usuario_id FK,UK
        bigint solicitacao_id FK,UK
        datetime aprovado_em
    }
    LOJA {
        bigint id PK
        bigint vendedor_id FK,UK
        string nome
        text descricao
        string logotipo "mídia pública"
        bool ativa
    }
    CATEGORIA {
        bigint id PK
        string nome "UK por nível"
        string slug UK
        bigint pai_id FK "nulo = raiz"
        bool ativa
    }
    PRODUTO {
        bigint id PK
        bigint loja_id FK
        bigint categoria_id FK
        string nome
        text descricao
        string tipo "fisico ou digital"
        decimal preco_base ">= 0"
        bool ativo
    }
    VARIACAO_PRODUTO {
        bigint id PK
        bigint produto_id FK
        string material "UK produto+material+cor+dimensoes"
        string cor
        string dimensoes
        decimal ajuste_preco "pode ser negativo"
        int estoque ">= 0"
    }
    IMAGEM_PRODUTO {
        bigint id PK
        bigint produto_id FK
        string imagem "mídia pública"
        bool principal "no máximo 1 por produto"
        int ordem
    }
    ARQUIVO_DIGITAL {
        bigint id PK
        bigint produto_id FK
        string arquivo "PRIVADO: STL, 3MF, OBJ, STEP"
        string descricao
    }
    ORCAMENTO {
        bigint id PK
        bigint comprador_id FK
        bigint vendedor_id FK
        string arquivo_3d "PRIVADO"
        int quantidade ">= 1"
        string material
        string cor
        string dimensoes
        text observacoes
        decimal preco_unitario_proposto "> 0 quando respondido"
        text detalhes_proposta
        string status "pendente, respondido, aceito, recusado, cancelado"
        datetime respondido_em
        datetime finalizado_em
    }
    CARRINHO {
        bigint id PK
        bigint comprador_id FK,UK
    }
    ITEM_CARRINHO {
        bigint id PK
        bigint carrinho_id FK
        bigint produto_id FK
        bigint variacao_id FK "obrigatória p/ físico, proibida p/ digital"
        int quantidade ">= 1; digital = 1"
    }
    PEDIDO {
        bigint id PK
        bigint comprador_id FK
        bigint endereco_id FK "SET_NULL"
        string status "pendente, em_andamento, concluido, cancelado"
        string entrega_logradouro "snapshot do endereço (9 campos)"
        decimal valor_total
    }
    SUBPEDIDO {
        bigint id PK
        bigint pedido_id FK "UK com loja"
        bigint loja_id FK
        string status "independente do pedido"
        decimal subtotal
    }
    ITEM_PEDIDO {
        bigint id PK
        bigint subpedido_id FK
        bigint produto_id FK "ou orcamento, nunca ambos"
        bigint variacao_id FK
        bigint orcamento_id FK,UK "impede pedido duplicado"
        string tipo_produto
        string descricao "snapshot"
        string detalhes_variacao "snapshot"
        decimal preco_unitario "snapshot"
        int quantidade
    }
    PAGAMENTO_SIMULADO {
        bigint id PK
        bigint subpedido_id FK,UK
        decimal valor
        string status "pendente, confirmado"
        bigint confirmado_por_id FK
        datetime confirmado_em
        string observacao
    }
```

## Políticas de exclusão (`on_delete`)

| Relação | Política | Motivo |
|---|---|---|
| Pedido → comprador, SubPedido → loja, ItemPedido → produto/variação/orçamento | `PROTECT` | Histórico comercial não pode sumir em cascata. |
| Produto → loja/categoria, Categoria → pai, Loja → vendedor, Perfil → usuário/solicitação | `PROTECT` | Exclusão acidental de dados de catálogo e cadastro. |
| Pedido → endereço | `SET_NULL` | O endereço usado fica copiado no pedido (snapshot). |
| Variação/Imagem/Arquivo → produto, Itens → carrinho/subpedido, SubPedido → pedido | `CASCADE` | Partes que só existem dentro do agregado; o admin não permite excluir pedidos. |
| Endereço/Carrinho → usuário | `CASCADE` | Dados pessoais do próprio usuário (usuários com pedidos já são protegidos). |

## Restrições no banco (CHECK/UNIQUE)

- Estados válidos em `status` de solicitação, orçamento, pedido, subpedido e pagamento.
- `SolicitacaoVendedor`: documento compatível com o tipo (11/14 dígitos); análise registra quem/quando; no máximo uma solicitação pendente/aprovada por usuário e por CPF/CNPJ.
- `Categoria`: não é pai de si mesma; nome único por nível (inclusive raízes). Ciclos indiretos são barrados em `clean()`.
- `Produto`: preço base ≥ 0. `VariacaoProduto`: estoque ≥ 0 e combinação material/cor/dimensão única (sem diferenciar maiúsculas). Preço final ≥ 0 validado em `clean()`.
- `ImagemProduto`: no máximo uma imagem principal por produto (índice único parcial).
- `ItemCarrinho`: quantidade ≥ 1; sem itens repetidos (produto/variação).
- `ItemPedido`: origem é produto **ou** orçamento; variação só com produto; digital com quantidade 1 e sem variação.
- `Orcamento`: pendente sem proposta; respondido/aceito/recusado com proposta; preço > 0.
- `SubPedido`: um por loja em cada pedido. `PagamentoSimulado`: confirmado ⇔ quem e quando.
