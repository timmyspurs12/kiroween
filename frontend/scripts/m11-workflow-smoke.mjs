// M11 DOM/API workflow regression. This executes the production bundle in jsdom,
// talks to the live local API, and is not a real-browser rendering test.
import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import { JSDOM, VirtualConsole } from "jsdom";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const base = process.env.NECROSPEC_BASE_URL || "http://127.0.0.1:8747";
const html = await readFile(path.join(root, "app/web_dist/index.html"), "utf8");
const bundleRel = html.match(/src="\.\/(assets\/[^\"]+\.js)"/)?.[1];
if (!bundleRel) throw new Error("production bundle reference missing from web_dist/index.html");
const bundle = path.join(root, "app/web_dist", bundleRel);
const errors = [];
const requests = [];
const projectBodies = [];
const vc = new VirtualConsole();
vc.on("error", (...xs) => errors.push(xs.join(" ")));
vc.on("warn", (...xs) => errors.push(xs.join(" ")));
vc.on("jsdomError", (e) => errors.push(e.message));
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: base + "/", pretendToBeVisual: true, runScripts: "outside-only", virtualConsole: vc,
});
const { window } = dom;
const nativeFetch = globalThis.fetch;
window.fetch = async (input, init) => {
  const url = typeof input === "string" && input.startsWith("/") ? base + input : String(input);
  if (url.endsWith("/api/project") && init?.body) {
    try { projectBodies.push(JSON.parse(String(init.body))); } catch {}
  }
  const response = await nativeFetch(url, init);
  requests.push({ url, status: response.status });
  return response;
};
window.scrollTo = () => {};
window.HTMLElement.prototype.scrollIntoView = function () {};
globalThis.window = window;
globalThis.document = window.document;
for (const key of ["navigator", "HTMLElement", "HTMLTextAreaElement", "Element", "Node",
  "CustomEvent", "KeyboardEvent", "MouseEvent", "InputEvent", "MutationObserver",
  "SVGElement", "HTMLInputElement", "HTMLButtonElement", "File", "FileList", "FileReader"]) {
  try { Object.defineProperty(globalThis, key, { value: window[key], configurable: true }); } catch {}
}
globalThis.getComputedStyle = window.getComputedStyle.bind(window);
globalThis.requestAnimationFrame = window.requestAnimationFrame.bind(window);
globalThis.cancelAnimationFrame = window.cancelAnimationFrame.bind(window);
globalThis.localStorage = window.localStorage;
globalThis.location = window.location;
globalThis.history = window.history;
globalThis.fetch = window.fetch;
globalThis.ResizeObserver = window.ResizeObserver || class { observe() {} disconnect() {} unobserve() {} };

const checks = [];
const check = (label, ok, evidence = "") => {
  checks.push({ label, ok: Boolean(ok) });
  console.log(`${ok ? "PASS" : "FAIL"} ${label}${ok ? "" : ` — ${evidence}`}`);
};
const q = (selector) => window.document.querySelector(selector);
const buttons = () => [...window.document.querySelectorAll("button")];
const clickButton = (matcher) => {
  const button = buttons().find((b) => matcher(b.textContent?.trim() || ""));
  if (!button) throw new Error(`button not found: ${String(matcher)}`);
  button.click();
  return button;
};
const waitFor = async (predicate, label, timeout = 8000) => {
  const start = Date.now();
  while (!predicate()) {
    if (Date.now() - start > timeout) throw new Error(`timeout waiting for ${label}`);
    await new Promise((resolve) => setTimeout(resolve, 40));
  }
};
const openProject = async () => {
  clickButton((t) => t === "Project");
  await waitFor(() => q(".pj-pane"), "project workspace");
};
const openReadiness = async () => {
  clickButton((t) => t.startsWith("Migration readiness"));
  await waitFor(() => q(".migration-readiness-head"), "readiness view");
};
const projectStateClass = () => q(".migration-readiness-head .migration-state")?.className || "";
const loadCase = async (label, projectName) => {
  const summary = q("details.pj-demo-menu > summary");
  if (!summary) throw new Error("illustrative case selector missing");
  summary.click();
  clickButton((t) => t.startsWith(label));
  await waitFor(() => q(".pj-demo-notice") &&
    (q(".pj-summary")?.textContent || "").includes(projectName) &&
    !buttons().find((b) => b.textContent?.includes("Load example project"))?.disabled, `${label} case result`);
  await openReadiness();
};

