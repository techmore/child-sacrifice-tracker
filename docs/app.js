const fmt = d3.format(",");
const short = n => n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "K" : String(n);
const METRICS = {
  abortions: { label: "Abortions per year", bins: [25e3, 100e3, 500e3, 2e6], show: short },
  rate: { label: "Per 1,000 women aged 15 to 49", bins: [15, 25, 35, 45], show: v => v.toFixed(0) },
  shareOfBirthsPlusAbortions: { label: "Abortions as % of births + abortions", bins: [15, 25, 35, 45], show: v => v.toFixed(0) + "%" },
};
const STEPS = ["--s1", "--s2", "--s3", "--s4", "--s5"].map(v => `var(${v})`);
const SOURCES = [
  ["WHO, Abortion fact sheet", "https://www.who.int/news-room/fact-sheets/detail/abortion"],
  ["Bearak et al. 2022, BMJ Global Health, country estimates", "https://pmc.ncbi.nlm.nih.gov/articles/PMC8943721/"],
  ["Bearak et al. 2020, Lancet Global Health, global trends", "https://pubmed.ncbi.nlm.nih.gov/32710833/"],
  ["Guttmacher, Induced Abortion Worldwide", "https://www.guttmacher.org/fact-sheet/induced-abortion-worldwide"],
  ["Guttmacher, Global Abortion Incidence Dataset", "https://osf.io/5k7fp/"],
  ["Guttmacher, US National and State Pregnancy Trends", "https://osf.io/kthnf/"],
  ["Society of Family Planning, #WeCount", "https://societyfp.org/research/wecount/wecount-december-2025-data/"],
  ["World Bank, GDP per capita 2023", "https://data.worldbank.org/indicator/NY.GDP.PCAP.CD"],
  ["NIMH, Suicide statistics", "https://www.nimh.nih.gov/health/statistics/suicide"],
  ["NCHS Data Brief 541", "https://www.cdc.gov/nchs/products/databriefs/db541.htm"],
  ["Our World in Data, WHO suicide rates", "https://ourworldindata.org/grapher/death-rate-from-suicides-gho"],
  ["Holt-Lunstad et al. 2010, PLoS Medicine", "https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.1000316"],
  ["Grover and Helliwell, How's Life at Home?", "https://www.nber.org/papers/20794"],
  ["KFF, The Hyde Amendment and Medicaid coverage", "https://www.kff.org/womens-health-policy/issue-brief/the-hyde-amendment-and-coverage-for-abortion-services/"],
  ["KFF, State policies on abortion coverage", "https://www.kff.org/womens-health-policy/issue-brief/interactive-how-state-policies-shape-access-to-abortion-coverage/"],
  ["ACGME, OB/GYN requirement impact statement, 2022", "https://prep.acgme.org/globalassets/pfassets/reviewandcomment/220_obstetricsandgynecology_2022-06-24_impact.pdf"],
  ["Vinekar et al. 2024, residency training after Dobbs", "https://works.bepress.com/callie-coxbauer/20"],
  ["Biggs et al. 2013, reasons for seeking abortion", "https://bmcwomenshealth.biomedcentral.com/articles/10.1186/1472-6874-13-29"],
  ["Taylor, Decimatio: Myth, Discipline and Death", "https://resolve.cambridge.org/core/services/aop-cambridge-core/content/view/504D6242E0621DE1B2CC0D32B92765E3/S0066477422000090a.pdf/decimatio-myth-discipline-and-death-in-the-roman-republic.pdf"],
  ["Livius.org, Decimation", "https://livius.org/articles/concept/decimation"],
  ["Archaeology Magazine, Carthage 2014", "https://archaeology.org/news/2014/01/23/140123-carthage-tophet-sacrifice"],
  ["Wikipedia, Child sacrifice", "https://en.wikipedia.org/wiki/Child_sacrifice"],
  ["Planned Parenthood v. ACLA, 290 F.3d 1058 (9th Cir. 2002)", "https://pld.cs.luc.edu/courses/ethics/spr25/mnotes/documents/nuremberg/PPvACLA_9th_enbanc.pdf"],
];

