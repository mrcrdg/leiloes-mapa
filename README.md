# Leilões Londrina

Mapa dos imóveis em leilão de Londrina-PR anunciados no [Leilão Imóvel](https://www.leilaoimovel.com.br).
Para ver o mapa, rode um servidor local e abra o endereço no navegador:

```bash
uv run python -m http.server 8000 -d site     # depois abra http://localhost:8000
```

Abrir `site/index.html` direto como arquivo (`file://`) pode dar "403 Access blocked" nos mapas: o
OpenStreetMap exige que a página diga de onde vem (Referer), e arquivos locais não dizem. Pelo servidor local
(ou no GitHub Pages) funciona.

## Importante: a coleta é manual

O site está protegido por uma verificação anti-robô (Cloudflare) e responde 403 a programas. O projeto
**não acessa o site**: você salva as páginas pelo navegador e o pipeline processa os arquivos.

## Rodar localmente (a partir das páginas já salvas)

```bash
uv sync
uv run python -m leiloes.pipeline      # lê tests/fixtures/manual/, gera site/data/ e site/thumbs/
uv run pytest                          # testes do parser
```

Depois abra `site/index.html`. Use `--sem-geocodificar` para pular o Nominatim.

## Atualização manual (quando quiser dados novos)

1. Abra a listagem de Londrina no navegador e salve cada página (`Ctrl+S`, "somente HTML") em
   `tests/fixtures/manual/` como `listagem-p1.html`, `listagem-p2.html`, ... Antes, apague as listagens antigas.
2. `uv run python scripts/gerar_tarefas.py` cria `tests/fixtures/manual/tarefas.html`, com um link por imóvel.
   Clique em cada um e salve a página (pode manter o nome que o navegador sugerir).
3. `uv run python scripts/conferir.py --renomear` renomeia para `imovel-ID.html` e diz o que falta ou veio
   com a tela de verificação.
4. `uv run python -m leiloes.pipeline` e recarregue o mapa.

Imóveis que sumirem da listagem ficam no JSON como `ativo: false`; os novos aparecem com destaque no mapa.
Imóveis sem página de detalhe salva aparecem só com os dados da listagem (`detalhe: false`).

## Notas

- Desconto = sobre a avaliação. Sem avaliação, fica vazio: o % que o site mostra nesses casos é a queda da
  1ª para a 2ª praça, outra coisa.
- Geocodificação: Nominatim (1 consulta/s), cache em `data/geocode_cache.json`. `precisao_geo` é `exato`,
  `rua` (o Nominatim quase nunca tem número de porta em Londrina), `bairro` ou `nenhuma`.
- Atualização diária automática (GitHub Actions) **não foi feita**: depende de o site liberar acesso programático.
