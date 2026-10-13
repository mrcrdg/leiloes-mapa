"""Lê as listagens salvas à mão e gera tarefas.html + manifesto.json (um link por imóvel)."""
import glob, html, json, re, sys
from pathlib import Path

PASTA = Path("tests/fixtures/manual")
ID_RE = re.compile(r"-(\d{6,8})(?:-\d+-venda-direta-caixa)?$")

urls = {}
for f in sorted(PASTA.glob("listagem-p*.html")):
    t = f.read_text(encoding="utf-8", errors="replace")
    for u in re.findall(r'href="(https://www\.leilaoimovel\.com\.br/imovel/[^"#?]+)"', t):
        urls.setdefault(html.unescape(u), f.name)

itens = []
for u, origem in urls.items():
    m = ID_RE.search(u)
    if not m:
        sys.exit(f"sem id reconhecível: {u}")
    itens.append({"id": m.group(1), "url": u, "arquivo": f"imovel-{m.group(1)}.html", "origem": origem})
if len({i["id"] for i in itens}) != len(itens):
    sys.exit("ids repetidos")

(PASTA / "manifesto.json").write_text(json.dumps(itens, ensure_ascii=False, indent=1), encoding="utf-8")

linhas = "\n".join(
    f'<li><label><input type="checkbox" data-k="{i["id"]}"> '
    f'<a href="{html.escape(i["url"])}" target="_blank" rel="noopener">{i["id"]}</a></label> '
    f'→ <code>{i["arquivo"]}</code></li>' for i in itens)
(PASTA / "tarefas.html").write_text(f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tarefas de coleta</title>
<style>body{{font-family:system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem;line-height:1.6}}
li{{margin:.4rem 0;list-style:none}}code{{background:#eee;padding:.1rem .35rem;border-radius:4px}}
.nota{{background:#fff7d6;padding:.6rem .8rem;border-radius:6px}}</style></head><body>
<h1>Tarefas de coleta: {len(itens)} imóveis</h1>
<p class="nota">Clique no número → a página abre numa aba nova → <code>Ctrl+S</code> → pasta
<code>tests/fixtures/manual/</code> → use o nome ao lado. Tipo: "Página da Web, somente HTML".
A caixinha só marca o que você já fez (fica salva neste navegador).</p>
<p id="cont"></p>
<ul>{linhas}</ul>
<script>
const cs=[...document.querySelectorAll('input[data-k]')];
const salvo=()=>{{try{{return JSON.parse(localStorage.getItem('feitos')||'[]')}}catch(e){{return[]}}}};
const feitos=new Set(salvo());
function atual(){{document.getElementById('cont').textContent=feitos.size+' de '+cs.length+' salvos';
 try{{localStorage.setItem('feitos',JSON.stringify([...feitos]))}}catch(e){{}}}}
cs.forEach(c=>{{c.checked=feitos.has(c.dataset.k);c.onchange=()=>{{c.checked?feitos.add(c.dataset.k):feitos.delete(c.dataset.k);atual()}}}});
atual();
</script></body></html>""", encoding="utf-8")
print(len(itens), "imóveis")
