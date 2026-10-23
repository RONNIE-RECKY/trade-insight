// Headless smoke drive of the PIP HIVE web app: home page, admin login,
// Charts and Signals. Screenshots land in the directory given as argv[2].
// Usage: NODE_PATH_PW=$(npm root -g) node drive.mjs <out-dir> [base-url]
import { createRequire } from "module";
const require = createRequire((process.env.NODE_PATH_PW ?? ".") + "/");
const { chromium } = require("playwright");

const out = process.argv[2] ?? ".";
const base = process.argv[3] ?? "http://localhost:3000";
const email = process.env.ADMIN_EMAIL || "admin@tradeinsight.app";
const password = process.env.ADMIN_PASSWORD || "Admin1234!";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));

await page.goto(`${base}/`);
await page.waitForTimeout(2000);
await page.screenshot({ path: `${out}/home.png` });

await page.goto(`${base}/login`);
await page.waitForTimeout(1500);
await page.fill("input[type=email]", email);
await page.fill("input[type=password]", password);
await page.click("button[type=submit]");
await page.waitForTimeout(4000);
console.log("after login:", page.url()); // expect /account

await page.goto(`${base}/charts`);
await page.waitForTimeout(6000);
await page.screenshot({ path: `${out}/charts.png` });

await page.goto(`${base}/signals`);
await page.waitForTimeout(4000);
await page.screenshot({ path: `${out}/signals.png` });

console.log("page errors:", errors);
await browser.close();
process.exit(errors.length ? 1 : 0);
