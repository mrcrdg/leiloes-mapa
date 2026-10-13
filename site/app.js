(() => {
  "use strict";
  const COR = { "judicial": "#d94841", "extrajudicial": "#e08a1e", "venda direta": "#2a8f4a" };
  const COR_OUTRA = "#6b7280";
  const NOME_PREC = { exato: "localização exata", rua: "na rua (número aproximado)", bairro: "centro do bairro" };
  const dados = window.DADOS || { imoveis: [], atualizado_em: null };
  const todos = dados.imoveis.filter(i => i.ativo);
  const $ = id => document.getElementById(id);

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const brl = v => v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const dataBR = iso => iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";
  const cor = i => COR[i.modalidade] || COR_OUTRA;
  const seguro = u => /^https:\/\/www\.leilaoimovel\.com\.br\//.test(u || "") ? u : "#";

  $("atualizado").textContent = dados.atualizado_em ? "Dados de " + dataBR(dados.atualizado_em) : "Sem dados";

  const mapa = L.map("mapa").setView([-23.31, -51.16], 12);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, referrerPolicy: "strict-origin-when-cross-origin", attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(mapa);
  const grupo = L.markerClusterGroup({ maxClusterRadius: 40 }).addTo(mapa);

  const fotoRemotaOk = u => /^https:\/\/image\.leilaoimovel\.com\.br\//.test(u || "");
  function fotoHtml(i) {
    if (i.foto_local) return `<img src="${esc(i.foto_local)}" alt="" loading="lazy">`;
    // sem cópia local: tenta a foto da fonte; se o site recusar, a imagem some sem deixar ícone quebrado
    if (fotoRemotaOk(i.foto_url)) return `<img src="${esc(i.foto_url)}" alt="" referrerpolicy="no-referrer" onerror="this.remove()">`;
    return "";
  }

  function popup(i) {
    const praca = (i.datas_leilao || []).map(d => `${esc(d.rotulo)}: ${dataBR(d.data)}${d.valor ? " (" + brl(d.valor) + ")" : ""}`).join("<br>");
    const aviso = i.precisao_geo && i.precisao_geo !== "exato" ? `<div class="aviso">Posição aproximada: ${esc(NOME_PREC[i.precisao_geo])}.</div>` : "";
    return `<div class="pop">
      ${fotoHtml(i)}
      <h3>${esc(i.titulo)}</h3>${i.novo ? "<b>NOVO</b>" : ""}
      <div>${esc(i.endereco || "Endereço não informado")}${i.bairro ? " — " + esc(i.bairro) : ""} · ${esc(i.cidade)}</div>
      <dl>
        <dt>Tipo</dt><dd>${esc(i.tipo || "—")}</dd>
        <dt>Preço</dt><dd><b>${brl(i.preco)}</b></dd>
        <dt>Avaliação</dt><dd>${brl(i.avaliacao)}</dd>
        <dt>Desconto</dt><dd>${i.desconto_pct != null ? i.desconto_pct + "%" : "—"}</dd>
        <dt>Modalidade</dt><dd>${esc(i.modalidade || "—")}</dd>
        <dt>Leilão</dt><dd>${praca || "—"}</dd>
        ${i.area_m2 ? `<dt>Área</dt><dd>${i.area_m2.toLocaleString("pt-BR")} m²</dd>` : ""}
        ${i.ocupado != null ? `<dt>Ocupado</dt><dd>${i.ocupado ? "sim" : "não"}</dd>` : ""}
      </dl>${aviso}
      <a class="ver" href="${esc(seguro(i.url_anuncio))}" target="_blank" rel="noopener">Ver anúncio</a></div>`;
  }

  function precoCurto(v) {
    if (v == null) return "s/ preço";
    if (v >= 1e6) return "R$ " + (v / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mi";
    if (v >= 1e3) return "R$ " + Math.round(v / 1e3).toLocaleString("pt-BR") + " mil";
    return "R$ " + Math.round(v);
  }

  function pino(i) {
    const classes = ["pin", i.novo ? "novo" : "", i.precisao_geo !== "exato" ? "aprox" : ""].join(" ");
    const icone = L.divIcon({
      className: "", iconSize: [92, 28], iconAnchor: [46, 14], popupAnchor: [0, -15],
      html: `<div class="${classes}" style="background:${cor(i)}">${esc(precoCurto(i.preco))}</div>`
    });
    return L.marker([i.lat, i.lng], { icon: icone }).bindPopup(popup(i), { maxWidth: 260 });
  }

  function preencher(sel, valores) {
    [...new Set(valores.filter(Boolean))].sort().forEach(v => sel.add(new Option(v, v)));
  }
  preencher($("f-cidade"), todos.map(i => i.cidade));
  preencher($("f-tipo"), todos.map(i => i.tipo));
  preencher($("f-mod"), todos.map(i => i.modalidade));

  function filtrados() {
    const min = parseFloat($("f-min").value), max = parseFloat($("f-max").value), desc = parseFloat($("f-desc").value);
    const cidade = $("f-cidade").value, tipo = $("f-tipo").value, mod = $("f-mod").value, novos = $("f-novos").checked;
    return todos.filter(i =>
      (isNaN(min) || (i.preco != null && i.preco >= min)) &&
      (isNaN(max) || (i.preco != null && i.preco <= max)) &&
      (!cidade || i.cidade === cidade) && (!tipo || i.tipo === tipo) && (!mod || i.modalidade === mod) &&
      (isNaN(desc) || (i.desconto_pct != null && i.desconto_pct >= desc)) &&
      (!novos || i.novo));
  }

  function desenhar() {
    const sel = filtrados();
    grupo.clearLayers();
    const com = sel.filter(i => i.lat != null && i.lng != null), sem = sel.filter(i => i.lat == null || i.lng == null);
    grupo.addLayers(com.map(pino));
    $("n-sem").textContent = sem.length;
    $("contagem").textContent = `${sel.length} de ${todos.length} imóveis · ${com.length} no mapa · ${sem.length} sem coordenada`;
    const ul = $("lista-itens");
    ul.replaceChildren(...sem.map(i => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = seguro(i.url_anuncio); a.target = "_blank"; a.rel = "noopener";
      a.textContent = i.titulo || i.id;
      li.append(a, ` — ${brl(i.preco)}${i.endereco ? " — " + i.endereco : ""}`);
      return li;
    }));
  }

  ["f-min", "f-max", "f-desc"].forEach(id => $(id).addEventListener("input", desenhar));
  ["f-cidade", "f-tipo", "f-mod", "f-novos"].forEach(id => $(id).addEventListener("change", desenhar));
  $("limpar").addEventListener("click", () => {
    ["f-min", "f-max", "f-desc"].forEach(id => $(id).value = "");
    $("f-cidade").value = $("f-tipo").value = $("f-mod").value = ""; $("f-novos").checked = false; desenhar();
  });
  function alternar(btn, painel) {
    btn.addEventListener("click", () => {
      painel.hidden = !painel.hidden; btn.setAttribute("aria-expanded", String(!painel.hidden));
      setTimeout(() => mapa.invalidateSize(), 50);
    });
  }
  alternar($("btn-filtros"), $("filtros")); alternar($("btn-lista"), $("lista"));

  const leg = $("legenda");
  Object.entries({ ...COR, outra: COR_OUTRA }).forEach(([k, c]) => {
    const s = document.createElement("span"); const chip = document.createElement("i");
    chip.className = "chip"; chip.style.background = c; s.append(chip, k); leg.append(s);
  });
  desenhar();
})();
