"""Miniaturas WebP (~400px de largura) a partir das fotos que já estão salvas junto às páginas."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

LARGURA = 400


def gerar_miniatura(origem: Path, destino: Path, largura: int = LARGURA) -> bool:
    """False se a imagem não existir ou não abrir (o imóvel fica sem foto, não derruba o pipeline)."""
    if not origem.is_file():
        return False
    try:
        with Image.open(origem) as im:
            im = im.convert("RGB")
            if im.width > largura:
                im = im.resize((largura, round(im.height * largura / im.width)), Image.LANCZOS)
            destino.parent.mkdir(parents=True, exist_ok=True)
            im.save(destino, "WEBP", quality=78)
        return True
    except OSError:
        return False


class BaixadorDeFotos:
    """Baixa fotos que só existem como link (listagens salvas sem a pasta `_files`).

    Educado: 1 requisição a cada 2,5 s, cache em disco, e desiste de vez no primeiro 403/429
    (nada de insistir ou contornar bloqueio; o imóvel fica sem foto)."""

    def __init__(self, pasta: Path, intervalo_s: float = 2.5):
        import httpx
        self.pasta, self.intervalo = pasta, intervalo_s
        self.cliente = httpx.Client(headers={"User-Agent": "leiloes-londrina-estudo-pessoal/0.1"}, timeout=30,
                                    follow_redirects=True)
        self.bloqueado = False
        self.baixadas = 0
        self._ultimo = 0.0

    def obter(self, iid: str, url: str) -> Path | None:
        destino = self.pasta / f"{iid}.webp"
        if destino.is_file():
            return destino
        if self.bloqueado:
            return None
        import time
        espera = self.intervalo - (time.monotonic() - self._ultimo)
        if espera > 0:
            time.sleep(espera)
        self._ultimo = time.monotonic()
        try:
            resp = self.cliente.get(url)
        except Exception as e:  # rede caiu etc.: segue sem foto
            print(f"  foto {iid}: {type(e).__name__}")
            return None
        if resp.status_code in (403, 429):
            self.bloqueado = True
            print(f"  fotos: HTTP {resp.status_code}; parei de baixar fotos (sem contornar). Imóveis ficam sem foto.")
            return None
        if resp.status_code != 200:
            print(f"  foto {iid}: HTTP {resp.status_code}")
            return None
        self.pasta.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(resp.content)
        self.baixadas += 1
        return destino
