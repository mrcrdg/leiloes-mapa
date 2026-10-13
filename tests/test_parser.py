from pathlib import Path

import pytest

from leiloes.geocode import limpar_endereco
from leiloes.sources.leilaoimovel import (
    calcular_desconto, carregar, data_iso, id_do_link, parse_detalhe, parse_listagem, preco_br,
)

FIX = Path(__file__).parent / "fixtures" / "manual"


def listagem(n):
    return parse_listagem(carregar(FIX / f"listagem-p{n}.html"))


def detalhe(iid):
    return parse_detalhe(carregar(FIX / f"imovel-{iid}.html"))


def test_helpers():
    assert preco_br("R$ 1.234,56") == 1234.56
    assert preco_br("Não informado") is None
    assert data_iso("13/10/2026 às 18:00") == "2026-10-13T18:00"
    assert id_do_link("https://x/imovel/pr/londrina/casa-imovel-3057212") == "3057212"
    assert id_do_link("https://x/imovel/pr/londrina/a-cef-2871089-8128400021471-venda-direta-caixa") == "2871089"


def test_listagem_soma_68_imoveis_unicos():
    ids = [i["id"] for n in (1, 2, 3, 4) for i in listagem(n)]
    assert len(ids) == 68 and len(set(ids)) == 68


def test_listagem_caixa_com_desconto():
    caixa = next(i for i in listagem(1) if i["id"] == "2871089")
    assert caixa["preco"] == 159328.58
    assert caixa["avaliacao"] == 250000.0
    assert caixa["desconto_site_pct"] == 36
    assert caixa["bairro"] == "Jardim Kase"
    assert caixa["modalidade"] == "venda direta"
    assert caixa["encerramento"] == "2026-10-13T18:00"


def test_site_mostra_pct_sem_avaliacao_mas_nao_e_desconto_sobre_avaliacao():
    # 3022450: o site mostra 39%, que é 1ª→2ª praça (2.312.019 → 1.412.511), não desconto sobre avaliação
    item = next(i for i in listagem(1) if i["id"] == "3022450")
    assert item["avaliacao"] is None and item["desconto_site_pct"] == 39
    assert calcular_desconto(item["preco"], item["avaliacao"], item["desconto_site_pct"]) is None


def test_calcular_desconto():
    assert calcular_desconto(159328.58, 250000.0, 36) == 36
    assert calcular_desconto(50.0, 100.0, None) == 50  # calcula quando o site não traz
    assert calcular_desconto(50.0, 100.0, 7) == 50      # % do site incoerente com a avaliação: vale a conta
    assert calcular_desconto(50.0, None, 7) is None


def test_detalhe_caixa():
    d = detalhe("2871089")
    assert d["area_m2"] == 70.28 and d["quartos"] == 2
    assert d["avaliacao_detalhe"] == 250000.0
    assert d["foto_detalhe"].endswith("-g.webp") and "2871089" in d["foto_detalhe"]


def test_detalhe_extrajudicial_ocupado_e_praca():
    d = detalhe("3057212")
    assert d["ocupado"] is True
    assert d["avaliacao_detalhe"] is None  # "Não informado"
    assert d["praças_detalhe"] == [{"rotulo": "1ª Praça", "data": "2026-10-20T11:00", "valor": 499000.0}]


def test_detalhe_ignora_imoveis_vizinhos_no_rodape():
    # a página lista outros imóveis depois de "Considerações Legais"; não podem entrar nas praças
    assert len(detalhe("3057212")["praças_detalhe"]) == 1


@pytest.mark.parametrize("end,rua,num", [
    ("RUA SAMPAIO VIDAL,N. 183 QD 02 TERRAS N 20, JARDIM KASE - CEP: 86026-350, LONDRINA - PARANA", "RUA SAMPAIO VIDAL", "183"),
    ("Avenida Arcebispo Dom Geraldo Fernandes, 2.330 (Lote 07 da Quadra 1)", "Avenida Arcebispo Dom Geraldo Fernandes", "2330"),
    ("Avenida Café Rubiacea s/n", "Avenida Café Rubiacea", None),
    ("Vaga de Garagem nº 40 - Edifício Manhattan", None, None),
    (None, None, None),
])
def test_limpar_endereco(end, rua, num):
    assert limpar_endereco(end) == (rua, num)


@pytest.mark.parametrize("arq,qtd,cidade", [("listagem-p1-cambe.html", 10, "Cambé"), ("listagem-p1-rolandia.html", 6, "Rolândia"),
                                         ("listagem-p1-ibipora.html", 3, "Ibiporã")])
def test_listagens_de_outras_cidades(arq, qtd, cidade):
    itens = parse_listagem(carregar(FIX / arq))
    assert len(itens) == qtd and {i["cidade"] for i in itens} == {cidade}


def test_cidade_de_londrina_vem_da_url():
    assert {i["cidade"] for n in (1, 2, 3, 4) for i in listagem(n)} == {"Londrina"}


def test_links_sempre_absolutos():
    for arq in ("listagem-p1.html", "listagem-p1-cambe.html", "listagem-p1-rolandia.html", "listagem-p1-ibipora.html"):
        for i in parse_listagem(carregar(FIX / arq)):
            assert i["url_anuncio"].startswith("https://www.leilaoimovel.com.br/imovel/pr/"), i["url_anuncio"]
