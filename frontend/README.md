# Inventory Count Hub

Crie o frontend inicial de um sistema web chamado:

SGI — Sistema de Gestão de Inventário

IMPORTANTE:

Este é um MVP de um sistema corporativo de inventário logístico.

Neste primeiro momento, quero desenvolver e validar apenas o fluxo operacional de contagem.

NÃO criar funcionalidades que não foram solicitadas.

NÃO adicionar login neste momento.

NÃO utilizar Supabase.

NÃO criar banco de dados próprio no frontend.

NÃO implementar regras complexas de inventário ainda.

NÃO integrar diretamente com SQL Server pelo navegador.

O frontend será posteriormente conectado a uma API/backend desenvolvido pela empresa, provavelmente em Python/FastAPI, que será responsável pela comunicação com SQL Server e API do WMS.

==================================================

1. OBJETIVO DO SISTEMA

==================================================

O SGI substituirá gradualmente um aplicativo de inventário atualmente desenvolvido em AppSheet.

O sistema será utilizado principalmente em:

- coletores de dados;

- celulares;

- tablets;

- computadores.

Por isso, a interface deve ser:

- mobile first;

- extremamente simples;

- rápida;

- responsiva;

- adequada para operação logística;

- adequada para leitura por scanner de código de barras;

- com botões grandes;

- campos grandes;

- pouco texto;

- sem elementos visuais desnecessários.

Quero uma aparência semelhante a um aplicativo operacional como AppSheet, mas com visual mais moderno e profissional.

==================================================

2. ARQUITETURA FUTURA

==================================================

A arquitetura prevista será:

Coletor / Navegador

        ↓

Frontend SGI

        ↓

API Backend (Python/FastAPI)

        ↓

SQL Server interno da empresa

E também:

API Backend

        ↓

API WMS interna

O frontend NÃO deve acessar SQL Server diretamente.

Prepare o código do frontend de forma que futuramente seja fácil substituir os dados simulados por chamadas HTTP para endpoints REST do backend.

Centralize essas chamadas em uma camada de serviço/API separada.

==================================================

3. MVP ATUAL

==================================================

Neste momento implementar somente:

CONTAGEM DE INVENTÁRIO

Fluxo operacional:

1. Operador inicia uma localização.

2. Bipa/digita a localização.

3. Confirma a localização.

4. A localização fica ativa.

5. Operador bipa/digita o código do produto.

6. Informa o lote.

7. Informa a quantidade.

8. Pressiona Salvar.

9. O item aparece imediatamente na lista de itens contados naquela localização.

10. Os campos Código, Lote e Quantidade são limpos.

11. A localização permanece ativa.

12. O cursor retorna automaticamente para Código.

13. O operador continua contando outros itens.

14. Ao terminar, pressiona "Encerrar Localização".

15. O sistema pede uma confirmação.

16. Depois de confirmar, limpa a localização atual.

17. O sistema volta para a tela de leitura da próxima localização.

==================================================

4. TELA INICIAL

==================================================

Criar uma tela inicial simples com:

SGI

Sistema de Gestão de Inventário

Um card/botão grande:

"Realizar Contagem"

Neste MVP somente esse módulo precisa funcionar.

Pode mostrar outros módulos futuros de forma discreta/desabilitada, mas não implementar funcionalidades.

Exemplos futuros:

- Inventários

- Análise

- Recontagem

- Histórico

Priorizar "Realizar Contagem".

==================================================

5. TELA DE LOCALIZAÇÃO

==================================================

Ao entrar em Realizar Contagem mostrar:

"Informe a localização"

Campo:

Localização

[________________]

Botão grande:

[ INICIAR LOCALIZAÇÃO ]

O campo deve receber foco automaticamente.

Precisa funcionar tanto digitando quanto usando scanner físico de código de barras.

Pressionar Enter também deve iniciar a localização.

Não permitir iniciar com localização vazia.

==================================================

6. TELA DE CONTAGEM

