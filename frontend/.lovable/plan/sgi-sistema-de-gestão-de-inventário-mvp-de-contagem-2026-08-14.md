# SGI — Sistema de Gestão de Inventário (MVP de Contagem)

Frontend operacional, mobile-first, com dados apenas em memória e uma camada de serviço pronta para trocar por chamadas ao backend FastAPI.

## Telas

**1. Início (`/`)**
- Título "SGI" + subtítulo "Sistema de Gestão de Inventário".
- Card grande e destacado: "Realizar Contagem".
- Abaixo, itens futuros desabilitados (Inventários, Análise, Recontagem, Histórico) — apenas visuais, sem navegação.

**2. Contagem (`/contagem`)** — uma rota, dois estados

*Sem localização ativa:*
- Texto "Informe a localização", campo grande com foco automático, botão `INICIAR LOCALIZAÇÃO`.
- Enter inicia; campo vazio bloqueia o início.

*Com localização ativa:*
- Faixa fixa no topo em alto contraste: "LOCALIZAÇÃO ATIVA" + código (ex. A01).
- Formulário: Código, Lote, Quantidade (numérico, teclado numérico no mobile) e botão `SALVAR ITEM`.
- Validação: Código obrigatório, Quantidade numérica > 0, Lote opcional.
- Enter avança entre campos; Enter na Quantidade salva.
- Após salvar: limpa os três campos, mantém a localização, devolve o foco ao Código.
- Lista "Itens contados nesta localização" (mais recente primeiro), com Código / Lote / Qtd. Leituras duplicadas de Código+Lote ficam como linhas separadas.
- Resumo: "Itens registrados: N" e "Quantidade total: X".
- Botão destacado no rodapé: `ENCERRAR LOCALIZAÇÃO` → diálogo "Tem certeza que deseja encerrar a localização A01?" com [CANCELAR] / [ENCERRAR]. Ao confirmar: limpa itens e localização, volta ao passo de leitura da localização com foco no campo.

## Design

Visual corporativo de logística: fundo neutro claro, azul industrial como cor primária, âmbar/laranja para a faixa de localização ativa, tipografia condensada e legível, campos e botões com altura mínima ~56px, alvos de toque grandes, sem banners, gráficos ou animações. Tokens semânticos definidos em `src/styles.css` (nada de cores fixas nos componentes).

## Estrutura técnica

```text
src/
  types/inventory.ts          ContagemItem, NovaContagem, Localizacao,
                              TipoInventario ('ROTATIVO'|'OFICIAL'), Rodada (reservados)
  services/apiClient.ts       wrapper fetch + BASE_URL (import.meta.env.VITE_API_URL)
  services/contagemService.ts registrarItem / listarItens / iniciarLocalizacao /
                              encerrarLocalizacao — hoje mock em memória, assinaturas async
  hooks/useContagem.ts        estado do fluxo (localização ativa, itens, totais, ações)
  components/contagem/        LocalizacaoBanner, LocalizacaoForm, ItemForm,
                              ItensContadosList, EncerrarDialog
  routes/index.tsx            tela inicial (substitui o placeholder)
  routes/contagem.tsx         fluxo de contagem
```

- Payload do serviço já no formato final: `{ localizacao, codigo, lote, quantidade }`.
- Validação com zod na camada de serviço/hook, não dentro do JSX.
- Componentes visuais não contêm regra de negócio; trocar o mock por HTTP ficará restrito a `services/`.
- `head()` próprio em cada rota (título/descrição do SGI).

## Fora do escopo

Login, usuários, permissões, Supabase, SQL Server, WMS, rodadas, inventário rotativo/oficial, recontagem, divergência, dashboards e relatórios. Apenas tipos reservados para expansão futura.
