const assert = require("node:assert/strict");
const { test } = require("node:test");
const path = require("node:path");
const { chromium } = require("playwright");
const evidenceRecords = require("../docs/data/evidence-records.json");
const states = require("../docs/data/states.json");
const history = require("../docs/data/us-history.json");
const countyReports = require("../docs/data/counties.json");
const docs = path.resolve(__dirname, "../docs");
const origin = "https://tracker.test";

async function checkMap(viewport, run, { failCounties = false } = {}) {
  const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH });
  try {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.route("**/*", route => {
      const url = new URL(route.request().url());
      if (url.origin !== origin || (failCounties && url.pathname === "/data/counties.json")) {
        return route.abort();
      }
      const file = url.pathname === "/" ? "index.html" : url.pathname.slice(1);
      return route.fulfill({ path: path.join(docs, file) });
    });
    await run(page);
    assert.deepEqual(errors, []);
  } finally {
    await browser.close();
  }
}

for (const width of [1280, 390]) {
  test(`state totals, Pennsylvania county counts and reload at ${width}px`, async () => {
    await checkMap({ width, height: 850 }, async page => {
      await page.goto(origin);
      await page.locator("#open-us").waitFor();
      assert.match(await page.locator("#banner").innerText(), /73\.3M.*worldwide, averaged over 2015–2019/s);
      assert.match(await page.locator("#banner").innerText(), /gives no worldwide count for 2025/);
      assert.match(await page.locator("#ytd + span").innerText(), /projection using the 2015–2019 average/);
      await page.locator("#open-us").click();
      const breakdown = page.locator("#us-total-breakdown");
      await breakdown.locator("summary").click();
      assert.match(await page.locator("#banner").innerText(), /60\.9M.*U\.S\. total across 48 years, 1973–2020/s);
      assert.match(await breakdown.innerText(), /2025 is 1,125,930 clinician-provided abortions/);
      assert.match(await breakdown.innerText(), /73\.3M is an annual average for 2015–2019/);
      const rows = await breakdown.locator("tbody tr").evaluateAll(elements => elements.map(row => Array.from(row.cells, cell => cell.textContent)));
      assert.deepEqual(rows, [
        ["1973–1979", "7", "8,080,620"], ["1980–1989", "10", "15,736,610"],
        ["1990–1999", "10", "14,300,450"], ["2000–2009", "10", "12,366,880"],
        ["2010–2019", "10", "9,495,050"], ["2020", "1", "930,160"],
      ]);
      assert.equal(await breakdown.locator("tfoot td").last().textContent(), "60,909,770");
      await page.getByRole("link", { name: "View the annual estimates" }).click();
      assert.equal(await page.locator("#us-annual-data").evaluate(el => el.open), true);
      const california = page.locator(".state").filter({ visible: true });
      const index = await california.evaluateAll(nodes => nodes.findIndex(node => node.__data__.id === "06"));
      await california.nth(index).click();
      assert.equal(await breakdown.isVisible(), false);
      const summary = page.locator("#state-total");
      await page.locator(".county-outlines path").first().waitFor();
      assert.match(await page.locator(".state-focus-label").textContent(), /CA 187,560 · 2025/);
      for (const state of states) {
        await page.selectOption("#state", state.id);
        const recent = history.recent.states[state.abbr].at(-1);
        assert.equal(await summary.locator("strong").innerText(), `${state.name} ${state.abortions.toLocaleString("en-US")}`);
        assert.match(await summary.innerText(), new RegExp(`${recent.abortions.toLocaleString("en-US")} clinician-provided in 2025`));
        const report = countyReports[state.id];
        const years = report?.years ?? report?.occurrence?.years;
        if (years) {
          await page.locator("path.county").first().waitFor();
          assert.equal(await page.locator("#county-table tbody tr").count(), years[Math.max(...Object.keys(years))].length);
        } else {
          await page.locator(".county-outlines path").first().waitFor();
          assert.match(await summary.innerText(), /County boundaries only/);
        }
      }
      await page.goto(origin + "/?state=PA&basis=occurrence&year=2024#county-panel");
      await page.getByRole("button", { name: "Bucks, 2024: 1,014" }).waitFor();
      assert.equal(await page.locator("#county-table tbody tr").count(), 67);
      assert.match(await page.locator("#county-concentration").innerText(), /Half of the total came from 2 counties/);
      assert.match(await page.locator("#county-concentration-list li").first().innerText(), /Philadelphia\s+12,466 · 38%/);
      await page.getByRole("button", { name: "Bucks", exact: true }).click();
      await page.locator(".municipal-boundary").first().waitFor();
      assert.equal(await page.locator(".county-count-badge.focused text").textContent(), "1,014");
      assert.equal(new URL(page.url()).searchParams.get("county"), "42017");
      await page.reload();
      await page.locator(".municipal-boundary").first().waitFor();
      assert.equal(await page.locator(".county-count-badge.focused text").textContent(), "1,014");
      await page.selectOption("#county-mode", "residence");
      assert.match(await page.locator("#county-detail").innerText(), /Bucks, 2024: 842/);

      await page.goto(origin + "/?state=MN&year=2022#county-panel");
      await page.getByRole("button", { name: "Anoka, 2022: 620" }).waitFor();
      assert.equal(await page.locator("#county-table tbody tr").count(), 87);
      assert.match(await page.getByRole("link", { name: "Source report" }).getAttribute("href"), /2022abrpt-revised\.pdf$/);
      await page.selectOption("#county-year", "2018");
      assert.match(await page.getByRole("link", { name: "Source report" }).getAttribute("href"), /2018abrpt\.pdf$/);

      await page.goto(origin + "/?state=VA&year=2020#county-panel");
      await page.getByRole("button", { name: /^Fairfax County, 2020:/ }).waitFor();
      assert.equal(await page.getByRole("button", { name: /^Fairfax City, 2020:/ }).count(), 1);
      await page.getByRole("button", { name: "Fairfax City", exact: true }).click();
      assert.equal(new URL(page.url()).searchParams.get("county"), "51600");
      await page.goto(origin + "/?state=WI&year=1994#county-panel");
      await page.getByRole("button", { name: "Adams, 1994: 28" }).waitFor();
      assert.equal(await page.locator("#county-table tbody tr").count(), 72);
      assert.match(await page.getByRole("link", { name: "Source report" }).getAttribute("href"), /p45360-98\.pdf$/);
      await page.goto(origin + "/?state=IN&year=1998#county-panel");
      await page.getByRole("button", { name: "Adams, 1998: 14" }).waitFor();
      assert.equal(await page.locator("#county-table tbody tr").count(), 92);
      assert.match(await page.getByRole("link", { name: "Source report" }).getAttribute("href"), /itp_tbl_14\.html$/);
    });
  });
}