==================================================

Depois de iniciar uma localização, mostrar claramente no topo:

LOCALIZAÇÃO ATIVA

A01

A localização precisa ficar visualmente destacada para evitar que o operador conte produtos no endereço errado.

Abaixo:

Código

[________________]

Lote

[________________]

Quantidade

[________]

[ SALVAR ITEM ]

Comportamento:

- Código obrigatório.

- Lote permitido.

- Quantidade obrigatória.

- Quantidade deve ser numérica e maior que zero.

- Enter deve facilitar a navegação entre os campos.

- Depois de salvar, limpar Código, Lote e Quantidade.

- NÃO limpar a localização.

- Retornar foco automaticamente ao campo Código.

==================================================

7. MÚLTIPLAS LEITURAS

==================================================

Não bloquear leitura duplicada de Código + Lote dentro da mesma localização.

Isso é intencional.

Exemplo:

Localização A01

Código 100

Lote X

Quantidade 5

Depois:

Código 100

Lote X

Quantidade 3

As duas leituras são válidas porque podem representar dois volumes físicos diferentes.

Neste MVP, mantenha os dois registros individuais na lista.

A consolidação será responsabilidade futura do backend.

==================================================

8. ITENS CONTADOS

==================================================

Abaixo do formulário mostrar:

"Itens contados nesta localização"

Exemplo:

Código 100

Lote X

Qtd. 5

Código 200

Lote Y

Qtd. 10

Código 100

Lote X

Qtd. 3

Mostrar também:

Itens registrados: 3

Quantidade total: 18

Os registros podem ficar armazenados temporariamente no estado da aplicação neste MVP.

Preparar a estrutura para futuramente os registros virem do backend.

==================================================

9. FECHAR LOCALIZAÇÃO

==================================================

Na parte inferior da tela criar um botão destacado:

[ ENCERRAR LOCALIZAÇÃO ]

Ao clicar mostrar confirmação:

"Tem certeza que deseja encerrar a localização A01?"

Botões:

[CANCELAR]

[ENCERRAR]

Depois de confirmar:

- encerrar a localização;

- limpar os itens exibidos;

- retornar à tela de leitura da localização;

- colocar foco automaticamente no campo Localização.

==================================================

10. REGRAS IMPORTANTES DO INVENTÁRIO

==================================================

O sistema terá futuramente dois tipos:

ROTATIVO

OFICIAL

Neste MVP NÃO implementar essas regras, mas organizar o código para permitir essa expansão.

No Inventário Oficial existem rodadas:

Rodada 1

Rodada 2

Rodada 3

Rodada 4

etc.

Regra importante:

Uma localização NÃO pode ser contada novamente pela mesma equipe em outra rodada do Inventário Oficial.

Porém, dentro da MESMA rodada e localização, podem existir várias leituras do mesmo Código + Lote.

Exemplo válido:

Rodada 1

A01

Código 100

Lote X

Qtd 5

Rodada 1

A01

Código 100

Lote X

Qtd 3

Resultado consolidado futuro:

8 unidades.

Também pode existir o mesmo Código + Lote distribuído em várias localizações:

Rodada 1

A01 = 5

A02 = 10

A03 = 8

Resultado da Rodada 1 = 23.

A localização NÃO fará parte da chave de comparação final do Inventário Oficial.

A comparação oficial será baseada principalmente em:

SKU + Lote + Rodada

==================================================

11. RECONTAGEM FUTURA

==================================================

Não implementar agora.

Apenas considerar na arquitetura futura.

Quando houver divergência:

Qtd WMS

versus

Qtd Contada

o sistema poderá gerar uma recontagem.

Exemplo:

WMS = 25

1ª Contagem = 23

Resultado = DIVERGENTE

2ª Contagem = 25

Resultado = OK

O sistema futuramente poderá ter:

- 1ª Contagem

- 2ª Contagem

- 3ª Contagem

- 4ª Contagem

