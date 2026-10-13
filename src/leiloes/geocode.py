"""Geocodificação com Nominatim: cascata endereço → rua → bairro, com cache persistente.

`precisao_geo`: "exato" (casa/prédio), "rua", "bairro" ou "nenhuma".
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx

URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "leiloes-londrina-estudo-pessoal/0.1 (marcia.rrdg@gmail.com)"
INTERVALO_S = 1.1  # política do Nominatim: no máximo 1 req/s
# Caixas delimitadoras aproximadas (oeste, sul, leste, norte): rejeitam acertos fora da cidade
CIDADES = {
    "Londrina": (-51.40, -23.65, -50.95, -23.10),
    "Cambé": (-51.42, -23.40, -51.12, -23.10),
    "Rolândia": (-51.60, -23.45, -51.25, -23.15),
    "Ibiporã": (-51.22, -23.40, -50.88, -23.15),
}
CACHE_PADRAO = Path("data/geocode_cache.json")


def limpar_endereco(endereco: str | None) -> tuple[str | None, str | None]:
    """Devolve (rua, numero) tirando CEP, parênteses e lixo; (None, None) se não der para achar a rua."""
    if not endereco:
        return None, None
    s = re.sub(r"\(.*?\)", " ", endereco)
    s = re.sub(r"CEP:?\s*[\d.-]+", " ", s, flags=re.I)
    if re.match(r"\s*(vaga|box|garagem)", s, flags=re.I):
        return None, None
    s = re.sub(r"\s+s/n\b.*", "", s, flags=re.I)
    rua = re.split(r",|\s+n[ºo°.]?\s*\d|\s+-\s", s, maxsplit=1)[0].strip()
    m = re.search(r",\s*N\.?\s*(\d[\d.]*)|\bn[ºo°.]?\s*(\d[\d.]*)|,\s*(\d[\d.]*)\b", s, flags=re.I)
    numero = next((g.replace(".", "") for g in (m.groups() if m else ()) if g), None)
    if len(rua) < 4 or rua.lower().startswith(("lote", "quadra")):
        return None, None
    return rua, numero


def _dentro(lat: float, lng: float, caixa: tuple) -> bool:
    return caixa[0] <= lng <= caixa[2] and caixa[1] <= lat <= caixa[3]


class Geocodificador:
    def __init__(self, cache_path: Path = CACHE_PADRAO, cliente: httpx.Client | None = None, dormir=time.sleep):
        self.cache_path = cache_path
        self.cache: dict[str, dict | None] = (
            json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        )
        self.cliente = cliente or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30)
        self._dormir = dormir
        self._ultimo = 0.0
        self.requisicoes = 0

    def _buscar(self, params: dict, caixa: tuple) -> dict | None:
        chave = json.dumps(params, sort_keys=True, ensure_ascii=False)
        if chave in self.cache:
            return self.cache[chave]
        espera = INTERVALO_S - (time.monotonic() - self._ultimo)
        if espera > 0:
            self._dormir(espera)
        resp = None
        for tentativa in range(3):
            self._ultimo = time.monotonic()
            self.requisicoes += 1
            resp = self.cliente.get(URL, params={**params, "format": "jsonv2", "limit": 1, "countrycodes": "br",
                                                 "addressdetails": 1, "viewbox": ",".join(map(str, caixa)),
                                                 "bounded": 1})
            if resp.status_code not in (429, 500, 502, 503, 504):
                break
            self._dormir(2 ** (tentativa + 2))
        if resp is None or resp.status_code != 200:
            print(f"  geocode: HTTP {getattr(resp, 'status_code', '?')} para {params}; não salvo no cache")
            return None
        dados = resp.json()
        achado = None
        if dados:
            lat, lng = float(dados[0]["lat"]), float(dados[0]["lon"])
            if _dentro(lat, lng, caixa):
                achado = {"lat": lat, "lng": lng, "tipo": dados[0].get("addresstype") or dados[0].get("type")}
        self.cache[chave] = achado
        self.salvar()
        return achado

    def salvar(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")

    def geocodificar(self, endereco: str | None, bairro: str | None, cidade: str = "Londrina") -> dict:
        """{'lat','lng','precisao_geo'}; precisao 'nenhuma' e lat/lng None se nada servir."""
        rua, numero = limpar_endereco(endereco)
        base = {"city": cidade, "state": "Paraná"}
        caixa = CIDADES[cidade]
        if rua and numero:
            r = self._buscar({**base, "street": f"{numero} {rua}"}, caixa)
            if r and r["tipo"] in ("house", "building", "residential", "commercial", "place"):
                return {"lat": r["lat"], "lng": r["lng"], "precisao_geo": "exato"}
        if rua:
            r = self._buscar({**base, "street": rua}, caixa)
            if r:
                return {"lat": r["lat"], "lng": r["lng"], "precisao_geo": "rua"}
        if bairro:
            r = self._buscar({"q": f"{bairro}, {cidade}, Paraná, Brasil"}, caixa)  # q não mistura com campos estruturados
            if r:
                return {"lat": r["lat"], "lng": r["lng"], "precisao_geo": "bairro"}
        return {"lat": None, "lng": None, "precisao_geo": "nenhuma"}