try {
  const health = await nativeFetch(base + "/api/health");
  if (!health.ok) throw new Error(`API is not healthy: ${health.status}`);
  await import(pathToFileURL(bundle).href);
  await waitFor(() => q(".header"), "application header");
  check("App boots and shows product positioning", Boolean(q(".header")) &&
    (q(".wordmark-sub")?.textContent || "").includes("Modernise with evidence"));
  await openProject();
  clickButton((t) => t === "Load example project");
  await waitFor(() => (window.document.body.textContent || "").includes("sample-project") &&
    q(".pj-files .sample-item"), "flagship project analysis");
  check("Flagship sample loads through the project API", (window.document.body.textContent || "").includes("12 programs"));

  const dependencySection = [...window.document.querySelectorAll(".pj-detail .ov-section")]
    .find((section) => section.querySelector("h3")?.textContent === "DEPENDENCIES");
  const dependencyRow = [...(dependencySection?.querySelectorAll(".lg-ref-row") || [])]
    .find((row) => row.textContent?.includes('CALL "GLUPDATE" USING WS-TOTAL'));
  const dependencySourceLink = dependencyRow?.querySelector(".ov-file-link .ov-source-link");
  check("M9 CALL dependency exposes its recorded source line", Boolean(dependencySourceLink) &&
    dependencySourceLink.textContent?.trim() === "open L16");
  dependencySourceLink?.click();
  await waitFor(() => q(".code-input") &&
    (q(".header-file")?.textContent || "").includes("AUDTOTAL.cbl"), "M9 dependency source handoff");
  await new Promise((resolve) => setTimeout(resolve, 100));
  const dependencyEditor = q(".code-input");
  const dependencyLine = dependencyEditor?.value.slice(0, dependencyEditor.selectionStart).split("\n").length;
  check("M9 dependency source action opens AUDTOTAL.cbl at line 16", dependencyLine === 16,
    `selected line=${dependencyLine}`);
  clickButton((t) => t === "Project");
  await waitFor(() => q(".pj-pane")?.parentElement?.style.display === "contents", "return from M9 dependency");

  await openReadiness();
  check("Real sample's actual investigation-only distribution remains visible",
    (window.document.body.textContent || "").includes("Investigation required12"));

  const riskRow = [...window.document.querySelectorAll(".readiness-evidence")]
    .find((row) => row.textContent?.includes("SEM_PRECISION_LOSS") &&
      row.querySelector("button.ov-source-link"));
  const sourceLink = riskRow?.querySelector("button.ov-source-link");
  check("Source-backed work-package evidence offers an exact-line action",
    Boolean(sourceLink) && sourceLink.textContent?.trim() === "open L11");
  sourceLink?.click();
  await waitFor(() => q(".code-input") &&
    (q(".header-file")?.textContent || "").includes("GLUPDATE.cbl"), "source handoff");
  await new Promise((resolve) => setTimeout(resolve, 100));
  const editor = q(".code-input");
  const selectedLine = editor?.value.slice(0, editor.selectionStart).split("\n").length;
  check("Source handoff opens the cited file at line 11", selectedLine === 11,
    `selected line=${selectedLine}`);
  check("Project analysis remains mounted during source review", Boolean(q(".migration-readiness-head")));
  clickButton((t) => t === "Project");
  await waitFor(() => q(".pj-pane")?.parentElement?.style.display === "contents", "return to project");
  check("Returning from source preserves the analyzed readiness worklist",
    (window.document.body.textContent || "").includes("MIGRATION WORK PACKAGES"));

  await loadCase("Ready ·", "supported planning case");
  check("Synthetic ready case uses the real M10 ready state",
    projectStateClass().includes("ready_for_planning"));
  await loadCase("Investigate ·", "source risk case");
  check("Existing GLUPDATE risk source uses the real investigation state and evidence",
    projectStateClass().includes("investigation_required") &&
      (window.document.body.textContent || "").includes("SEM_PRECISION_LOSS"));
  await loadCase("Not assessable ·", "no-source input gap");
  check("Controlled no-source case is explicitly project-level not assessable",
    projectStateClass().includes("not_assessable") &&
      (window.document.body.textContent || "").includes("src/UNREADABLE.cbl"));
  check("Controlled cases are labelled, and source gap stays visible",
    (q(".pj-demo-notice")?.textContent || "").includes("not customer code") &&
      (window.document.body.textContent || "").includes("SKIPPED"));

  const uploadInput = window.document.querySelector('.pj-pane input[type="file"][multiple]');
  const brokenFile = new window.File([""], "BROKEN.cbl", { type: "text/plain" });
  Object.defineProperty(brokenFile, "webkitRelativePath", { value: "read-error-case/src/BROKEN.cbl" });
  const OriginalFileReader = window.FileReader;
  class FailingFileReader {
    constructor() { this.error = new Error("controlled browser read failure"); }
    readAsText() { setTimeout(() => this.onerror?.(), 0); }
  }
  window.FileReader = FailingFileReader;
  Object.defineProperty(globalThis, "FileReader", { value: FailingFileReader, configurable: true, writable: true });
  Object.defineProperty(uploadInput, "files", { configurable: true, value: [brokenFile] });
  uploadInput.dispatchEvent(new window.Event("change", { bubbles: true }));
  await waitFor(() => (q(".pj-summary")?.textContent || "").includes("read-error-case") &&
    (window.document.body.textContent || "").includes("BROKEN.cbl"), "FileReader error preserved");
  const uploadRequest = [...projectBodies].reverse().find((body) => body.name === "read-error-case");
  check("Directory FileReader failure keeps its relative path and reason in the API request",
    uploadRequest?.files?.[0]?.path === "src/BROKEN.cbl" &&
      uploadRequest.files[0].error === "controlled browser read failure");
  window.FileReader = OriginalFileReader;
  globalThis.FileReader = OriginalFileReader;

  check("All API requests succeeded", requests.length > 0 && requests.every((r) => r.status === 200),
    JSON.stringify(requests));
  check("No console or jsdom errors", errors.length === 0, errors.join(" | "));
} finally {
  dom.window.close();
}

const failed = checks.filter((x) => !x.ok);
console.log(`\nM11 workflow DOM/API checks: ${checks.length - failed.length}/${checks.length} passed`);
if (failed.length) process.exitCode = 1;
