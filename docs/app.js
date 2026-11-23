const fmt = d3.format(",");
const short = n => n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "K" : String(n);
const METRICS = {
  abortions: { label: "Abortions per year", bins: [25e3, 100e3, 500e3, 2e6], show: short },
  rate: { label: "Per 1,000 women aged 15 to 49", bins: [15, 25, 35, 45], show: v => v.toFixed(0) },
  shareOfBirthsPlusAbortions: { label: "Abortions as % of births + abortions", bins: [15, 25, 35, 45], show: v => v.toFixed(0) + "%" },
};
const STEPS = ["--s1", "--s2", "--s3", "--s4", "--s5"].map(v => `var(${v})`);
const LABELED = [840, 156, 356, 76, 643, 586, 360, 566, 124, 36, 180, 710];
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

Promise.all([d3.json("data/countries.json"), d3.json("vendor/countries-110m.json"), d3.json("data/us.json")]).then(([data, world, us]) => {
  const byId = new Map(data.map(d => [d.id, d]));
  let metric = "abortions", selected = byId.get(840);
  const W = 960, H = 490;
  const features = topojson.feature(world, world.objects.countries).features.filter(f => f.properties.name !== "Antarctica");
  const projection = d3.geoNaturalEarth1().fitSize([W, H], { type: "FeatureCollection", features });
  const path = d3.geoPath(projection);
  const svg = d3.select("#map").attr("viewBox", `0 0 ${W} ${H}`);
  const tip = d3.select("#tip");
  const rec = f => byId.get(+f.id);
  const color = v => STEPS[d3.bisect(METRICS[metric].bins, v)];

  const shapes = svg.append("g").selectAll("path").data(features).join("path")
    .attr("d", path).attr("class", f => "country" + (rec(f) ? "" : " none"))
    .on("mousemove", (e, f) => {
      const d = rec(f), [x, y] = d3.pointer(e, document.querySelector(".map-wrap"));
      tip.attr("hidden", null).style("left", Math.min(x + 12, document.querySelector(".map-wrap").clientWidth - 200) + "px").style("top", y + 12 + "px")
        .html(d ? `<b>${d.name}</b><br>${METRICS[metric].label}: ${METRICS[metric].show(d[metric])}` : `<b>${f.properties.name}</b><br>No published estimate`);
    })
    .on("mouseleave", () => tip.attr("hidden", true))
    .on("click", (e, f) => { if (rec(f)) select(rec(f)); });
  const labels = svg.append("g").selectAll("text").data(features.filter(f => LABELED.includes(+f.id) && rec(f))).join("text")
    .attr("class", "map-label").attr("x", f => labelPoint(f)[0]).attr("y", f => labelPoint(f)[1]);

  function labelPoint(f) {
    if (+f.id === 840) return projection([-99, 39]);
    if (+f.id === 124) return projection([-105, 57]);
    if (+f.id === 643) return projection([98, 62]);
    return path.centroid(f);
  }
  function paint() {
    shapes.filter(f => rec(f)).attr("fill", f => color(rec(f)[metric]));
    shapes.classed("sel", f => rec(f) === selected);
    labels.text(f => `${rec(f).name === "United States" ? "USA" : rec(f).name} ${METRICS[metric].show(rec(f)[metric])}`);
    const b = METRICS[metric].bins, s = METRICS[metric].show;
    const names = [`under ${s(b[0])}`, ...b.slice(0, -1).map((v, i) => `${s(v)} to ${s(b[i + 1])}`), `${s(b[b.length - 1])} or more`];
    document.getElementById("legend").innerHTML = names.map((n, i) => `<span><i style="background:${STEPS[i]}"></i>${n}</span>`).join("") + `<span><i style="background:var(--nodata)"></i>no estimate</span>`;
  }
  function spark(d) {
    if (d.reported.length < 3) return `<p class="small">Too few complete official annual counts to chart a trend for this country.</p>`;
    const x = d3.scaleLinear(d3.extent(d.reported, r => r[0]), [6, 262]), y = d3.scaleLinear([0, d3.max(d.reported, r => r[1])], [62, 8]);
    const line = d3.line(r => x(r[0]), r => y(r[1]));
    const [a, z] = [d.reported[0], d.reported[d.reported.length - 1]];
    return `<svg viewBox="0 0 268 84" role="img" aria-label="Officially reported abortions, ${a[0]} ${fmt(a[1])} to ${z[0]} ${fmt(z[1])}"><path d="${line(d.reported)}" fill="none" stroke="var(--mark)" stroke-width="2"/><text x="2" y="80" font-size="11" fill="var(--ink2)">${a[0]}: ${short(a[1])}</text><text x="266" y="80" text-anchor="end" font-size="11" fill="var(--ink2)">${z[0]}: ${short(z[1])}</text></svg><p class="small">Officially reported counts, where complete. These may differ from modeled estimates.</p>`;
  }
  function select(d) {
    selected = d;
    document.getElementById("country").value = d.id;
    const gdp = d.gdpPerCapita2023 ? d.abortions * d.gdpPerCapita2023 : null;
    const money = v => v >= 1e12 ? "$" + (v / 1e12).toFixed(1) + "T" : "$" + Math.round(v / 1e9) + "B";
    document.getElementById("panel").innerHTML = `<h3>${d.name}</h3><span class="small">Annual average, 2015 to 2019</span>
      <dl><dt>Estimated abortions</dt><dd>${fmt(d.abortions)}</dd><dt>Likely range</dt><dd>${short(d.abortionsLow)} to ${short(d.abortionsHigh)}</dd>
      <dt>Rate per 1,000 women</dt><dd>${d.rate}</dd><dt>Births per year</dt><dd>${fmt(d.births)}</dd>
      <dt>Abortions, % of births + abortions</dt><dd>${d.shareOfBirthsPlusAbortions}%</dd>
      ${d.shareUnintendedAborted != null ? `<dt>Unintended pregnancies aborted</dt><dd>${d.shareUnintendedAborted}%</dd>` : ""}
      ${gdp ? `<dt>Thought experiment: added annual output</dt><dd>${money(gdp)}</dd>` : ""}</dl>
      ${gdp ? `<p class="small">One year's abortions times 2023 GDP per person. This is an illustration, not a forecast.</p>` : ""}${spark(d)}`;
    paint();
  }
  document.querySelectorAll("[data-metric]").forEach(b => b.addEventListener("click", () => {
    metric = b.dataset.metric;
    document.querySelectorAll("[data-metric]").forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", x === b); });
    paint();
  }));
  const pick = document.getElementById("country");
  pick.innerHTML = [...data].sort((a, b) => a.name.localeCompare(b.name)).map(d => `<option value="${d.id}">${d.name}</option>`).join("");
  pick.addEventListener("change", () => select(byId.get(+pick.value)));
  document.getElementById("table").innerHTML = `<thead><tr><th>Country</th><th>Abortions/yr</th><th>Likely range</th><th>Rate</th><th>Births/yr</th><th>Share</th></tr></thead><tbody>` +
    [...data].sort((a, b) => b.abortions - a.abortions).map(d => `<tr><td>${d.name}</td><td>${fmt(d.abortions)}</td><td>${short(d.abortionsLow)} to ${short(d.abortionsHigh)}</td><td>${d.rate}</td><td>${fmt(d.births)}</td><td>${d.shareOfBirthsPlusAbortions}%</td></tr>`).join("") + `</tbody>`;
  select(selected);
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
