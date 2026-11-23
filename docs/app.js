const fmt = d3.format(",");
const short = n => n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "K" : String(n);
const METRICS = {
  abortions: { label: "Abortions per year", bins: [25e3, 100e3, 500e3, 2e6], show: short },
  rate: { label: "Per 1,000 women aged 15 to 49", bins: [15, 25, 35, 45], show: v => v.toFixed(0) },
  shareOfBirthsPlusAbortions: { label: "Abortions as % of births + abortions", bins: [15, 25, 35, 45], show: v => v.toFixed(0) + "%" },
};
const exact = n => n < 2e6 ? fmt(n) : short(n);
const STEPS = ["--s1", "--s2", "--s3", "--s4", "--s5"].map(v => `var(${v})`);
const sourceLink = (source, label = source.title) => `<a href="${source.url}">${label}</a>`;
const countyKey = name => name.toLowerCase().replace(/[^a-z]/g, "");
const COUNTY_BINS = [10, 50, 250, 1000];
const mapWrap = document.querySelector(".map-wrap");

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
Promise.all([
  d3.json("data/countries.json"), d3.json("vendor/countries-110m.json"),
  d3.json("data/us.json"), d3.json("data/states.json"), d3.json("vendor/states-10m.json"),
  d3.json("data/us-history.json"), d3.json("data/counties.json"), d3.json("data/sources.json"),
]).then(([data, world, us, stateData, usMap, history, counties, bibliography]) => {
  const params = new URLSearchParams(location.search);
  const sources = new Map(bibliography.map(source => [source.id, source]));
  d3.select("#source-list").selectAll("li").data(bibliography).join("li")
    .attr("id", source => source.id).append("a").attr("href", source => source.url).text(source => source.title);
  const cite = (id, label) => sourceLink(sources.get(id), label);
  const newUS = history.recent.rows.at(-1);
  let countyYear, countyMode, countyTransform, countyRows = new Map(), activeCounty, countyGeometry;
  const byId = new Map(data.map(d => [d.id, d]));
  let metric = Object.hasOwn(METRICS, params.get("metric")) ? params.get("metric") : "abortions";
  let selected = byId.get(840), view = "world", activeState = null, picked = false;
  const stateById = new Map(stateData.map(d => [d.id, d]));
  const usTotal = d3.sum(us, d => d.abortions), usLatest = us[us.length - 1];
  const STATE_BINS = { abortions: [3000, 10000, 25000, 60000], rate: [5, 10, 15, 20], shareOfBirthsPlusAbortions: [10, 15, 20, 25] };
  const W = Math.max(1000, document.querySelector(".map-scroll").clientWidth);
  const features = topojson.feature(world, world.objects.countries).features.filter(f => f.properties.name !== "Antarctica");
  const france = features.find(f => +f.id === 250);
  const isGuiana = poly => d3.geoCentroid({ type: "Polygon", coordinates: poly })[0] < 0;
  const guiana = france.geometry.coordinates.filter(isGuiana);
  france.geometry = { type: "MultiPolygon", coordinates: france.geometry.coordinates.filter(c => !isGuiana(c)) };
  features.push({ type: "Feature", id: "254", properties: { name: "French Guiana" }, geometry: { type: "MultiPolygon", coordinates: guiana } });
  const land = { type: "FeatureCollection", features };
  const projection = d3.geoNaturalEarth1().rotate([-11, 0]).fitWidth(W, land);
  const [[, top], [, bottom]] = d3.geoPath(projection).bounds(land);
  const [tx, ty] = projection.translate();
  projection.translate([tx, ty - top + 4]);
  const H = Math.ceil(bottom - top) + 8;
  const path = d3.geoPath(projection);
  const svg = d3.select("#map").attr("viewBox", `0 0 ${W} ${H}`);
  const tip = d3.select("#tip");
  const rec = f => byId.get(+f.id);
  const bins = () => view === "world" ? METRICS[metric].bins : STATE_BINS[metric];
  const color = v => STEPS[d3.bisect(bins(), v)];
  const worldG = svg.append("g"), usG = svg.append("g").style("display", "none");
  const countyG = svg.append("g").style("display", "none");
  const countyLabels = svg.append("g").attr("aria-hidden", "true");
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
  const CHAR = 8, LINE = 16;
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
      const w = Math.max(l.text.length, 6) * CHAR + 12, box = { l: x - w / 2, r: x + w / 2, t: y - LINE, b: y + LINE };
      l.show = box.l >= 0 && box.r <= W && box.t >= 0 && box.b <= H && !placed.some(o => box.l < o.r && box.r > o.l && box.t < o.b && box.b > o.t);
      if (l.show) { placed.push(box); l.sx = x; l.sy = y; }
    });
    labels.style("display", l => l.show ? null : "none").filter(l => l.show).attr("x", l => l.sx).attr("y", l => l.sy);
    labelNames.filter(l => l.show).attr("x", l => l.sx).text(l => l.text);
    labelValues.filter(l => l.show).attr("x", l => l.sx);
  }
  const mapLayer = d3.select(shapes.node().parentNode);
  const zoom = d3.zoom().clickDistance(4).scaleExtent([1, 12]).translateExtent([[0, 0], [W, H]]).extent([[0, 0], [W, H]])
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
        .html(`<b>${d.name}</b><br>${metric === "rate" ? "Per 1,000 women aged 15 to 44" : METRICS[metric].label}: ${METRICS[metric].show(d[metric])} (${d.year}, by state of residence)`);
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
  function saveView() {
    const url = new URL(location.href);
    for (const key of ["view", "state", "basis", "year", "county", "country", "metric"]) url.searchParams.delete(key);
    if (view === "state") {
      url.searchParams.set("state", activeState.abbr);
      if (countyYear) {
        url.searchParams.set("basis", countyMode);
        url.searchParams.set("year", countyYear);
        if (activeCounty) url.searchParams.set("county", activeCounty);
      }
    } else {
      if (view === "us") url.searchParams.set("view", "us");
      else if (picked) url.searchParams.set("country", selected.id);
      if (url.hash === "#county-panel") url.hash = "";
    }
    if (metric !== "abortions") url.searchParams.set("metric", metric);
    if (url.href !== location.href) window.history.replaceState(window.history.state, "", url);
  }
  function crumbs() {
    const c = document.getElementById("crumbs");
    const countyView = view === "state" && !!counties[activeState.id];
    const parts = [view === "world" ? `<strong aria-current="page">World</strong>` : `<button data-go="world">World</button>`];
    if (view !== "world") parts.push(`<span>/</span><button data-go="us">United States</button>`);
    if (view === "state") parts.push(`<span>/</span><strong>${activeState.name}</strong>`);
    if (countyView) parts.push('<a class="county-jump" href="#county-panel">County numbers</a>');
    c.innerHTML = parts.join("");
    document.getElementById("zoom").hidden = view !== "world";
    document.querySelector(".controls").hidden = countyView;
    document.getElementById("panel").setAttribute("aria-live", countyView ? "off" : "polite");
    svg.attr("role", countyView ? "group" : "img").attr("aria-label", view === "world" ? "World map of estimated abortions by country"
      : view === "us" ? "United States map of estimated abortions by state of residence"
      : countyView ? `Reported abortion counts by county in ${activeState.name}` : `Map of ${activeState.name}`);
    document.getElementById("state-pick").hidden = view === "world";
    document.getElementById("state").value = activeState ? activeState.id : "";
    c.querySelectorAll("button").forEach(b => b.onclick = () => b.dataset.go === "world" ? leaveUS() : enterUS());
  }
  function usPanel() {
    document.getElementById("panel").innerHTML = `<h3>United States</h3><dl><dt>Estimated, ${usLatest.year}</dt><dd>${fmt(usLatest.abortions)}</dd>
      <dt>Rate per 1,000 women aged 15 to 44, ${usLatest.year}</dt><dd>${usLatest.rate}</dd>
      <dt>Estimated, 1973 to ${usLatest.year}</dt><dd>${short(usTotal)}</dd>
      <dt>Clinician-provided estimate, ${newUS.year}</dt><dd>${fmt(newUS.abortions)}</dd></dl>
      <p class="small">The map shows 2020 estimates by state of residence. Choose a state for its history and available county counts. The <a href="#us-history">U.S. history chart</a> includes early CDC reports and newer Guttmacher estimates.</p>`;
  }
  function enterUS() {
    view = "us"; activeState = null; selected = byId.get(840);
    countyG.style("display", "none"); tip.attr("hidden", true);
    document.getElementById("map-heading").textContent = "United States, state by state";
    worldG.style("display", "none"); usG.style("display", null).attr("transform", null);
    stateLabels.style("display", null);
    document.getElementById("country").value = 840;
    setBanner("United States", fmt(newUS.abortions), `clinician-provided estimate in ${newUS.year}`, short(usTotal), `estimated from 1973 to ${usLatest.year} in the historical series`);
    usPanel(); crumbs(); paint(); saveView();
  }
  function leaveUS() {
    view = "world"; activeState = null;
    countyG.style("display", "none"); tip.attr("hidden", true);
    document.getElementById("map-heading").textContent = "The world, country by country";
    usG.style("display", "none"); worldG.style("display", null);
    worldBanner(); crumbs(); select(byId.get(840), true);
  }
  function selectState(d, { basis, year, county } = {}) {
    view = "state"; activeState = d;
    activeCounty = county?.startsWith(d.id) && /^\d{5}$/.test(county) ? county : null;
    const reports = counties[d.id];
    countyYear = year ?? "";
    countyMode = reports?.occurrence && (basis === "occurrence" || !reports.years) ? "occurrence" : "residence";
    countyRows = new Map();
    worldG.style("display", "none"); usG.style("display", null);
    document.getElementById("country").value = 840;
    countyG.style("display", "none").selectAll("path").remove();
    tip.attr("hidden", true);
    document.getElementById("map-heading").textContent = d.name;
    const f = stateFeatures.find(x => x.id === d.id), [[x0, y0], [x1, y1]] = usPath.bounds(f);
    const k = Math.min(7, 0.82 / Math.max((x1 - x0) / W, (y1 - y0) / H));
    countyTransform = d3.zoomIdentity.translate(W / 2 - k * (x0 + x1) / 2, H / 2 - k * (y0 + y1) / 2).scale(k);
    usG.attr("transform", countyTransform); countyG.attr("transform", countyTransform);
    stateLabels.style("display", "none");
    setBanner(d.name, fmt(d.abortions), `estimated in ${d.year}`, short(d.total2005to2020), "estimated from 2005 to 2020, the longest unbroken state series");
    document.getElementById("panel").innerHTML = `<div id="county-panel"></div>
      <h3>${d.name} statewide estimates</h3><span class="small">Guttmacher estimate by state of residence, ${d.year}</span><dl><dt>Abortions</dt><dd>${fmt(d.abortions)}</dd><dt>Rate per 1,000 women 15 to 44</dt><dd>${d.rate}</dd><dt>Births</dt><dd>${fmt(d.births)}</dd><dt>Abortions, % of births + abortions</dt><dd>${d.shareOfBirthsPlusAbortions}%</dd></dl>
      ${spark(d, "Guttmacher state estimates. Years before 2005 are intermittent.", true)}
      <details><summary>View annual state estimates</summary><div class="table-scroll"><table><thead><tr><th scope="col">Year</th><th scope="col">Estimated abortions</th></tr></thead><tbody>
      ${d.reported.map(([year, count]) => `<tr><th scope="row">${year}</th><td>${fmt(count)}</td></tr>`).join("")}</tbody></table></div></details>`;
    crumbs(); paint();
    reveal(stateShapes.filter(x => x === f).node());
    showCounties(d);
    saveView();
  }

  function showCounties(state) {
    const panel = document.getElementById("county-panel");
    const countyData = counties[state.id];
    if (!countyData) {
      panel.innerHTML = "<h3>County counts</h3><p class='small'>No county-of-residence series is available for this state in this tracker.</p>";
      return;
    }
    panel.innerHTML = `<h3>Reported abortions by county</h3>
      <div class="county-filters">
        ${countyData.occurrence && countyData.years ? `<label class="pick">Count by <select id="county-mode">
          <option value="residence">Patient residence</option><option value="occurrence">Procedure location</option>
        </select></label>` : ""}
        <label class="pick">Year <select id="county-year"></select></label>
      </div>
      <p class="small"><span id="county-scope"></span> <span id="county-source"></span></p>
      <div id="county-detail" role="status"></div>
      <p id="county-status" class="small" role="status" hidden></p>
      <div class="table-scroll" role="region" aria-label="County counts" tabindex="0"><table id="county-table"></table></div>`;
    const yearPick = document.getElementById("county-year");
    const modePick = document.getElementById("county-mode");
    if (modePick) modePick.value = countyMode;
    const rowFor = feature => countyRows.get(countyKey(feature.properties.name));
    const description = feature => `${rowFor(feature)?.name ?? feature.properties.name}, ${countyYear}: ${countyCount(rowFor(feature))}`;
    const showCountyDetail = () => {
      const feature = countyG.selectAll("path").data().find(f => f.id === activeCounty);
      document.getElementById("county-detail").textContent = feature
        ? description(feature) : "Select a county on the map for its reported count.";
    };
    const update = (series = countyData, refreshYears = false) => {
      if (refreshYears) {
        const years = Object.keys(series.years).sort((a, b) => b - a);
        yearPick.replaceChildren(...years.map(year => new Option(year, year)));
        yearPick.value = years.includes(countyYear) ? countyYear : years[0];
      }
      countyYear = yearPick.value;
      const source = series.sourceByYear?.[countyYear] ?? series.source;
      document.getElementById("county-scope").textContent = series.scope;
      document.getElementById("county-source").innerHTML = series.report
        ? `${cite(series.report, "Source report")} · ${cite(source, "Data file")}`
        : cite(source, "Source report");
      countyRows = new Map(series.years[countyYear].map(row => [countyKey(row.name), row]));
      const heading = countyMode === "occurrence" ? "County of procedure" : "County of residence";
      const rows = d3.select("#county-table").html(`<thead><tr><th scope="col">${heading}</th><th scope="col">Reported abortions · ${countyYear}</th></tr></thead>`)
        .append("tbody").selectAll("tr").data([...countyRows.values()].sort((a, b) => a.name.localeCompare(b.name))).join("tr");
      rows.append("th").attr("scope", "row").text(row => row.name);
      rows.append("td").text(countyCount);
      showCountyDetail();
      paint();
      tip.attr("hidden", true);
      saveView();
    };
    const series = () => countyMode === "occurrence" ? countyData.occurrence : countyData;
    yearPick.addEventListener("change", () => update(series()));
    modePick?.addEventListener("change", () => {
      countyMode = modePick.value;
      update(series(), true);
    });
    update(series(), true);
    const status = document.getElementById("county-status");
    status.hidden = false;
    status.textContent = "Loading county boundaries…";
    countyGeometry ??= d3.json("vendor/counties-10m.json")
      .then(topology => topojson.feature(topology, topology.objects.counties).features);
    countyGeometry.then(features => {
      if (view !== "state" || state !== activeState || !panel.isConnected) return;
      const pickCounty = feature => {
        activeCounty = feature.id;
        countyG.selectAll("path").classed("sel", f => f.id === activeCounty);
        showCountyDetail();
        saveView();
      };
      countyG.style("display", null).selectAll("path")
        .data(features.filter(f => f.id.startsWith(state.id))).join("path")
        .attr("class", "county").attr("d", usPath).attr("tabindex", 0).attr("role", "button")
        .on("mousemove", (event, feature) => {
          const [x, y] = d3.pointer(event, mapWrap);
          tip.attr("hidden", null).style("left", Math.min(x + 12, mapWrap.clientWidth - 200) + "px")
            .style("top", y + 12 + "px").text(description(feature));
        })
        .on("mouseleave", () => tip.attr("hidden", true))
        .on("click", (_, feature) => pickCounty(feature))
        .on("keydown", (event, feature) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            pickCounty(feature);
          }
        });
      status.hidden = true;
      showCountyDetail();
      paint();
    }).catch(() => {
      countyGeometry = null;
      if (panel.isConnected) {
        status.textContent = "County boundaries could not load. County counts are available in the table.";
        document.getElementById("county-detail").textContent = "";
      }
    });
  }

  function countyCount(row) {
    if (!row) return "No published figure";
    return row.count == null ? "Suppressed" : fmt(row.count);
  }

  function paintCountyLabels(features, rowFor) {
    const labels = features.map(feature => {
      const count = rowFor(feature)?.count;
      const [x, y] = countyTransform.apply(usPath.centroid(feature));
      return { count, x, y };
    }).filter(({ count, x, y }) => count != null && Number.isFinite(x) && Number.isFinite(y))
      .sort((a, b) => b.count - a.count);
    const placed = [];
    for (const label of labels) {
      const width = fmt(label.count).length * 8 + 6;
      const bounds = { l: label.x - width / 2, r: label.x + width / 2, t: label.y - 9, b: label.y + 9 };
      if (bounds.l < 0 || bounds.r > W || bounds.t < 0 || bounds.b > H ||
          placed.some(a => bounds.l < a.r && bounds.r > a.l && bounds.t < a.b && bounds.b > a.t)) continue;
      placed.push({ ...bounds, ...label });
    }
    countyLabels.selectAll("text").data(placed).join("text").attr("class", "county-label")
      .attr("x", label => label.x).attr("y", label => label.y).text(label => fmt(label.count));
  }

  function reveal(n) {
    const s = document.querySelector(".map-scroll"), r = n.getBoundingClientRect(), v = s.getBoundingClientRect();
    s.scrollLeft += (r.left + r.right - v.left - v.right) / 2;
  }
  function labelPoint(f) {
    if (+f.id === 840) return projection([-99, 39]);
    if (+f.id === 124) return projection([-105, 57]);
    if (+f.id === 643) return projection([98, 62]);
    if (+f.id === 250) return projection([2.5, 46.6]);
    if (+f.id === 704) return projection([105.5, 20]);
    return path.centroid(f);
  }
  function paint() {
    shapes.filter(f => rec(f)).attr("fill", f => color(rec(f)[metric]));
    shapes.classed("sel", f => picked && rec(f) === selected);
    shapes.filter(".sel").raise();
    stateShapes.attr("fill", f => color(stateById.get(f.id)[metric])).classed("sel", f => stateById.get(f.id) === activeState);
    stateShapes.filter(".sel").raise();
    stateLabels.text(f => `${stateById.get(f.id).abbr} ${METRICS[metric].show(stateById.get(f.id)[metric])}`);
    labelValues.text(l => METRICS[metric].show(l.d[metric]));
    const countyView = view === "state" && !!counties[activeState.id];
    if (countyView) {
      const rowFor = f => countyRows.get(countyKey(f.properties.name));
      const countyShapes = countyG.selectAll("path").attr("fill", f => {
        const n = rowFor(f)?.count;
        return n == null ? "var(--nodata)" : STEPS[d3.bisect(COUNTY_BINS, n)];
      }).attr("aria-label", f => `${f.properties.name}, ${countyYear}: ${countyCount(rowFor(f))}`)
        .classed("sel", f => f.id === activeCounty);
      paintCountyLabels(countyShapes.data(), rowFor);
    } else countyLabels.selectAll("text").remove();
    const b = countyView ? COUNTY_BINS : bins(), s = countyView ? fmt : METRICS[metric].show;
    const names = [`under ${s(b[0])}`, ...b.slice(0, -1).map((v, i) => `${s(v)} to ${s(b[i + 1] - (countyView ? 1 : 0))}`), `${s(b.at(-1))} or more`];
    const countyBasis = countyMode === "occurrence" ? "by procedure location" : "by patient residence";
    document.getElementById("legend").innerHTML = (countyView ? `<strong>${countyYear} reported abortions ${countyBasis}</strong>` : "") +
      names.map((n, i) => `<span><i style="background:${STEPS[i]}"></i>${n}</span>`).join("") +
      `<span><i style="background:var(--nodata)"></i>${countyView ? "suppressed or unavailable" : "no estimate"}</span>` +
      (countyView ? '<a href="#county-panel">County counts table</a>' : "");
  }
  function spark(d, caption = "Reported counts for the years in this series. Coverage varies, and these may differ from modeled estimates.", showGaps = false) {
    if (d.reported.length < 3) return `<p class="small">Too few annual counts to chart a trend for this country.</p>`;
    const x = d3.scaleLinear(d3.extent(d.reported, r => r[0]), [6, 262]), y = d3.scaleLinear([0, d3.max(d.reported, r => r[1])], [62, 8]);
    const line = d3.line(r => x(r[0]), r => y(r[1])).defined(r => r !== null);
    const points = showGaps ? d.reported.flatMap((r, index) =>
      index && r[0] > d.reported[index - 1][0] + 1 ? [null, r] : [r]) : d.reported;
    const dots = showGaps ? d.reported.filter(r => r[0] < 2005)
      .map(([yr, n]) => `<circle cx="${x(yr)}" cy="${y(n)}" r="1.8" fill="var(--mark)"/>`).join("") : "";
    const [a, z] = [d.reported[0], d.reported[d.reported.length - 1]];
    return `<svg viewBox="0 0 268 84" role="img" aria-label="Abortions, ${a[0]} ${fmt(a[1])} to ${z[0]} ${fmt(z[1])}"><path d="${line(points)}" fill="none" stroke="var(--mark)" stroke-width="2"/>${dots}<text x="2" y="80" font-size="11" fill="var(--ink2)">${a[0]}: ${short(a[1])}</text><text x="266" y="80" text-anchor="end" font-size="11" fill="var(--ink2)">${z[0]}: ${short(z[1])}</text></svg><p class="small">${caption}</p>`;
  }
  function select(d, keepBanner) {
    selected = d;
    if (view !== "world") {
      view = "world"; activeState = null;
      usG.style("display", "none"); countyG.style("display", "none"); worldG.style("display", null);
      tip.attr("hidden", true);
      document.getElementById("map-heading").textContent = "The world, country by country";
      crumbs();
    }
    picked = !keepBanner;
    if (!keepBanner) {
      const n = d.reported.length, sum = d3.sum(d.reported, r => r[1]);
      setBanner(d.name, fmt(d.abortions), "estimated per year, 2015 to 2019", n ? short(sum) : "Not available", n ? `reported across the ${n} year${n > 1 ? "s" : ""} in this series, between ${d.reported[0][0]} and ${d.reported[n - 1][0]}. Other years are missing.` : "No annual counts in the source dataset");
    }
    document.getElementById("country").value = d.id;
    const gdp = d.gdpPerCapita2023 ? d.abortions * d.gdpPerCapita2023 : null;
    const money = v => v >= 1e12 ? "$" + (v / 1e12).toFixed(1) + "T" : v >= 1e9 ? "$" + Math.round(v / 1e9) + "B" : "$" + Math.round(v / 1e6) + "M";
    document.getElementById("panel").innerHTML = `<h3>${d.name}</h3><span class="small">Annual average, 2015 to 2019</span>
      <dl><dt>Estimated abortions</dt><dd>${fmt(d.abortions)}</dd><dt>80% uncertainty interval</dt><dd>${exact(d.abortionsLow)} to ${exact(d.abortionsHigh)}</dd>
      <dt>Rate per 1,000 women</dt><dd>${d.rate}</dd><dt>Births per year</dt><dd>${fmt(d.births)}</dd>
      <dt>Abortions, % of births + abortions</dt><dd>${d.shareOfBirthsPlusAbortions}%</dd>
      ${d.shareUnintendedAborted != null ? `<dt>Unintended pregnancies aborted</dt><dd>${d.shareUnintendedAborted}%</dd>` : ""}
      ${gdp ? `<dt>Thought experiment: added annual output</dt><dd>${money(gdp)}</dd>` : ""}</dl>
      ${gdp ? `<p class="small">One year's abortions times 2023 GDP per person. This is an illustration, not a forecast.</p>` : ""}${d.id === 840 ? `<button class="open" id="open-us">Open state map</button>` : ""}${spark(d)}`;
    const open = document.getElementById("open-us");
    if (open) open.onclick = enterUS;
    paint();
    if (picked) {
      const f = features.find(x => rec(x) === d);
      if (f) {
        if (d3.zoomTransform(svg.node()).k > 1) svg.call(zoom.translateTo, ...labelPoint(f));
        reveal(shapes.filter(x => x === f).node());
      }
    }
    saveView();
  }
  const metricButtons = document.querySelectorAll("[data-metric]");
  function paintMetricButtons() {
    metricButtons.forEach(button => {
      const on = button.dataset.metric === metric;
      button.classList.toggle("on", on);
      button.setAttribute("aria-pressed", on);
    });
  }
  paintMetricButtons();
  metricButtons.forEach(b => b.addEventListener("click", () => {
    metric = b.dataset.metric;
    paintMetricButtons(); paint(); saveView();
  }));
  const pick = document.getElementById("country");
  pick.innerHTML = [...data].sort((a, b) => a.name.localeCompare(b.name)).map(d => `<option value="${d.id}">${d.name}</option>`).join("");
  const statePick = document.getElementById("state");
  statePick.innerHTML = `<option value="">All states</option>` + [...stateData].sort((a, b) => a.name.localeCompare(b.name)).map(d => `<option value="${d.id}">${d.name}</option>`).join("");
  statePick.addEventListener("change", () => statePick.value ? selectState(stateById.get(statePick.value)) : enterUS());
  pick.addEventListener("change", () => +pick.value === 840 ? enterUS() : select(byId.get(+pick.value)));
  document.getElementById("table").innerHTML = `<thead><tr><th>Country</th><th>Abortions/yr</th><th>80% interval</th><th>Rate</th><th>Births/yr</th><th>Share</th></tr></thead><tbody>` +
    [...data].sort((a, b) => b.abortions - a.abortions).map(d => `<tr><td>${d.name}</td><td>${fmt(d.abortions)}</td><td>${exact(d.abortionsLow)} to ${exact(d.abortionsHigh)}</td><td>${d.rate}</td><td>${fmt(d.births)}</td><td>${d.shareOfBirthsPlusAbortions}%</td></tr>`).join("") + `</tbody>`;
  const state = stateData.find(d => d.abbr === params.get("state")?.toUpperCase());
  const savedCountry = byId.get(Number(params.get("country")));
  if (state) {
    selectState(state, { basis: params.get("basis"), year: params.get("year"), county: params.get("county") });
    if (location.hash === "#county-panel") document.getElementById("county-panel").scrollIntoView();
  } else if (params.get("view") === "us") {
    enterUS();
  } else if (savedCountry) {
    crumbs(); select(savedCountry);
  } else {
    select(selected, true);
    worldBanner();
    crumbs();
  }
  usChart(us, history);
}).catch(err => {
  console.error(err);
  document.getElementById("banner").innerHTML = "<div><b>Map data failed to load</b><span>Please refresh the page.</span></div>";
});

