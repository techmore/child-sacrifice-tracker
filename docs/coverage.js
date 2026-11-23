function renderCountyCoverage(states, counties) {
  const container = document.getElementById("county-coverage");
  const summary = document.createElement("p");
  summary.className = "note coverage-summary";

  const scroll = document.createElement("div");
  scroll.className = "table-scroll";
  scroll.setAttribute("role", "region");
  scroll.setAttribute("aria-label", "Scroll county data coverage by state");
  scroll.tabIndex = 0;

  const table = document.createElement("table");
  table.setAttribute("aria-label", "County data coverage for the 50 states and District of Columbia");
  const heading = table.createTHead().insertRow();
  for (const title of ["State or district", "Patient residence", "Procedure location"]) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = title;
    heading.append(cell);
  }
  scroll.append(table);

  let residenceCount = 0;
  let occurrenceCount = 0;
  const body = table.createTBody();
  for (const state of [...states].sort((a, b) => a.name.localeCompare(b.name))) {
    const row = body.insertRow();
    const name = document.createElement("th");
    name.scope = "row";
    const link = document.createElement("a");
    link.href = `?state=${encodeURIComponent(state.abbr)}#map-section`;
    link.textContent = state.name;
    name.append(link);
    row.append(name);

    const data = counties[state.id];
    if (addCoverage(row.insertCell(), data)) residenceCount++;
    if (addCoverage(row.insertCell(), data?.occurrence)) occurrenceCount++;
  }

  summary.textContent = `County reports in this tracker cover ${residenceCount} jurisdictions by patient residence and ${occurrenceCount} by procedure location. Some published tables omit counties or suppress counts.`;
  container.replaceChildren(summary, scroll);

  function addCoverage(cell, series) {
    const years = Object.keys(series?.years ?? {}).map(Number).sort((a, b) => a - b);
    if (!years.length) {
      cell.className = "coverage-missing";
      cell.textContent = "No series in the tracker";
      return false;
    }
    const groups = [];
    for (const year of years) {
      const last = groups.at(-1);
      if (last && year === last[1] + 1) last[1] = year;
      else groups.push([year, year]);
    }
    const range = document.createElement("span");
    range.className = "coverage-years";
    range.textContent = groups.map(([first, last]) => first === last ? first : `${first}–${last}`).join(", ");
    const scope = document.createElement("span");
    scope.className = "coverage-scope";
    scope.textContent = series.scope;
    cell.append(range, scope);
    return true;
  }
}
