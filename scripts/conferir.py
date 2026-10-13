"""Confere o que foi salvo em tests/fixtures/manual/ contra o manifesto."""
import json
from pathlib import Path

PASTA = Path("tests/fixtures/manual")
itens = json.loads((PASTA / "manifesto.json").read_text(encoding="utf-8"))
import sys
renomear = "--renomear" in sys.argv
falta, desafio, ok = [], [], 0
for i in itens:
    f = PASTA / i["arquivo"]
    if not f.exists():
        achados = [g for g in PASTA.glob(f"*Imóvel {i['id']} -*.html")]
        if achados and renomear:
            achados[0].rename(f)
            for pasta_ap in PASTA.glob(achados[0].stem + "_files"):
                pasta_ap.rename(PASTA / (f.stem + "_files"))
    if not f.exists():
        if achados:
            falta.append(f"{i['arquivo']} (salvo com o nome do navegador; rode com --renomear)")
            continue
        falta.append(i["arquivo"]); continue
    t = f.read_text(encoding="utf-8", errors="replace")
    if "Just a moment" in t or "challenge-platform" in t[:5000] or len(t) < 20000:
        desafio.append(i["arquivo"])
    else:
        ok += 1
print(f"ok: {ok} | faltam: {len(falta)} | suspeitos (desafio/vazio): {len(desafio)}")
for n in desafio: print("  suspeito:", n)
for n in falta[:10]: print("  falta:", n)
if len(falta) > 10: print(f"  ... e mais {len(falta)-10}")