- Operador 1ª Contagem

- Operador 2ª Contagem

- Operador 3ª Contagem

- Operador 4ª Contagem

- Localizações bipadas por rodada

- Diferença

- Resultado

- Status da recontagem

Não implementar isso neste MVP.

==================================================

12. BANCO FUTURO

==================================================

Já existe SQL Server interno da empresa.

Banco:

Inventario

Existe uma tabela inicial de testes:

dbo.ContagensTeste

O backend será responsável por gravar no SQL Server.

O frontend deve estar preparado para futuramente enviar algo semelhante a:

{

    "localizacao": "A01",

    "codigo": "7899990392973",

    "lote": "LOTE01",

    "quantidade": 5

}

NÃO conectar diretamente ao SQL Server neste momento.

==================================================

13. API WMS FUTURA

==================================================

Existe uma API WMS interna da empresa.

Ela futuramente poderá ser utilizada pelo backend para consultar estoque.

Não implementar a integração no frontend.

O frontend deverá conversar somente com nosso backend SGI.

Fluxo correto:

Frontend SGI

      ↓

Backend SGI

      ↓

API WMS

e/ou:

Frontend SGI

      ↓

Backend SGI

      ↓

SQL Server

==================================================

14. TECNOLOGIA E ORGANIZAÇÃO

==================================================

Criar código organizado e preparado para manutenção.

Separar:

- páginas;

- componentes;

- serviços;

- tipos/interfaces;

- regras de interface.

Criar uma camada de serviço para comunicação futura com API.

Por enquanto essa camada pode usar dados simulados.

Evitar colocar regras de negócio importantes diretamente nos componentes visuais.

O objetivo é futuramente conectar esse frontend a FastAPI sem precisar reconstruir as telas.

==================================================

15. DESIGN

==================================================

Quero um sistema corporativo de logística.

Visual:

- limpo;

- moderno;

- profissional;

- simples;

- operacional;

- mobile first.

Evitar aparência de site comercial.

Evitar:

- banners;

- gráficos;

- animações desnecessárias;

- excesso de cards;

- gradientes exagerados;

- textos longos.

O operador precisa conseguir utilizar o sistema rapidamente em um coletor.

Priorizar contraste, legibilidade e tamanho dos elementos.

==================================================

16. EXPERIÊNCIA COM SCANNER

==================================================

Isso é muito importante.

O sistema será usado com leitores de código de barras.

Portanto:

- foco automático nos campos;

- suporte a Enter;

- evitar necessidade de tocar na tela repetidamente;

- depois de salvar retornar automaticamente para Código;

- permitir operação rápida em sequência.

Fluxo ideal:

Bipa Localização

↓

Enter

↓

Bipa Código

↓

Lote

↓

Quantidade

↓

Salvar

↓

Código novamente

==================================================

17. PRIMEIRA ENTREGA

==================================================

Para esta primeira versão quero SOMENTE:

1. Tela inicial.

2. Iniciar localização.

3. Localização ativa.

4. Informar Código.

5. Informar Lote.

6. Informar Quantidade.

7. Salvar item.

8. Mostrar itens registrados.

9. Permitir múltiplas leituras do mesmo Código + Lote.

10. Manter localização ativa após salvar.

11. Encerrar localização.

12. Interface responsiva para coletor/celular.

13. Dados simulados/local state.

14. Estrutura preparada para integração futura com FastAPI.

NÃO implementar ainda:

- login;

- usuários;

- permissões;

- SQL Server;

- Supabase;

- API WMS;

- inventário rotativo;

- inventário oficial;

- rodadas;

- análise de divergência;

- recontagem;

- dashboards;

- relatórios.

Primeiro quero validar visualmente e operacionalmente o fluxo básico de contagem.

This project was built with [Lovable](https://lovable.dev).

**Live app**: https://quick-count-ops.lovable.app

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/3e5b180e-4aaa-44c4-ba74-2d5f1194df34).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
