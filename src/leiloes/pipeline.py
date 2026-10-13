"""Orquestra: lê as páginas salvas à mão → parser → geocodifica → miniaturas → site/data/imoveis.json.

Uso: uv run python -m leiloes.pipeline [--sem-geocodificar]
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from collections import Counter
from datetime import datetime
from pathlib import Path

from leiloes.geocode import Geocodificador
from leiloes.sources.leilaoimovel import calcular_desconto, carregar, parse_detalhe, parse_listagem
from leiloes.thumbnails import BaixadorDeFotos, gerar_miniatura

ENTRADA = Path("tests/fixtures/manual")
SAIDA = Path("site/data/imoveis.json")
THUMBS = Path("site/thumbs")
CAMPOS_PUBLICOS = (
    "id", "fonte", "titulo", "tipo", "endereco", "bairro", "cidade", "uf", "area_m2", "preco", "avaliacao",
    "desconto_pct", "modalidade", "datas_leilao", "ocupado", "foto_local", "url_anuncio", "lat", "lng",
    "precisao_geo", "primeira_vez_visto", "ultima_vez_visto", "ativo", "novo", "detalhe", "quartos", "vagas",
)


def _foto_local(entrada: Path, listagem_html: str, src: str | None) -> Path | None:
    if not src:
        return None
    return entrada / urllib.parse.unquote(src.removeprefix("./"))


def montar(entrada: Path, geo: Geocodificador | None, agora: str, antigos: dict[str, dict],
           fotos: BaixadorDeFotos | None = None) -> list[dict]:
    brutos: dict[str, dict] = {}
    for pag in sorted(entrada.glob("listagem-p*.html")):
        html = carregar(pag)
        for it in parse_listagem(html):
            it["_pagina"] = pag
            brutos.setdefault(it["id"], it)

    imoveis = []
    for iid, it in brutos.items():
        det_arq = entrada / f"imovel-{iid}.html"
        det = parse_detalhe(carregar(det_arq)) if det_arq.exists() else {}
        foto = None
        if det.get("foto_detalhe"):  # "-g.webp" é maior; o navegador salva em imovel-ID_files/
            nome = det["foto_detalhe"].rsplit("/", 1)[-1]
            cand = entrada / f"imovel-{iid}_files" / nome
            foto = cand if cand.is_file() else None
        src = it.get("foto_listagem")
        if foto is None and src and src.startswith("https://") and fotos is not None:
            foto = fotos.obter(iid, src)  # listagem salva sem a pasta _files: a foto é só um link
        foto = foto or (_foto_local(entrada, "", src) if src and not src.startswith("http") else None)
        thumb_rel = f"thumbs/{iid}.webp"
        tem_foto = gerar_miniatura(foto, THUMBS.parent / thumb_rel) if foto else False

        avaliacao = it["avaliacao"] if it["avaliacao"] is not None else det.get("avaliacao_detalhe")
        datas = det.get("praças_detalhe") or it["praças"]
        endereco = it["endereco"]
        bairro = it["bairro"] or det.get("bairro_detalhe")
        if not endereco and det.get("rua_detalhe"):
            endereco = det["rua_detalhe"]
        reg = {
            "id": iid, "fonte": it["fonte"], "titulo": it["titulo"],
            "tipo": it["tipo"] or det.get("tipo_detalhe"),
            "endereco": endereco, "bairro": bairro, "cidade": it["cidade"], "uf": "PR",
            "area_m2": det.get("area_m2"), "quartos": det.get("quartos"), "vagas": det.get("vagas"),
            "preco": it["preco"], "avaliacao": avaliacao,
            "desconto_pct": calcular_desconto(it["preco"], avaliacao, it["desconto_site_pct"]), "modalidade": it["modalidade"] or det.get("modalidade_detalhe"),
            "datas_leilao": datas, "ocupado": det.get("ocupado"),
            "foto_local": thumb_rel if tem_foto else None,
            # plano B: sem cópia local, o navegador tenta carregar a foto pelo endereço da fonte
            "foto_url": src if (not tem_foto and src and src.startswith("https://image.leilaoimovel.com.br/")) else None,
            "url_anuncio": it["url_anuncio"],
            "detalhe": bool(det),
        }
        if geo is not None:
            reg.update(geo.geocodificar(endereco, bairro, it["cidade"]))
        else:
            reg.update({"lat": None, "lng": None, "precisao_geo": "nenhuma"})
        ant = antigos.get(iid, {})
        reg["primeira_vez_visto"] = ant.get("primeira_vez_visto", agora)
        reg["ultima_vez_visto"] = agora
        reg["ativo"] = True
        reg["novo"] = bool(antigos) and iid not in antigos  # novo desde a execução anterior
        imoveis.append(reg)

    # o que sumiu da fonte fica marcado como inativo, nunca apagado
    for iid, ant in antigos.items():
        if iid not in brutos:
            imoveis.append({**ant, "ativo": False})
    return imoveis


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-geocodificar", action="store_true")
    ap.add_argument("--baixar-fotos", action="store_true",
                    help="tenta baixar fotos que são só link (o CDN do site respondeu 403 na única tentativa)")
    ap.add_argument("--entrada", type=Path, default=ENTRADA)
    args = ap.parse_args()

    agora = datetime.now().isoformat(timespec="minutes")
    antigos = {}
    if SAIDA.exists():
        antigos = {i["id"]: i for i in json.loads(SAIDA.read_text(encoding="utf-8"))["imoveis"]}
    geo = None if args.sem_geocodificar else Geocodificador()
    fotos = BaixadorDeFotos(Path("data/fotos")) if args.baixar_fotos else None
    imoveis = montar(args.entrada, geo, agora, antigos, fotos)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    corpo = json.dumps({"atualizado_em": agora, "imoveis": imoveis}, ensure_ascii=False, indent=1)
    SAIDA.write_text(corpo, encoding="utf-8")
    # o navegador não deixa fetch() ler arquivo local; um <script> lê, então o index.html abre com duplo clique
    SAIDA.with_suffix(".js").write_text(f"window.DADOS = {corpo};\n", encoding="utf-8")

    ativos = [i for i in imoveis if i["ativo"]]
    print(f"{len(ativos)} imóveis ativos ({len(imoveis) - len(ativos)} inativos) → {SAIDA}")
    print("com detalhe:", sum(i["detalhe"] for i in ativos), "| com foto:", sum(bool(i["foto_local"]) for i in ativos))
    print("precisão geo:", dict(Counter(i["precisao_geo"] for i in ativos)))
    print("cidades:", dict(Counter(i["cidade"] for i in ativos)))
    if geo:
        print("requisições ao Nominatim:", geo.requisicoes, "| fotos baixadas:", fotos.baixadas if fotos else "(desligado)")


if __name__ == "__main__":
    main()