const now = new Date();
const start = new Date(now.getFullYear(), 0, 1);
const end = new Date(now.getFullYear() + 1, 0, 1);
document.getElementById("ytd").textContent = ((73.3 * (now - start)) / (end - start)).toFixed(1) + "M";
document.querySelectorAll(".waffle").forEach(w => {
  const n = +w.dataset.n;
  w.setAttribute("role", "img");
  w.setAttribute("aria-label", `${n} of 100 squares filled`);
  w.innerHTML = Array.from({ length: 100 }, (_, i) => `<i class="${i < n ? "f" : ""}"></i>`).join("");
});
document.getElementById("source-list").innerHTML = SOURCES.map(([t, u]) => `<li><a href="${u}">${t}</a></li>`).join("");

Promise.all([d3.json("data/countries.json"), d3.json("vendor/countries-110m.json"), d3.json("data/us.json"), d3.json("data/states.json"), d3.json("vendor/states-10m.json")]).then(([data, world, us, stateData, usMap]) => {
  const byId = new Map(data.map(d => [d.id, d]));
  let metric = "abortions", selected = byId.get(840), view = "world", activeState = null, picked = false;
  const stateById = new Map(stateData.map(d => [d.id, d]));
  const usTotal = d3.sum(us, d => d.abortions), usLatest = us[us.length - 1];
  const STATE_BINS = { abortions: [3000, 10000, 25000, 60000], rate: [5, 10, 15, 20], shareOfBirthsPlusAbortions: [10, 15, 20, 25] };
  const W = 1400, H = 720;
  const features = topojson.feature(world, world.objects.countries).features.filter(f => f.properties.name !== "Antarctica");
  const projection = d3.geoNaturalEarth1().fitSize([W, H], { type: "FeatureCollection", features });
  const path = d3.geoPath(projection);
  const svg = d3.select("#map").attr("viewBox", `0 0 ${W} ${H}`);
  const tip = d3.select("#tip");
  const rec = f => byId.get(+f.id);
  const bins = () => view === "world" ? METRICS[metric].bins : STATE_BINS[metric];
  const color = v => STEPS[d3.bisect(bins(), v)];
  const worldG = svg.append("g"), usG = svg.append("g").style("display", "none");
  const stateFeatures = topojson.feature(usMap, usMap.objects.states).features.filter(f => stateById.has(f.id));
  const albers = d3.geoAlbersUsa().fitExtent([[8, 8], [W - 8, H - 8]], { type: "FeatureCollection", features: stateFeatures });
  const usPath = d3.geoPath(albers);

  const shapes = worldG.append("g").selectAll("path").data(features).join("path")
    .attr("d", path).attr("class", f => "country" + (rec(f) ? "" : " none"))
    .on("mousemove", (e, f) => {
      const d = rec(f), [x, y] = d3.pointer(e, document.querySelector(".map-wrap"));
      tip.attr("hidden", null).style("left", Math.min(x + 12, document.querySelector(".map-wrap").clientWidth - 200) + "px").style("top", y + 12 + "px")
        .html(d ? `<b>${d.name}</b><br>${METRICS[metric].label}: ${METRICS[metric].show(d[metric])}` : `<b>${f.properties.name}</b><br>No published estimate`);
    })
    .on("mouseleave", () => tip.attr("hidden", true))
    .on("click", (e, f) => { if (+f.id === 840) enterUS(); else if (rec(f)) select(rec(f)); });
  const CHAR = 7.6, LINE = 15;
  const shortName = d => ({ "United States": "USA", "United Kingdom": "UK", "DR Congo": "DR Congo", "Central African Republic": "CAR" })[d.name] || d.name;
  const labelData = features.filter(rec).sort((a, b) => rec(b).abortions - rec(a).abortions).map(f => {
    const d = rec(f), [[x0], [x1]] = path.bounds(f), [x, y] = labelPoint(f);
    return { f, d, x, y, span: x1 - x0, name: shortName(d) };
  }).filter(l => Number.isFinite(l.x));
  const labels = worldG.append("g").selectAll("text").data(labelData).join("text").attr("class", "map-label");
  const labelNames = labels.append("tspan").attr("class", "n").attr("dy", -2);
  const labelValues = labels.append("tspan").attr("class", "v").attr("dy", LINE);
  function placeLabels(t) {
    const placed = [];
    labelData.forEach(l => {
      const [x, y] = t.apply([l.x, l.y]);
      l.text = l.span * t.k >= l.name.length * CHAR * 0.7 ? l.name : (l.d.iso3 || l.name);
      const w = Math.max(l.text.length, 6) * CHAR + 4, box = { l: x - w / 2, r: x + w / 2, t: y - LINE, b: y + LINE };
      l.show = box.l >= 0 && box.r <= W && box.t >= 0 && box.b <= H && !placed.some(o => box.l < o.r && box.r > o.l && box.t < o.b && box.b > o.t);
      if (l.show) { placed.push(box); l.sx = x; l.sy = y; }
    });
    labels.style("display", l => l.show ? null : "none").filter(l => l.show).attr("x", l => l.sx).attr("y", l => l.sy);
    labelNames.filter(l => l.show).attr("x", l => l.sx).text(l => l.text);
    labelValues.filter(l => l.show).attr("x", l => l.sx);
  }
  const mapLayer = d3.select(shapes.node().parentNode);
  const zoom = d3.zoom().scaleExtent([1, 12]).translateExtent([[0, 0], [W, H]]).extent([[0, 0], [W, H]])
    .filter(e => view === "world" && !e.button && !e.touches && e.type !== "wheel")
    .on("zoom", e => { mapLayer.attr("transform", e.transform); placeLabels(e.transform); });
  svg.call(zoom).on("wheel.zoom", null).on("dblclick.zoom", null).style("touch-action", "pan-x pan-y pinch-zoom");
  document.querySelectorAll("#zoom button").forEach(b => b.addEventListener("click", () => {
    if (b.dataset.z === "reset") svg.call(zoom.transform, d3.zoomIdentity);
    else svg.call(zoom.scaleBy, b.dataset.z === "in" ? 1.7 : 1 / 1.7);
  }));
  placeLabels(d3.zoomIdentity);

  const stateShapes = usG.append("g").selectAll("path").data(stateFeatures).join("path").attr("class", "state").attr("d", usPath)
    .on("mousemove", (e, f) => {
      const d = stateById.get(f.id), wrap = document.querySelector(".map-wrap"), [x, y] = d3.pointer(e, wrap);
      tip.attr("hidden", null).style("left", Math.min(x + 12, wrap.clientWidth - 200) + "px").style("top", y + 12 + "px")
        .html(`<b>${d.name}</b><br>${METRICS[metric].label}: ${METRICS[metric].show(d[metric])} (${d.year})`);
    })
    .on("mouseleave", () => tip.attr("hidden", true))
    .on("click", (e, f) => selectState(stateById.get(f.id)));
  const SMALL = new Set(["CT", "DC", "DE", "MA", "MD", "NH", "NJ", "RI", "VT", "HI"]);
  const stateLabels = usG.append("g").selectAll("text").data(stateFeatures.filter(f => !SMALL.has(stateById.get(f.id).abbr))).join("text")
    .attr("class", "state-label").attr("x", f => usPath.centroid(f)[0]).attr("y", f => usPath.centroid(f)[1] + 3);

  function setBanner(place, annual, annualNote, total, totalNote) {
    document.getElementById("banner").innerHTML = `<div><b>${place}</b><span>Selected area</span></div><div><b>${annual}</b><span>${annualNote}</span></div><div><b>${total}</b><span>${totalNote}</span></div>`;
  }
  function worldBanner() {
    setBanner("World", "73.3M", "estimated per year, 2015 to 2019", "No reliable total", "No source measures a worldwide cumulative count. Records begin in the 20th century and remain incomplete.");
  }
  function crumbs() {
    const c = document.getElementById("crumbs");
    const parts = [`<button data-go="world">World</button>`];
    if (view !== "world") parts.push(`<span>/</span><button data-go="us">United States</button>`);
    if (view === "state") parts.push(`<span>/</span><strong>${activeState.name}</strong>`);
    c.innerHTML = parts.join("");
    document.getElementById("zoom").hidden = view !== "world";
    c.querySelectorAll("button").forEach(b => b.onclick = () => b.dataset.go === "world" ? leaveUS() : enterUS());
  }
  function usPanel() {
    document.getElementById("panel").innerHTML = `<h3>United States</h3><span class="small">Guttmacher estimates</span><dl><dt>Abortions, ${usLatest.year}</dt><dd>${fmt(usLatest.abortions)}</dd><dt>Rate per 1,000 women</dt><dd>${usLatest.rate}</dd><dt>Recorded, 1973 to ${usLatest.year}</dt><dd>${short(usTotal)}</dd><dt>#WeCount, 2025</dt><dd>1,126,760</dd></dl><p class="small">Select a state on the map. Counts before 1973 are not included because abortion was largely illegal and unrecorded.</p>`;
  }
  function enterUS() {
    view = "us"; activeState = null; selected = byId.get(840);
    worldG.style("display", "none"); usG.style("display", null).attr("transform", null);
    stateLabels.style("display", null);
    document.getElementById("country").value = 840;
    setBanner("United States", fmt(usLatest.abortions), `estimated in ${usLatest.year}. #WeCount counted 1,126,760 in 2025.`, short(usTotal), `recorded from 1973 to ${usLatest.year}, the span of the national series`);
    usPanel(); crumbs(); paint();
  }
  function leaveUS() {
    view = "world"; activeState = null;
    usG.style("display", "none"); worldG.style("display", null);
    worldBanner(); crumbs(); select(byId.get(840), true);
  }
  function selectState(d) {
    view = "state"; activeState = d;
    const f = stateFeatures.find(x => x.id === d.id), [[x0, y0], [x1, y1]] = usPath.bounds(f);
    const k = Math.min(7, 0.82 / Math.max((x1 - x0) / W, (y1 - y0) / H));
    usG.attr("transform", `translate(${W / 2 - k * (x0 + x1) / 2},${H / 2 - k * (y0 + y1) / 2}) scale(${k})`);
    stateLabels.style("display", "none");
    setBanner(d.name, fmt(d.abortions), `estimated in ${d.year}`, short(d.total2005to2020), "estimated from 2005 to 2020, the longest unbroken state series");
    document.getElementById("panel").innerHTML = `<h3>${d.name}</h3><span class="small">Guttmacher estimate, ${d.year}</span><dl><dt>Abortions</dt><dd>${fmt(d.abortions)}</dd><dt>Rate per 1,000 women</dt><dd>${d.rate}</dd><dt>Births</dt><dd>${fmt(d.births)}</dd><dt>Abortions, % of births + abortions</dt><dd>${d.shareOfBirthsPlusAbortions}%</dd></dl>${spark(d, "Guttmacher state estimates. Years before 2005 are intermittent.")}<p class="small">County figures are not shown. There is no national county dataset, and small-county counts can expose individual patients.</p>`;
    crumbs(); paint();
  }

  function labelPoint(f) {
    if (+f.id === 840) return projection([-99, 39]);
    if (+f.id === 124) return projection([-105, 57]);
    if (+f.id === 643) return projection([98, 62]);
    return path.centroid(f);
  }
  function paint() {
    shapes.filter(f => rec(f)).attr("fill", f => color(rec(f)[metric]));
    shapes.classed("sel", f => picked && rec(f) === selected);
    stateShapes.attr("fill", f => color(stateById.get(f.id)[metric])).classed("sel", f => stateById.get(f.id) === activeState);
    stateLabels.text(f => `${stateById.get(f.id).abbr} ${METRICS[metric].show(stateById.get(f.id)[metric])}`);
    labelValues.text(l => METRICS[metric].show(l.d[metric]));
    const b = bins(), s = METRICS[metric].show;
    const names = [`under ${s(b[0])}`, ...b.slice(0, -1).map((v, i) => `${s(v)} to ${s(b[i + 1])}`), `${s(b[b.length - 1])} or more`];
    document.getElementById("legend").innerHTML = names.map((n, i) => `<span><i style="background:${STEPS[i]}"></i>${n}</span>`).join("") + `<span><i style="background:var(--nodata)"></i>no estimate</span>`;
  }
  function spark(d, caption = "Officially reported counts, where complete. These may differ from modeled estimates.") {
    if (d.reported.length < 3) return `<p class="small">Too few complete official annual counts to chart a trend for this country.</p>`;
    const x = d3.scaleLinear(d3.extent(d.reported, r => r[0]), [6, 262]), y = d3.scaleLinear([0, d3.max(d.reported, r => r[1])], [62, 8]);
    const line = d3.line(r => x(r[0]), r => y(r[1]));
    const [a, z] = [d.reported[0], d.reported[d.reported.length - 1]];
    return `<svg viewBox="0 0 268 84" role="img" aria-label="Officially reported abortions, ${a[0]} ${fmt(a[1])} to ${z[0]} ${fmt(z[1])}"><path d="${line(d.reported)}" fill="none" stroke="var(--mark)" stroke-width="2"/><text x="2" y="80" font-size="11" fill="var(--ink2)">${a[0]}: ${short(a[1])}</text><text x="266" y="80" text-anchor="end" font-size="11" fill="var(--ink2)">${z[0]}: ${short(z[1])}</text></svg><p class="small">${caption}</p>`;
  }
  function select(d, keepBanner) {
    selected = d;
    if (view !== "world") { view = "world"; activeState = null; usG.style("display", "none"); worldG.style("display", null); crumbs(); }
    picked = !keepBanner;
    if (!keepBanner) {
      const n = d.reported.length, sum = d3.sum(d.reported, r => r[1]);
      setBanner(d.name, fmt(d.abortions), "estimated per year, 2015 to 2019", n ? short(sum) : "Not available", n ? `officially recorded across ${n} complete year${n > 1 ? "s" : ""} between ${d.reported[0][0]} and ${d.reported[n - 1][0]}. Other years are missing.` : "No complete official annual counts in the source dataset");
    }
    document.getElementById("country").value = d.id;
    const gdp = d.gdpPerCapita2023 ? d.abortions * d.gdpPerCapita2023 : null;
    const money = v => v >= 1e12 ? "$" + (v / 1e12).toFixed(1) + "T" : "$" + Math.round(v / 1e9) + "B";
    document.getElementById("panel").innerHTML = `<h3>${d.name}</h3><span class="small">Annual average, 2015 to 2019</span>
      <dl><dt>Estimated abortions</dt><dd>${fmt(d.abortions)}</dd><dt>Likely range</dt><dd>${short(d.abortionsLow)} to ${short(d.abortionsHigh)}</dd>
      <dt>Rate per 1,000 women</dt><dd>${d.rate}</dd><dt>Births per year</dt><dd>${fmt(d.births)}</dd>
      <dt>Abortions, % of births + abortions</dt><dd>${d.shareOfBirthsPlusAbortions}%</dd>
      ${d.shareUnintendedAborted != null ? `<dt>Unintended pregnancies aborted</dt><dd>${d.shareUnintendedAborted}%</dd>` : ""}
      ${gdp ? `<dt>Thought experiment: added annual output</dt><dd>${money(gdp)}</dd>` : ""}</dl>
      ${gdp ? `<p class="small">One year's abortions times 2023 GDP per person. This is an illustration, not a forecast.</p>` : ""}${d.id === 840 ? `<button class="open" id="open-us">Open state map</button>` : ""}${spark(d)}`;
    const open = document.getElementById("open-us");
    if (open) open.onclick = enterUS;
    paint();
  }
  document.querySelectorAll("[data-metric]").forEach(b => b.addEventListener("click", () => {
    metric = b.dataset.metric;
    document.querySelectorAll("[data-metric]").forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", x === b); });
    paint();
  }));
  const pick = document.getElementById("country");
  pick.innerHTML = [...data].sort((a, b) => a.name.localeCompare(b.name)).map(d => `<option value="${d.id}">${d.name}</option>`).join("");
  pick.addEventListener("change", () => +pick.value === 840 ? enterUS() : select(byId.get(+pick.value)));
  document.getElementById("table").innerHTML = `<thead><tr><th>Country</th><th>Abortions/yr</th><th>Likely range</th><th>Rate</th><th>Births/yr</th><th>Share</th></tr></thead><tbody>` +
    [...data].sort((a, b) => b.abortions - a.abortions).map(d => `<tr><td>${d.name}</td><td>${fmt(d.abortions)}</td><td>${short(d.abortionsLow)} to ${short(d.abortionsHigh)}</td><td>${d.rate}</td><td>${fmt(d.births)}</td><td>${d.shareOfBirthsPlusAbortions}%</td></tr>`).join("") + `</tbody>`;
  select(selected, true);
  worldBanner();
  crumbs();
  usChart(us);
});

