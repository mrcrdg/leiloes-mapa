"""Parsing das páginas do Leilão Imóvel (HTML salvo à mão; ver PLAN.md, seção 1)."""
from __future__ import annotations

import html as _html
import re
from pathlib import Path
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser

FONTE = "leilaoimovel"
BASE = "https://www.leilaoimovel.com.br/"
ID_RE = re.compile(r"-(\d{6,8})(?:-\d+-venda-direta-caixa)?$")
DATA_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})(?:\s+(?:às\s+)?(\d{2}):(\d{2}))?")
TIPOS = {
    "casa": "casa", "casas": "casa", "apartamento": "apartamento", "apartamentos": "apartamento",
    "terreno": "terreno", "terrenos": "terreno", "prédio": "prédio", "prédios": "prédio",
    "garagem": "garagem", "vaga": "garagem", "galpão": "galpão", "comercial": "comercial", "outros": "outros", "rural": "rural", "área": "rural",
}
MODALIDADES = {"judicial": "judicial", "extrajudicial": "extrajudicial", "venda direta": "venda direta"}


def preco_br(txt: str | None) -> float | None:
    """'R$ 1.234,56' -> 1234.56; qualquer outra coisa ('Não informado') -> None."""
    if not txt:
        return None
    m = re.search(r"R\$\s*([\d.]+,\d{2})", txt)
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None


def calcular_desconto(preco: float | None, avaliacao: float | None, site_pct: int | None) -> int | None:
    """Desconto sobre a avaliação. Sem avaliação não há desconto: o % que o site mostra nesses casos é a
    queda da 1ª para a 2ª praça (conferido em 3022450 e 3049455), que é outra grandeza."""
    if not preco or not avaliacao or avaliacao <= 0:
        return None
    calculado = round(100 * (1 - preco / avaliacao))
    if site_pct is not None and abs(site_pct - calculado) <= 1:
        return site_pct
    return calculado


def numero_br(txt: str | None) -> float | None:
    m = re.search(r"([\d.]+(?:,\d+)?)", txt or "")
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None


def data_iso(txt: str | None) -> str | None:
    m = DATA_RE.search(txt or "")
    if not m:
        return None
    d, mo, a, h, mi = m.groups()
    return f"{a}-{mo}-{d}T{h or '00'}:{mi or '00'}"


def id_do_link(url: str) -> str | None:
    m = ID_RE.search(url.split("?")[0].split("#")[0])
    return m.group(1) if m else None


CIDADES_URL = {"londrina": "Londrina", "cambe": "Cambé", "rolandia": "Rolândia", "ibipora": "Ibiporã"}


def cidade_do_link(url: str) -> str | None:
    m = re.search(r"/imovel/pr/([^/]+)/", url)
    return CIDADES_URL.get(m.group(1)) if m else None


def tipo_do_titulo(titulo: str) -> str | None:
    primeira = titulo.split(" ")[0].lower()
    return TIPOS.get(primeira)


def _praças(textos: list[str]) -> list[dict]:
    """'2ª Praça: 08/12/2026 14:00R$ 77.500,00' -> {'rotulo','data','valor'}."""
    out, vistos = [], set()
    for t in textos:
        t = re.sub(r"\s+", " ", t).strip()
        m = re.match(r"(1ª Praça|2ª Praça|Praça única|Encerra em)\s*:?\s*(.*)", t)
        if m and data_iso(m.group(2)):
            item = {"rotulo": m.group(1), "data": data_iso(m.group(2)), "valor": preco_br(m.group(2))}
            chave = tuple(item.values())
            if chave not in vistos:
                vistos.add(chave)
                out.append(item)
    return out


