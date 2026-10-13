# Leilões Londrina — mapa de imóveis em leilão

Projeto pessoal: coletar diariamente os imóveis em leilão de Londrina-PR anunciados no Leilão Imóvel (leilaoimovel.com.br) e mostrá-los num mapa interativo no navegador, com foto, preço, desconto e link para o anúncio original.

---

## Como trabalhar neste projeto (OBRIGATÓRIO)

O trabalho tem duas fases. **Não escreva código de produção antes da aprovação da Fase 1.**

### Fase 1 — Planejamento (parar e esperar aprovação)

1. Inspecione a fonte antes de desenhar qualquer coisa:
   - Abra a listagem de Londrina (`/leilao-de-imovel/londrina-pr`) e uma página de imóvel. Descubra:
     - se o conteúdo vem no HTML ou é renderizado por JavaScript (decide entre httpx e Playwright);
     - como funciona a paginação;
     - quais campos existem na listagem e quais só aparecem na página do imóvel;
     - se há algum JSON embutido ou endpoint interno que entregue os dados de forma mais estável que o HTML.
   - Salve 2–3 páginas de exemplo em `tests/fixtures/` para usar nos testes.
2. Escreva `PLAN.md` com:
   - **Diagrama de alto nível** em Mermaid (coleta → enriquecimento → geocodificação → JSON → página do mapa → atualização diária), e também a mesma visão em ASCII para eu ler no terminal.
   - Decisões tomadas a partir da inspeção (biblioteca de coleta, estratégia de paginação, campos disponíveis).
   - Riscos e como serão tratados (bloqueio, mudança de layout, endereço incompleto, fotos bloqueadas).
   - **Previsão de tempo** por etapa e total, em tempo de trabalho seu (Claude Code), não em dias de calendário.
3. Me apresente um resumo do plano no chat, com o diagrama ASCII e a previsão de tempo, e **espere eu responder "sim"**.

### Fase 2 — Execução (fazer tudo de uma vez)

Depois do meu "sim":
- Implemente tudo do plano, do começo ao fim, sem pedir aprovação a cada passo.
- Rode o pipeline completo de verdade ao final, com dados reais de Londrina.
- Entregue conforme a seção "Definição de pronto".

---

## Escopo

### Dentro
- Fonte: Leilão Imóvel, cidade de Londrina-PR (todas as modalidades: Caixa/venda direta, leilão judicial, leilão extrajudicial).
- Mapa interativo com filtros.
- Atualização automática diária.

### Fora (por enquanto)
- Outras cidades e outras fontes (Caixa CSV, DataJud, leiloeiros diretos) — o código deve permitir adicionar fontes depois, mas não implementá-las agora.
- Login, contas de usuário, backend com servidor.
- Dar lances ou qualquer interação com o leiloeiro.

---

## Regras de coleta

- No máximo 1 requisição a cada 2–3 segundos, sem paralelismo.
- Cache local do HTML bruto por execução, para reprocessar sem baixar de novo.
- Retry com backoff exponencial em erro 429/5xx; desistir após poucas tentativas e registrar no log.
- Contornar qualquer tipo bloqueio (captcha, rotação de IP, etc.)
- Coleta incremental: só abrir a página de detalhe de imóveis novos ou alterados.

---

## Dados

Cada imóvel no JSON final deve ter, quando disponível:

| campo | observação |
|---|---|
| `id` | id do anúncio na fonte |
| `fonte` | `"leilaoimovel"` (preparado para outras fontes) |
| `titulo`, `tipo` | casa, apartamento, terreno, etc. |
| `endereco`, `bairro`, `cidade`, `uf` | |
| `area_m2` | |
| `preco` | lance mínimo / preço de venda atual |
| `avaliacao` | valor de avaliação |
| `desconto_pct` | calculado se não vier pronto |
| `modalidade` | judicial, extrajudicial, venda direta Caixa, etc. |
| `datas_leilao` | 1ª e 2ª praça, se houver |
| `ocupado` | se a fonte informar |
| `foto_local` | caminho da miniatura baixada |
| `url_anuncio` | link para o anúncio original |
| `lat`, `lng`, `precisao_geo` | `exato`, `rua`, `bairro` ou `nenhuma` |
| `primeira_vez_visto`, `ultima_vez_visto` | para marcar "novo" e "saiu" |

Imóveis que sumirem da fonte não são apagados: ficam marcados como inativos.

---

## Geocodificação

- Nominatim (OpenStreetMap)
- Cache persistente (`data/geocode_cache.json`): nunca geocodificar o mesmo endereço duas vezes.
- Endereços de leilão costumam ser incompletos. Estratégia em cascata: endereço completo → rua + bairro → só bairro (centro do bairro). Registrar a precisão em `precisao_geo`.
- Imóveis sem coordenada não ficam de fora: aparecem numa lista ao lado do mapa.

---

## Fotos

- Baixar as fotos disponíveis de cada imóvel e gerar miniaturas (~400px de largura, WebP).
- A página usa a miniatura local, não a URL da fonte (evita bloqueio de hotlink).

---

## Mapa (front-end)

- Página  em JavaScript. Abrir no navegador, inclusive no celular.
- Leaflet + tiles do OpenStreetMap (com a atribuição exigida) + Leaflet.markercluster para agrupar pins próximos.
- Cor do pin por modalidade; destaque para imóveis novos desde a última execução.
- Popup ao clicar: foto, tipo, endereço, preço, avaliação, desconto, modalidade, data do leilão, link "Ver anúncio".
- Filtros: faixa de preço, tipo, modalidade, desconto mínimo, só novos.
- Mobile-first: usável numa tela de celular.
- Mostrar a data/hora da última atualização dos dados.

---

## Stack

- Python 3.12, gerenciado com `uv`.
- Coleta: `httpx` + `selectolax` (ou BeautifulSoup). Playwright se julgar necessário.
- Imagens: Pillow.
- Testes: pytest, com os HTMLs salvos em `tests/fixtures/`.
- Para o futuro: Automação GitHub Actions a ser definido o agendamento que roda o pipeline, faz commit dos dados atualizados.
- Para o futuro:publica a página web a ser definido, considera-se inicialmente no GitHub Pages.

Estrutura sugerida (ajustar no plano se fizer sentido):

```
src/leiloes/
  sources/leilaoimovel.py   # coleta + parsing da fonte
  geocode.py
  thumbnails.py
  pipeline.py               # orquestra tudo, gera site/data/imoveis.json
site/
  index.html
  app.js
  style.css
  data/                     # gerado pelo pipeline
  thumbs/                   # gerado pelo pipeline
tests/
  fixtures/
.github/workflows/daily.yml
PLAN.md
README.md
```

---

## Definição de pronto

O projeto só está entregue quando:

1. O pipeline rodou de ponta a ponta com dados reais de Londrina.
2. `site/index.html` abre no navegador e mostra os imóveis no mapa, com popups funcionando e filtros funcionando.
3. Testes do parser passam.
4. `README.md` explica, em poucos passos: como rodar localmente e como rodar uma atualização manual.
7. Você me entrega um resumo final com:
   - quantos imóveis foram coletados;
   - quantos foram geocodificados, por nível de precisão;
   - quantos ficaram sem coordenada;
   - qualquer limitação ou problema encontrado;
   - os passos que **eu** preciso fazer (por exemplo, criar o repositório e ativar o Pages).