function usChart(us) {
  const W = 720, H = 300, m = { t: 16, r: 18, b: 28, l: 52 };
  const point = { year: 2025, abortions: 1126760 };
  const x = d3.scaleLinear([1973, 2025], [m.l, W - m.r]), y = d3.scaleLinear([0, 1800000], [H - m.b, m.t]);
  const root = d3.select("#us-chart"), svg = root.append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img")
    .attr("aria-label", "US abortions per year, 1973 to 2020, peaking near 1.6 million in 1990");
  y.ticks(4).forEach(t => {
    svg.append("line").attr("x1", m.l).attr("x2", W - m.r).attr("y1", y(t)).attr("y2", y(t)).attr("stroke", "var(--line)");
    svg.append("text").attr("x", m.l - 8).attr("y", y(t) + 4).attr("text-anchor", "end").text(t ? t / 1e6 + "M" : "0");
  });
  [1973, 1990, 2005, 2020].forEach(t => svg.append("text").attr("x", x(t)).attr("y", H - 8).attr("text-anchor", "middle").text(t));
  svg.append("path").datum(us).attr("fill", "none").attr("stroke", "var(--mark)").attr("stroke-width", 2).attr("d", d3.line(d => x(d.year), d => y(d.abortions)));
  svg.append("circle").attr("cx", x(point.year)).attr("cy", y(point.abortions)).attr("r", 5).attr("fill", "var(--bg)").attr("stroke", "var(--mark)").attr("stroke-width", 2);
  svg.append("text").attr("x", x(point.year)).attr("y", y(point.abortions) - 11).attr("text-anchor", "end").text("#WeCount 2025: 1.13M");
  const peak = us.reduce((a, b) => b.abortions > a.abortions ? b : a);
  svg.append("text").attr("x", x(peak.year)).attr("y", y(peak.abortions) - 8).attr("text-anchor", "middle").text(`${peak.year} peak: ${(peak.abortions / 1e6).toFixed(2)}M`);
  const cross = svg.append("line").attr("y1", m.t).attr("y2", H - m.b).attr("stroke", "var(--ink2)").attr("visibility", "hidden");
  const tip = root.append("div").attr("id", "us-tip").style("position", "absolute").style("pointer-events", "none").style("background", "var(--ink)").style("color", "var(--bg)").style("font", "13px system-ui").style("padding", "5px 8px").style("border-radius", "5px").style("display", "none");
  svg.append("rect").attr("x", m.l).attr("y", m.t).attr("width", W - m.l - m.r).attr("height", H - m.t - m.b).attr("fill", "transparent")
    .on("mousemove", e => {
      const yr = Math.round(x.invert(d3.pointer(e)[0])), d = us.find(u => u.year === yr);
      if (!d) { cross.attr("visibility", "hidden"); tip.style("display", "none"); return; }
      cross.attr("x1", x(yr)).attr("x2", x(yr)).attr("visibility", "visible");
      const scale = root.node().clientWidth / W;
      tip.style("display", "block").style("left", Math.min(x(yr) * scale + 8, root.node().clientWidth - 150) + "px").style("top", "8px").html(`<b>${yr}</b>: ${fmt(d.abortions)}`);
    })
    .on("mouseleave", () => { cross.attr("visibility", "hidden"); tip.style("display", "none"); });
}