def parse_listagem(html: str) -> list[dict]:
    """Um dict por imóvel. Chaves ausentes na fonte viram None."""
    tree = LexborHTMLParser(html)
    saida, vistos = [], set()
    for box in tree.css("div.place-box"):
        a = box.css_first("a.Link_Redirecter")
        if a is None:
            continue
        url = urljoin(BASE, a.attributes.get("href", ""))  # algumas listagens salvas trazem link relativo
        iid = id_do_link(url)
        if not iid or iid in vistos:
            continue
        vistos.add(iid)

        def txt(sel):
            n = box.css_first(sel)
            return re.sub(r"\s+", " ", n.text()).strip() if n else None

        titulo = txt(".address b")
        img = box.css_first("img")
        alt = img.attributes.get("alt", "") if img else ""
        m_bairro = re.search(r"\]\s*\['([^']*)'\]\s*-\s*\['([^']*)'\]", _html.unescape(alt))
        pct = re.search(r"(\d+)\s*%", txt(".down b") or "")
        cats = [c.text(strip=True) for c in box.css(".categories a")]
        modalidade = next((MODALIDADES[c.lower()] for c in cats if c.lower() in MODALIDADES), None)
        caixa = "caixa" in url and "venda-direta-caixa" in url
        if modalidade is None and caixa:
            modalidade = "venda direta"
        saida.append({
            "id": iid,
            "fonte": FONTE,
            "cidade": cidade_do_link(url),
            "url_anuncio": url,
            "titulo": titulo,
            "tipo": tipo_do_titulo(titulo or ""),
            "endereco": txt(".address span") or None,
            "bairro": (m_bairro.group(1) or None) if m_bairro else None,
            "preco": preco_br(txt(".discount-price")),
            "avaliacao": preco_br(txt(".last-price")),
            "desconto_site_pct": int(pct.group(1)) if pct else None,  # pode ser 1ª→2ª praça; ver calcular_desconto
            "modalidade": modalidade,
            "categorias": cats,
            "praças": _praças([n.text() for n in box.css(".infos span")]),
            "encerramento": data_iso(txt(".tag span")),
            "foto_listagem": img.attributes.get("src") if img else None,
        })
    return saida


def _linhas(html: str) -> list[str]:
    html = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    partes = re.sub(r"<[^>]+>", "\n", html).split("\n")
    return [_html.unescape(p).strip() for p in partes if p.strip()]


def _depois(linhas: list[str], rotulo: str) -> str | None:
    for i, l in enumerate(linhas):
        if l == rotulo and i + 1 < len(linhas):
            return linhas[i + 1]
    return None


def parse_detalhe(html: str) -> dict:
    """Campos que só existem na página do imóvel. Ausente na fonte -> None."""
    L = _linhas(html)
    if "Considerações Legais" in L:  # depois disso vêm imóveis vizinhos e rodapé
        L = L[:L.index("Considerações Legais")]
    tree = LexborHTMLParser(html)
    loc = None
    if "Localização:" in L:
        i = L.index("Localização:")
        loc = [x.lstrip("/") for x in L[i + 1:i + 5] if x.startswith("/") or x == "PR"]
    tipo_linha = _depois(L, "Tipo:")
    tipo, modalidade = None, None
    if tipo_linha:
        tipo = TIPOS.get(tipo_linha.lower(), tipo_linha.lower())
        i = L.index("Tipo:")
        resto = L[i + 2] if i + 2 < len(L) else ""
        modalidade = MODALIDADES.get(resto.lstrip("/").strip().lower())
    aval = _depois(L, "Valor de Avaliação:")
    m = re.search(r"https://image\.leilaoimovel\.com\.br/images/[^\"' ]+-g\.webp", html)
    foto = m.group(0) if m else None
    area_total = numero_br(_depois(L, "Área Total:"))
    area_util = numero_br(_depois(L, "Área Útil:"))
    situacao = _depois(L, "Situação:")
    return {
        "tipo_detalhe": tipo,
        "modalidade_detalhe": modalidade,
        "bairro_detalhe": loc[2] if loc and len(loc) > 2 else None,
        "rua_detalhe": loc[3] if loc and len(loc) > 3 else None,
        "area_m2": area_util or area_total or numero_br(_depois(L, "Área Terreno:")),
        "area_total_m2": area_total,
        "quartos": int(numero_br(_depois(L, "Quartos:"))) if _depois(L, "Quartos:") else None,
        "vagas": int(numero_br(_depois(L, "Vagas:"))) if _depois(L, "Vagas:") else None,
        "ocupado": None if situacao is None else situacao.lower().startswith("ocupado"),
        "avaliacao_detalhe": preco_br(aval),
        "precisao_site": _depois(L, "Precisão da geolocalização:"),
        "data_inclusao": data_iso(_depois(L, "Data de Inclusão:")),
        "praças_detalhe": _praças([" ".join(L[i:i + 3]) for i, l in enumerate(L)
                                   if re.match(r"(1ª Praça|2ª Praça|Praça única)", l)]),
        "foto_detalhe": foto,
    }


def carregar(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8", errors="replace")
