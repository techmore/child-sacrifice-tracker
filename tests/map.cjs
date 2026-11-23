const assert = require("node:assert/strict");
const { test } = require("node:test");
const path = require("node:path");
const { chromium } = require("playwright");
const states = require("../docs/data/states.json");
const history = require("../docs/data/us-history.json");
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
      await page.locator("#open-us").click();
      const california = page.locator(".state").filter({ visible: true });
      const index = await california.evaluateAll(nodes => nodes.findIndex(node => node.__data__.id === "06"));
      await california.nth(index).click();
      const summary = page.locator("#state-total");
      for (const state of states) {
        await page.selectOption("#state", state.id);
        const recent = history.recent.states[state.abbr].at(-1);
        assert.equal(await summary.locator("strong").innerText(), `${state.name} ${state.abortions.toLocaleString("en-US")}`);
        assert.match(await summary.innerText(), new RegExp(`${recent.abortions.toLocaleString("en-US")} clinician-provided in 2025`));
      }
      await page.goto(origin + "/?state=PA&basis=occurrence&year=2024#county-panel");
      await page.getByRole("button", { name: "Bucks, 2024: 1,014" }).waitFor();
      assert.equal(await page.locator("#county-table tbody tr").count(), 67);
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