test("county data failure leaves the statewide view and U.S. chart usable", async () => {
  await checkMap({ width: 1280, height: 850 }, async page => {
    await page.goto(origin + "/?state=CA");
    await page.locator("#county-panel").getByText(/County data could not load/).waitFor();
    assert.match(await page.locator("#state-total").innerText(), /California 152,400/);
    assert.equal(await page.locator("#us-chart svg").count(), 1);
    await page.selectOption("#state", "42");
    assert.match(await page.locator("#state-total").innerText(), /Pennsylvania/);
  }, { failCounties: true });
});

test("international history lists continent coverage and preserves the selected reporting series", async () => {
  await checkMap({ width: 1280, height: 850 }, async page => {
    await page.goto(origin + "/?history=NZL&historySource=new-zealand#international-history");
    const controls = page.locator("#international-controls");
    await controls.waitFor();
    assert.equal(await page.locator("#international-coverage tbody tr").count(), 6);
    assert.equal(await page.locator("#history-continent").inputValue(), "Oceania");
    assert.equal(await page.locator("#history-geography").inputValue(), "NZL");
    assert.equal(await page.locator("#history-series").inputValue(), "new-zealand");
    const observations = page.locator("#international-observations tbody tr");
    assert.equal(await observations.count(), 45);
    assert.match(await observations.first().innerText(), /2024\s+17,785/);
    assert.match(await observations.filter({ hasText: "Revised Ministry total" }).innerText(), /2019\s+12,948/);
    await page.selectOption("#history-continent", "Africa");
    await page.selectOption("#history-geography", "ZAF");
    await page.selectOption("#history-series", "south-africa");
    assert.match(await observations.first().innerText(), /2025\s+140,737.*Financial year 2024\/25/);
    await page.reload();
    await controls.waitFor();
    assert.equal(await page.locator("#history-series").inputValue(), "south-africa");
    assert.equal(await observations.count(), 6);
  });
});

test("evidence markers open sourced records and persist on the world map", async () => {
  await checkMap({ width: 1280, height: 850 }, async page => {
    await page.goto(origin);
    const toggle = page.getByLabel("Show evidence markers");
    const markers = page.locator("#evidence-markers a");
    const nsw = page.getByRole("link", { name: /^New South Wales, Australia, 2009/ });
    await toggle.check();
    assert.equal(await markers.count(), evidenceRecords.length);
    assert.equal(new URL(page.url()).searchParams.get("evidence"), "1");
    await nsw.click();
    await page.waitForURL(url => url.hash === "#evidence-new-south-wales-2009");
    const entry = page.locator("#evidence-new-south-wales-2009").locator("..");
    assert.match(await entry.innerText(), /energy recovery or sales/);
    assert.match(await entry.getByRole("link", { name: /^New South Wales/ }).getAttribute("href"), /parliament\.nsw\.gov\.au/);
    await page.reload();
    await nsw.waitFor();
    assert.equal(await toggle.isChecked(), true);
    await page.locator("#country").selectOption("840");
    assert.equal(await toggle.isVisible(), false);
    assert.equal(await page.locator("#evidence-markers").isVisible(), false);
    await page.getByRole("button", { name: "World", exact: true }).click();
    await nsw.waitFor();
    await toggle.uncheck();
    assert.equal(await nsw.isVisible(), false);
    const payments = page.getByRole("region", { name: "Public records of payments and charges" });
    await payments.getByText(/\$7,470 across nine invoices/).waitFor();
    assert.match(await payments.getByText(/\$15,900 original obligation/).locator("../..").innerText(),
      /Disbursements require invoice and payment records/);
    assert.equal(await page.getByRole("heading", { name: "Further reading and investigations" }).count(), 1);
  });
});
