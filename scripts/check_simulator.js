// Verify the browser simulator against the Python model and take the screenshot used in the report.
//   npm install playwright   (once)      node scripts/check_simulator.js
// Writes results/simulators/verification_js.json and results/simulators/sim_html.png
const path = require("path"), fs = require("fs");
const { chromium } = require("playwright");
(async () => {
  const root = path.join(__dirname, "..");
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1400, height: 1420 }, deviceScaleFactor: 1.5 });
  await p.emulateMedia({ reducedMotion: "reduce" });
  await p.goto("file://" + path.join(root, "simulator", "rear-end-sim.html"));
  await p.waitForTimeout(1200);
  const r = await p.evaluate(() => {
    const s = window.__sim, v0 = 96.48 / 3.6, rut = s.rampUp(v0, 0.92, 6.55, 12.5);
    const rt = s.rtModel(rut, 0.63, 0.47, 0.4, null), T = s.traj(v0, 0.92, 6.55, 12.5, rt, 7.5, 20);
    const z = s.invN(0.1), A = s.traj(v0, 0.92, 6.55, 12.5, 0.55, 8, 30);
    return { rut, rt, t_contact: T.contact.t, vc_kph: T.contact.vc * 3.6, p_mais3: s.injury(T.contact.vc, 1.55),
             rt10: s.rtModel(rut, 0.63, 0.47, 0.4, z), rt90: s.rtModel(rut, 0.63, 0.47, 0.4, -z), ads_min_gap: A.minGap };
  });
  await p.click("#runMC");
  await p.waitForFunction(() => document.getElementById("mcRef").textContent !== "–", null, { timeout: 60000 });
  r.mc = await p.evaluate(() => ({ p_coll: +mcRef.textContent, band: mcRefCI.textContent.replace("5th–95th: ", ""),
                                   flip: +mcFlip.textContent, ads: +mcAds.textContent }));
  await p.$eval("#scrub", e => { e.value = 640; e.dispatchEvent(new Event("input")); });
  await p.waitForTimeout(300);
  const out = path.join(root, "results", "simulators");
  fs.mkdirSync(out, { recursive: true });
  await p.screenshot({ path: path.join(out, "sim_html.png") });
  fs.writeFileSync(path.join(out, "verification_js.json"), JSON.stringify(r, null, 1));
  console.log(r);
  await b.close();
})();