function usChart(us, history) {
  const W = 720, H = 300, m = { t: 24, r: 24, b: 28, l: 60 };
  const { cdc, recent } = history;
  const series = [
    { label: "CDC reports", rows: cdc.rows, color: "var(--ink2)", dash: "5 4" },
    { label: "Guttmacher historical estimates", rows: us, color: "var(--mark)" },
    { label: "Guttmacher monthly study", rows: recent.rows, color: "var(--sel)" },
  ];
  const first = cdc.rows[0].year, last = recent.rows.at(-1).year;
  const x = d3.scaleLinear([first, last], [m.l, W - m.r]);
  const y = d3.scaleLinear([0, 1800000], [H - m.b, m.t]);
  const root = d3.select("#us-chart");
  const svg = root.append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img")
    .attr("aria-label", `U.S. abortion counts from ${first} to ${last}. Three series with different coverage. The annual data table follows.`);
  y.ticks(4).forEach(n => {
    svg.append("line").attr("x1", m.l).attr("x2", W - m.r).attr("y1", y(n)).attr("y2", y(n)).attr("stroke", "var(--line)");
    svg.append("text").attr("x", m.l - 8).attr("y", y(n) + 4).attr("text-anchor", "end").text(n ? n / 1e6 + "M" : "0");
  });
  [first, 1980, 1990, 2000, 2010, last].forEach(year => svg.append("text").attr("x", x(year)).attr("y", H - 8).attr("text-anchor", "middle").text(year));
  const line = d3.line(d => x(d.year), d => y(d.abortions));
  for (const { label, rows, color, dash } of series) {
    const segments = dash ? [rows.filter(d => d.year < 1998), rows.filter(d => d.year >= 1998)] : [rows];
    svg.append("g").selectAll("path").data(segments).join("path").attr("fill", "none").attr("stroke", color)
      .attr("stroke-width", 2.25).attr("stroke-dasharray", dash ?? null).attr("d", line);
    d3.select("#us-legend").append("span").style("--series-color", color)
      .classed("dashed", !!dash).text(label);
  }
  svg.append("g").selectAll("circle").data(recent.rows).join("circle").attr("cx", d => x(d.year))
    .attr("cy", d => y(d.abortions)).attr("r", 3.5).attr("fill", series[2].color);
  const peak = us.reduce((a, b) => b.abortions > a.abortions ? b : a);
  svg.append("text").attr("x", x(peak.year)).attr("y", y(peak.abortions) - 8).attr("text-anchor", "middle")
    .text(`${peak.year} peak · ${(peak.abortions / 1e6).toFixed(2)}M`);
  const byYear = series.map(s => new Map(s.rows.map(row => [row.year, row])));
  const years = d3.range(first, last + 1);
  d3.select("#us-table").append("tbody").selectAll("tr").data(years).join("tr").each(function (year) {
    const [reported, historical, current] = byYear.map(rows => rows.get(year));
    const display = row => row ? fmt(row.abortions) : "—";
    const interval = current?.low != null && current?.high != null ? `${fmt(current.low)} to ${fmt(current.high)}` : "—";
    const tr = d3.select(this);
    tr.append("th").attr("scope", "row").text(year);
    tr.selectAll("td").data([display(reported), reported?.areas ?? "—", display(historical),
      historical?.rate ?? "—", display(current), interval]).join("td").text(d => d);
  });
  const cross = svg.append("line").attr("y1", m.t).attr("y2", H - m.b).attr("stroke", "var(--ink2)").attr("visibility", "hidden");
  const tip = root.append("div").attr("class", "chart-tip").attr("hidden", true);
  svg.append("rect").attr("x", m.l).attr("y", m.t).attr("width", W - m.l - m.r).attr("height", H - m.t - m.b).attr("fill", "transparent")
    .on("mousemove", event => {
      const year = Math.round(x.invert(d3.pointer(event)[0]));
      const values = series.flatMap(({ label }, index) => {
        const row = byYear[index].get(year);
        return row ? [`${label} · ${fmt(row.abortions)}`] : [];
      });
      cross.attr("x1", x(year)).attr("x2", x(year)).attr("visibility", "visible");
      const width = root.node().clientWidth;
      tip.attr("hidden", null).style("left", Math.max(0, Math.min(x(year) * width / W + 8, width - 235)) + "px")
        .html(`<b>${year}</b><br>${values.join("<br>")}`);
    })
    .on("mouseleave", () => { cross.attr("visibility", "hidden"); tip.attr("hidden", true); });
}
