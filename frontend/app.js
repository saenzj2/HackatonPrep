// Deploy skeleton: proves the frontend reaches the API in production.
// The page is served by the API itself (/app), so relative URLs hit the same origin.
// To point it at another API, open the page with ?api=https://host
const API = new URLSearchParams(location.search).get("api") || "..";

const $ = (id) => document.getElementById(id);

async function call(path, options) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body && body.error;
    throw new Error(err ? `${err.code}: ${err.message}` : `HTTP ${res.status}`);
  }
  return body;
}

async function checkHealth() {
  try {
    const h = await call("/health");
    $("status").textContent = `API ${h.status ?? "ok"} · ${JSON.stringify(h)}`;
  } catch (e) {
    $("status").textContent = `API no disponible: ${e.message}`;
  }
}

function text(t, lang) {
  return t && typeof t === "object" ? (t[lang] ?? t.en) : (t ?? "");
}

function render(data, lang) {
  const rows = data.rotations.map((r) => {
    const seq = r.sequence.map((s) => `${s.season}: ${s.crop_name}`).join(" → ");
    return `<article>
      <h3>#${r.rank} ${seq}</h3>
      <p><strong>${Math.round(r.score * 100)}/100</strong>${r.viable ? "" : " · no viable"}</p>
      <p>${text(r.explanation, lang)}</p>
    </article>`;
  });
  $("results").innerHTML = rows.join("") || "<p>Sin resultados.</p>";
}

$("form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const [lat, lon] = $("field").value.split(",").map(Number);
  const lang = $("lang").value;
  $("results").textContent = "Calculando…";
  try {
    render(await call("/recommendations", { method: "POST", body: JSON.stringify({ lat, lon }) }), lang);
  } catch (e) {
    $("results").textContent = `Error: ${e.message}`;
  }
});

checkHealth();
