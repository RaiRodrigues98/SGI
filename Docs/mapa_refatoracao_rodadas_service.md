# Mapa de Refatoração — `rodadas_service.py`

Arquivo analisado: `rodadas_service(20260828-175523).py`  
Total: **3172 linhas**  
Funções de módulo: **23**

## Alerta de baseline

A versão enviada **não contém** o `sp_getapplock` aplicado no Estágio 14 para serializar a criação concorrente da R2 ROTATIVO.

Antes de qualquer refatoração, é necessário garantir que o `services/rodadas_service.py` local corresponde à versão que passou a regressão final.

## Distribuição principal

- `criar_proxima_rodada`: **821 linhas** (25.9%)
- `visualizar_proxima_rodada`: **630 linhas** (19.9%)
- As duas funções juntas: **1451 linhas** (45.7%)

Essas duas funções devem ficar para o fim da refatoração.

## Mapeamento das funções

| Função | Linhas | Tamanho | Responsabilidade | Destino sugerido | Tabelas SQL diretas |
|---|---:|---:|---|---|---|
| `_normalizar_texto` | 33-38 | 6 | Compartilhada | `shared/normalizacao.py` | - |
| `_normalizar_lote` | 41-43 | 3 | Compartilhada | `shared/normalizacao.py` | - |
| `_normalizar_localizacao` | 46-51 | 6 | Compartilhada | `shared/normalizacao.py` | - |
| `_finalizar_rodada_atual` | 66-152 | 87 | Lifecycle | `rodadas/lifecycle.py` | RodadasInventario |
| `_buscar_itens_nova_recontagem_gestor` | 163-232 | 70 | Gestor | `rodadas/gestor.py` | DecisoesGestorInventario |
| `_existem_decisoes_gestor_ativas` | 239-259 | 21 | Gestor | `rodadas/gestor.py` | DecisoesGestorInventario |
| `_buscar_localizacoes_snapshot_item` | 266-330 | 65 | Localização | `rodadas/localizacoes.py` | InventarioEstoqueSnapshot |
| `_buscar_localizacoes_contagem_item` | 337-406 | 70 | Localização | `rodadas/localizacoes.py` | Contagens, SessoesContagem |
| `_buscar_localizacoes_para_item` | 413-450 | 38 | Localização | `rodadas/localizacoes.py` | - |
| `_inserir_rodada_item` | 457-533 | 77 | Persistência/Itens | `rodadas/itens.py` | RodadaItens |
| `_inserir_rodada_localizacao` | 540-601 | 62 | Localização | `rodadas/localizacoes.py` | RodadaLocalizacoes |
| `sincronizar_localizacoes_recontagem` | 608-746 | 139 | Localização | `rodadas/localizacoes.py` | RodadaItens, RodadasInventario |
| `_validar_divergencias_r1_rotativo_tratadas` | 755-860 | 106 | ROTATIVO | `rodadas/candidatos_rotativo.py` | Contagens, DecisoesRotativo, InventarioEstoqueSnapshot, SessoesContagem |
| `_buscar_colunas_tabela` | 875-898 | 24 | Infra/Schema | `rodadas/schema_utils.py` | - |
| `_resolver_coluna_quantidade_rotativo` | 901-930 | 30 | Infra/Schema | `rodadas/schema_utils.py` | - |
| `_buscar_candidatos_r2_rotativo` | 933-1038 | 106 | ROTATIVO | `rodadas/candidatos_rotativo.py` | DecisoesRotativo |
| `_buscar_candidatos_r3` | 1046-1111 | 66 | OFICIAL | `rodadas/candidatos_oficial.py` | - |
| `_buscar_candidatos_recontagem_anterior` | 1118-1198 | 81 | OFICIAL | `rodadas/candidatos_oficial.py` | - |
| `_buscar_candidatos_gestor` | 1207-1242 | 36 | Gestor | `rodadas/gestor.py` | - |
| `_encerrar_inventario_rotativo_apos_r1_sem_recontagem` | 1268-1521 | 254 | ROTATIVO | `rodadas/finalizacao_rotativo.py` | DecisoesRotativo, Inventarios, OcorrenciasDivergencia, SessoesContagem |
| `_encerrar_inventario_rotativo_apos_r2` | 1533-1715 | 183 | ROTATIVO | `rodadas/finalizacao_rotativo.py` | Inventarios, RodadasInventario |
| `criar_proxima_rodada` | 1720-2540 | 821 | Orquestração | `rodadas/service.py` | Inventarios, RodadasInventario, SessoesContagem |
| `visualizar_proxima_rodada` | 2543-3172 | 630 | Orquestração/Preview | `rodadas/preview.py` | RodadasInventario, SessoesContagem |

## Ordem recomendada

### Fase 0 — Garantir o baseline
1. Confirmar que o arquivo em uso contém a correção de concorrência do Estágio 14.
2. Executar `teste_rotativo_estagio14.py`.
3. Executar `regressao_final_sgi.py`.
4. Só então iniciar a separação estrutural.

### Fase 1 — Extração de baixo risco
Criar:
- `services/rodadas/__init__.py`
- `services/rodadas/itens.py`
- `services/rodadas/localizacoes.py`

Mover somente:
- `_inserir_rodada_item`
- `_buscar_localizacoes_snapshot_item`
- `_buscar_localizacoes_contagem_item`
- `_buscar_localizacoes_para_item`
- `_inserir_rodada_localizacao`
- `sincronizar_localizacoes_recontagem`

Manter imports/reexports de compatibilidade no `rodadas_service.py`.

Depois executar regressão final.

### Fase 2 — Regras ROTATIVO / OFICIAL
Criar:
- `candidatos_rotativo.py`
- `candidatos_oficial.py`

Mover:
- validação e candidatos R2 ROTATIVO
- candidatos R3 e recontagem OFICIAL

Depois executar regressão final.

### Fase 3 — Gestor
Criar `gestor.py` e mover as três funções relacionadas a decisões gerenciais.

Depois executar regressão final.

### Fase 4 — Finalização ROTATIVO
Criar `finalizacao_rotativo.py` e mover:
- encerramento pela R1 sem recontagem
- encerramento após R2

Depois executar regressão final.

### Fase 5 — Lifecycle
Mover `_finalizar_rodada_atual` para `lifecycle.py`.

Depois executar regressão final.

### Fase 6 — Orquestração
Por último:
- reduzir `criar_proxima_rodada`
- separar `visualizar_proxima_rodada` para `preview.py`
- preservar o contrato público atual do router

Depois executar regressão final.

## Regra da refatoração

**Nesta primeira passagem, mudar apenas estrutura, nunca comportamento.**

Não alterar simultaneamente:
- contrato HTTP;
- regras ROTATIVO;
- regras OFICIAL;
- schema do banco;
- transações;
- nomes de campos;
- regras de autorização.

Cada fase deve terminar com:

```powershell
python tests_e2e\regressao_final_sgi.py
```

e exigir:

```text
RESULTADO FINAL: APROVADO PARA HOMOLOGAÇÃO CONTROLADA
```
