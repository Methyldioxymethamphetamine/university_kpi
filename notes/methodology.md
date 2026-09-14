methodology.md

# Methodology

**Scope.** How the work in `findings/` and `notes/` was actually produced — session 1 (source investigation, 13 Sep 2026) and session 2 (the six dictionary/reconciliation tasks, same day). This is not a results document. It exists so that any claim in the other files can be traced to the command that produced it, and so that someone with no context on this project can re-run it.

**How to read the evidence markers.** Every substantive claim in the other documents falls into one of three classes, and they are not equally strong:

| **MarkerMeaningHow to challenge it** |                                                                   |                                            |
| ------------------------------------ | ----------------------------------------------------------------- | ------------------------------------------ |
| **[M] Measured**                     | Read directly out of a file or page by inspection                 | Open the same file at the same coordinates |
| **[C] Computed**                     | Produced by a script over a whole population                      | Re-run the script; it is in `scripts/`     |
| **[R] Reasoned**                     | A judgment call. Evidence constrains it but does not determine it | Read the justification in §7 and disagree  |

Anything marked **[R]** is where a different analyst could reasonably land somewhere else. Those are collected in §7 with the reasoning and what would change my mind.

**How the work actually went.** Not a plan executed — a sequence of dead ends that each redirected the next step. Dashed arrows are failures.

ROBOTS\_DISALLOWED403 from egress proxyeven Wikipedia blockedoutput fluent but scrambled'Rs.) Rs.)' · duplicatedheadersyesSandip unranked\:no PDF on the portalcell(value=None) is a no-op;caught only by read-back9 mismatches — 4 werethe parser's own bugsjoin builds, but 93% ofrouting is 'the universitywebsite'Are NIRF PDFs scans?(the question that gatedeverything)WebFetch the IITB NIRFpagecurl from the containerParse PDFs in the laptopbrowserpdf.js loaded from CDNStructural diagnosticpages · chars · images ·fontsANSWERED: born-digital,0 images, no OCR neededRebuild lines: group bytransform 5Suspicious enoughto check?Dump raw geometry+ page.rotate + text angles/Rotate 90 found\:axes are swappedGroup by transform 4insteadClean tables recoveredRepeat diagnostic across2020-2026, 2 institutionsRead page 1 line by lineto sanity-check the fixSpot 3750000 vs'Three Lakh Seventy FiveThousand'Verify against raw text runs— not a join artifactAcquisition surfaceURL pattern: 537 ranked IDsWordPress /wp-json mediaAPI→ 28 files, 4 years ofsubmissionsSESSION 2client documents nowavailableVerify Excel defectsBuild dictionary v2Assign via .value insteadMap 229 codes to NIRFfieldsChecksum studyScale absorption + idiomabstain+ self-test → 11 realReconcile parameters docxShip the join as anappendix;lead with verified URLpatterns

---

## 1. The environment, because it shaped everything

This mattered more than expected, so it goes first.

The work ran in two places with three different network positions:

```
  ┌─────────────────────────────┐         ┌──────────────────────────────┐
  │  CLOUD CONTAINER            │         │  USER'S LAPTOP               │
  │  Linux 6.18, Python 3.11.15 │         │  Windows, Claude desktop app │
  │                             │         │                              │
  │  • openpyxl, pandas,        │         │  • browser pane w/ full       │
  │    python-docx, pyyaml      │         │    consumer internet         │
  │  • NO general web access    │         │  • E:\kpi mounted read/write │
  │    (egress allowlist)       │         │  • NO shell available         │
  └──────────┬──────────────────┘         └──────────────┬───────────────┘
             │                                           │
             │   device_stage_files  (laptop → container)│
             │   device_commit_files (container → laptop)│
             └───────────────────────────────────────────┘

  WebFetch / WebSearch: routed through Anthropic infrastructure, a third
  network position again — reaches some hosts the other two cannot.
```

**[M]** The cloud container's egress allowlist blocks essentially all general web traffic. Tested directly:

bash

```bash
for h in www.nirfindia.org nirfindia.org www.sandipuniversity.edu.in sandipfoundation.org \
         web.mit.edu ir.mit.edu www.iitb.ac.in en.wikipedia.org; do
  code=$(curl -sS -o /dev/null -w "%{http_code}" -m 20 -A "Mozilla/5.0" "https://$h/" 2>&1 | tail -1)
  echo "$h -> $code"
done
```

Every host returned `000`, including Wikipedia. The proxy's own status endpoint confirmed the cause rather than a transport fault:

bash

```bash
curl -sS "$HTTPS_PROXY/__agentproxy/status"
# "recentRelayFailures": [{ "kind": "connect_rejected",
#   "detail": "gateway answered 403 to CONNECT (policy denial or upstream failure)",
#   "host": "www.iitb.ac.in:443" }, ...]
```

**Consequence:** no PDF could be downloaded into the container where the PDF libraries live. That single constraint dictated the entire acquisition method described in §2.3 — parsing PDFs inside the laptop's browser and returning only extracted text — and it is why there are no `.pdf` files in `E:\kpi`. If you reproduce this on an unrestricted machine, use PyMuPDF or pdfplumber locally instead; the *rules* in §9 transfer unchanged, only the transport differs.

**Reproducibility note.** No files were written to the laptop except into `E:\kpi`. The client's three source documents were staged read-only into the container at `/mnt/user-data/uploads/kpi/` and never written back.

---

## 2. Session 1 — source investigation

### 2.1 What I was trying to find out

One question dominated: **are the NIRF submission PDFs scans?** If they were, extraction meant OCR, OCR means 70–90% character accuracy on numeric tables, and the project's whole evidence-chain premise would need rethinking. Everything else was secondary.

### 2.2 First approach: WebFetch. Failed.

**Attempt.**

```
WebFetch(url="https://www.iitb.ac.in/en/about-iit-bombay/nirf",
         prompt="List every PDF link on this page with its year, category and full URL.")
```

**Result.** `{"error_type":"ROBOTS_DISALLOWED","message":"Failed to fetch or parse robots.txt"}` — on the HTML page, and again on a PDF URL found via WebSearch.

**How I handled it.** The error text says robots.txt could not be *fetched or parsed*, which is an infrastructure failure, not a stated disallow. Rather than assume either way, I read the file through a channel that could reach it (the laptop browser) and checked what it actually says:

js

```js
const r = await fetch('https://www.iitb.ac.in/robots.txt');
({status: r.status, body: (await r.text()).slice(0,1500)})
```

**[M]** It is a stock Drupal robots.txt. It disallows `/core/`, `/profiles/`, `/admin/`, `/search/` and a list of README files. It says nothing about `/sites/default/files/`, which is where the PDFs live. So the block was tooling, not policy — but by then the container egress test above had already ruled out downloading anyway, so the point was moot.

**Lesson recorded:** a fail-closed error from a fetching tool is not evidence that content is restricted. Verify what the restriction actually is before either respecting or routing around it.

### 2.3 Second approach: parse PDFs inside the laptop's browser

**Reasoning.** The laptop browser reaches the sites. The container has the libraries but no network. There is no shell on the laptop. So: run a PDF parser *in the browser*, and return only the extracted text through the tool channel.

**What I did.** Loaded pdf.js from a CDN into a page already on the target origin (so the PDF fetch is same-origin and CORS is not an issue), then parsed from an ArrayBuffer:

js

```js
if (typeof pdfjsLib === 'undefined') {
  await new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
    s.onload = res; s.onerror = () => rej(new Error('blocked'));
    document.head.appendChild(s);
  });
  pdfjsLib.GlobalWorkerOptions.workerSrc =
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
}
const buf = await fetch(url).then(r => r.arrayBuffer());
const doc = await pdfjsLib.getDocument({data: buf}).promise;
```

**Constraint this imposes.** Every browser call is stateless in practice — a navigation, a page error, or the user closing the pane wipes `window`. Three times during the session a helper stored on `window` vanished mid-sequence. The working pattern became: **make each call self-contained**, re-loading pdf.js with the `typeof` guard at the top rather than assuming it is present. Every JS block quoted below does that.

### 2.4 The structural diagnostic

**What I wanted:** page count, whether a text layer exists, how much text, how many images, and the font situation — enough to classify the document without reading it.

js

```js
let chars = 0, imgs = 0, pages = [];
const fonts = new Set();
for (let i = 1; i <= doc.numPages; i++) {
  const p  = await doc.getPage(i);
  const tc = await p.getTextContent();
  const c  = tc.items.reduce((a, it) => a + it.str.length, 0);
  tc.items.forEach(it => it.fontName && fonts.add(it.fontName));
  const ops = await p.getOperatorList();
  const im  = ops.fnArray.filter(f =>
        f === pdfjsLib.OPS.paintImageXObject ||
        f === pdfjsLib.OPS.paintJpegXObject  ||
        f === pdfjsLib.OPS.paintInlineImageXObject).length;
  chars += c; imgs += im;
  pages.push({p: i, chars: c, items: tc.items.length, imgs: im});
}
```

**[M] Result for IIT Bombay 2025 Overall** (`nirfpdfcdn/2025/pdf/Overall/IR-O-U-0306.pdf`):

```
numPages 4 · totalChars 9741 · totalImages 0 · fonts ["g_d0_f1","g_d0_f3"] · elapsed 572 ms
per page: 2417/0  2154/0  3378/0  1792/0     (chars / images)
```

Zero images across four pages with \~9,700 characters of real text settles the primary question: **not a scan, no OCR needed.** The 572 ms is wall-clock including the network fetch, measured with `performance.now()` around the whole block.

The per-page chars/images pair turned out to be the more useful output. It became the mixed-mode detector in §2.9.

### 2.5 The `/Rotate 90` discovery — the most important failure in the project

This is the one worth reading closely, because it nearly passed.

**The naive reconstruction.** Having confirmed a text layer, the obvious next step is to rebuild lines. PDF text items carry a 6-element transform; `transform[4]` is conventionally x and `transform[5]` is y. So: group by y, sort by x.

js

```js
const rows = {};
tc.items.forEach(it => {
  const y = Math.round(it.transform[5]);
  (rows[Math.round(y/3)] = rows[Math.round(y/3)] || []).push({x: it.transform[4], s: it.str});
});
// emit rows top-to-bottom, each sorted left-to-right
```

**[M] What came back** (IIT Bombay 2025 Overall, page 1, verbatim excerpt):

```
tuition fee
who are not
receiving full Studies Studies
No. of students reimbursement
1430 78 410
No. of students No. of students
2018-19 selected for Higher selected for Higher
83 154 259
Bodies
tuition fee
- - -
receiving full
No. of students reimbursement
from the Private 419 61 0
Rs.) Rs.)
```

**Why this is dangerous rather than merely broken.** It does not throw. It does not return empty. It returns fluent English fragments and correctly-formatted numbers. `1430 78 410` is a real triple of real values from the document. `83 154 259` is a real row. Every number present is a number that genuinely appears in the file. What is destroyed is only the *association* between labels and values — and association is invisible in the output.

An extractor built on this would find `2668`, `564`, `1325` and confidently label them whatever the nearest surviving text happened to be.

**What made me suspicious.** Three specific things, in order:

1. `Rs.) Rs.)` — a closing bracket fragment, twice, on one line. Column headers do not repeat like that unless two independent things are being merged.
2. `No. of students No. of students` and `selected for Higher selected for Higher` — the same header appearing twice on one line, and split from its own value.
3. `- - -` on its own line, with nothing to attach it to.

Any single one of those reads as ordinary PDF messiness. Together they say: *two parallel structures are being collapsed into one*.

**Diagnosis.** I dumped the raw items with geometry rather than guessing:

js

```js
const p = await doc.getPage(1);
const vp = p.getViewport({scale: 1});
const tc = await p.getTextContent();
({ view: [vp.width, vp.height],
   rotate: p.rotate,
   textAngles: [...new Set(tc.items.map(i => {
       const t = i.transform; return Math.round(Math.atan2(t[1], t[0]) * 180 / Math.PI);
   }))],
   sample: tc.items.slice(0, 12).map(i => ({
       s: i.str, x: Math.round(i.transform[4]), y: Math.round(i.transform[5])
   })) })
```

**[M] Output — the answer is in three lines:**

```
view        [842, 595]        ← landscape
rotate      90                ← page-level rotation
textAngles  [90]              ← EVERY text item has a 90° text matrix

sample:
  {s: "Data Submitted by Institution for India Rankings '2025'", x: 57, y: 10}
  {s: "Institute Name: Indian Institute of Technology Bombay ...", x: 69, y: 10}
  {s: "Sanctioned (Approved) Intake",                             x: 95, y: 10}
```

Those three strings are three consecutive *lines* of the document. They share `y = 10` and differ in `x` (57, 69, 95). **The axes are swapped.** Under `/Rotate 90`, `transform[4]` is the page's vertical axis as displayed and `transform[5]` is the horizontal one. Grouping by `transform[5]` therefore groups *columns* together and calls them rows — which is exactly why two side-by-side tables merged.

**The fix** — group on the other axis, sort within group by the first:

js

```js
const rot  = p.rotate === 90;
const rows = {};
tc.items.forEach(it => {
  if (!it.str.trim()) return;
  const a = rot ? it.transform[4] : -it.transform[5];   // down-the-page
  const b = rot ? it.transform[5] :  it.transform[4];   // across-the-page
  (rows[Math.round(a/4)] = rows[Math.round(a/4)] || []).push({b, s: it.str});
});
Object.keys(rows).map(Number).sort((x,y) => x-y).forEach(k => {
  console.log(rows[k].sort((x,y) => x.b - y.b).map(o => o.s).join(' | '));
});
```

**[M] Same page, same file, after:**

```
Data Submitted by Institution for India Rankings '2025'
Institute Name: Indian Institute of Technology Bombay [IR-O-U-0306]
Sanctioned (Approved) Intake
Academic Year | 2023-24 | 2022-23 | 2021-22 | 2020-21 | 2019-20 | 2018-19
UG [4 Years Program(s)] | 1161 | 1059 | 1039 | 1030 | - | -
UG [5 Years Program(s)] | 80 | 182 | 202 | 211 | 178 | -
PG [2 Year Program(s)] | 1558 | 1543 | - | - | - | -
```

Side by side:

```
   BEFORE (grouped on transform[5])        AFTER (grouped on transform[4])
   ─────────────────────────────────       ───────────────────────────────────────
   1430 78 410                             Academic Year | 2023-24 | 2022-23 | ...
   No. of students No. of students         UG [4 Years Program(s)] | 1161 | 1059 | ...
   2018-19 selected for Higher             UG [5 Years Program(s)] | 80 | 182 | ...
       selected for Higher                 PG [2 Year Program(s)] | 1558 | 1543 | ...
   83 154 259
   Rs.) Rs.)                               labels attached to values
   - - -                                   columns in document order
                                           dashes in their own cells
   no error raised                         no error raised
```

**The honest counterfactual.** Had page 1 contained one table instead of two side by side, the naive output would have been *plausible but subtly wrong* rather than obviously garbled, and I do not think I would have caught it from the text alone. The tell was the duplication caused by two tables merging. **On a single-table page this defect is close to undetectable by reading the output.** The only reliable check is to verify a known value end to end, which is why that is a rule in `CLAUDE.md` rather than advice.

**Root cause.** Not a pdf.js bug. pdf.js reports geometry in unrotated PDF user space and exposes `page.rotate` and the text matrix so the caller can handle it. The defect was mine: assuming `transform[4]`/`transform[5]` are screen x/y. Any library that hands you raw coordinates has the same trap. A library that returns pre-formatted text may or may not handle it — which is why `CLAUDE.md` says to *test* rather than to prefer a particular library.

### 2.6 Establishing that the format is stable

**Question:** is this one document's quirk, or the form's?

Ran the §2.4 diagnostic across years and categories:

**[C] Result:**

| **DocumentPagesCharsImagesRotation** |              |                          |   |    |
| ------------------------------------ | ------------ | ------------------------ | - | -- |
| IITB 2025 Overall                    | 4            | 9,741                    | 0 | 90 |
| IITB 2024 Overall                    | 4            | 8,965                    | 0 | 90 |
| IITB 2023 Overall                    | 4            | 8,382                    | 0 | 90 |
| IITB 2020 Overall                    | 3            | 7,043                    | 0 | 90 |
| IITB 2025 Engineering                | 3            | 7,807                    | 0 | 90 |
| Sandip 2026 / 2025 / 2024 Overall    | 10 / 13 / 10 | 20,292 / 25,738 / 20,684 | 0 | 90 |

**Sampling disclosure.** This is 8 documents spanning 2020–2026, two institutions, two institution types (University and College) and two categories. It is **not** a random sample of the 537 ranked institutions. It is sufficient to establish that the rotation and the born-digital property are properties of the *form generator*, not of one submitter — but a systematic rotation check across a larger sample is listed in §8 as outstanding.

### 2.7 Mapping the acquisition surface

Having established the documents are parseable, the question became *where do they come from at scale*.

**Finding the index.** The IIT Bombay NIRF page was not at the URL search suggested. I used the site's own Drupal search through a same-origin fetch rather than guessing paths:

js

```js
const r = await fetch('/en/search/node?keys=NIRF').then(r => r.text());
const d = new DOMParser().parseFromString(r, 'text/html');
[...d.querySelectorAll('a')]
  .map(a => ({t: a.textContent.trim(), h: a.getAttribute('href')}))
  .filter(x => /nirf/i.test(x.t + x.h));
// → /national-institutional-ranking-framework-nirf
```

Then read the table structurally rather than scraping visible text:

js

```js
const rows = [...d.querySelectorAll('table tr')].map(tr =>
  [...tr.children].map(td => {
    const a = td.querySelector('a');
    return a ? td.textContent.trim() + ' || ' + a.href : td.textContent.trim();
  }));
```

**[M]** 9 years (2018–2026) × up to 5 categories = 32 submission PDFs in one table.

**The URL pattern.** WebSearch surfaced `nirfindia.org/nirfpdfcdn/2020/pdf/Overall/IR-O-U-0306.pdf`. Substituting the year confirmed the pattern holds for 2023, 2024 and 2025. **[M]**

```
https://www.nirfindia.org/nirfpdfcdn/{year}/pdf/{Category}/{InstitutionID}.pdf
                                                            IR-O-U-0306  (Overall, University)
                                                            IR-O-C-41520 (Overall, College)
```

**Scale.** Counted rather than estimated:

js

```js
for (const p of ['Overall','Engineering','University','Management','College','Pharmacy']) {
  const h = await fetch(`/Rankings/2025/${p}Ranking.html`).then(r => r.text());
  const d = new DOMParser().parseFromString(h, 'text/html');
  const as = [...d.querySelectorAll('a[href*=".pdf"]')];
  as.forEach(a => { const m = a.getAttribute('href').match(/IR-[A-Z]-[A-Z]-\d+/); if (m) ids.add(m[0]); });
}
```

**[C]** 601 PDF links, 537 unique institution IDs, across the six top-100 lists.

**A negative result that mattered.** Sandip appears in the *participating institutions* lists (`{Category}RankingALL.html`) for Overall, Engineering, Management and Pharmacy — but those pages contain **zero** PDF links. **[C]** NIRF publishes submissions only for *ranked* institutions. That looked like a dead end for the client's own institution.

**The recovery — CMS API instead of crawling.** Sandip's site is WordPress. Instead of crawling it, I queried its REST media endpoint:

js

```js
await fetch('/wp-json/wp/v2/media?per_page=100&search=nirf&_fields=source_url,title')
      .then(r => r.json());
```

**[M]** 28 NIRF-related files, including four years of full submissions — none of them linked from any navigation page I had seen. The institution publishes its own copy even though NIRF does not.

This is the single highest-leverage technique found in the whole investigation and it is generalisable: **before writing a crawler for a site, test whether its CMS exposes an index.**

### 2.8 The published-vs-institution-copy asymmetry

**[M]** Sandip's own 2025 Overall copy is 13 pages / 25,738 chars; IIT Bombay's NIRF-portal copy is 4 pages / 9,741 chars. Reading both showed why:

| **IITB (portal copy)Sandip (own copy)** |                   |                                     |
| --------------------------------------- | ----------------- | ----------------------------------- |
| IPR / patents block                     | absent            | present                             |
| NAAC accreditation block                | absent            | present (CGPA 3.11)                 |
| PG medical block                        | absent            | present                             |
| Faculty information                     | one number: `833` | 190-row annexure, no summary number |

Confirmed the absence of the summary field rather than assuming it:

js

```js
for (let i = 1; i <= doc.numPages; i++) {
  const txt = (await (await doc.getPage(i)).getTextContent()).items.map(it => it.str).join(' ');
  if (/faculty members entered|Number of faculty/i.test(txt)) hits.push(i);
}
// → [] for Sandip; present on the last page for IITB
```

**[M]** The two copies are complementary halves of one form. Same KPI (faculty headcount), two derivations, two sources — which is the concrete case that justifies `source_id` in the row identity.

### 2.9 The faculty annexure, and verifying an extraction is complete

Parsed 190 rows from pages 5–13 by requiring a numeric first cell and ≥9 cells:

js

```js
Object.keys(rows).map(Number).sort((a,b)=>a-b).forEach(k => {
  const cells = rows[k].sort((x,y)=>x.b-y.b).map(o => o.s.trim()).filter(Boolean);
  if (cells.length >= 9 && /^\d+$/.test(cells[0])) recs.push(cells);
});
```

**The verification is the point.** A row-shaped heuristic silently drops rows whose name wrapped onto a second line. Rather than trust the count, I used the document's own serial numbers as a checksum:

js

```js
const srs = recs.map(r => +r.cells[0]);
const seen = new Set(); const dup = [];
srs.forEach(s => { if (seen.has(s)) dup.push(s); seen.add(s); });
const miss = []; for (let i = 1; i <= Math.max(...srs); i++) if (!seen.has(i)) miss.push(i);
({parsed: recs.length, maxSr: Math.max(...srs), uniqueSr: seen.size, duplicates: dup, missing: miss})
```

**[C]** `{parsed: 190, maxSr: 190, uniqueSr: 190, duplicates: [], missing: []}` — contiguous 1..190, no gaps, no duplicates. The extraction is lossless.

**A coincidence I checked rather than reported.** PhD-qualified faculty = 48, and faculty marked `Currently working = No` = 48. Identical numerators looked like a variable-reuse bug. Verified they come from different columns (`Qualification` matched against `/Ph\.?D/` versus `Currently working`) and are genuinely independent. Reported **[M]** as a coincidence with a flag to re-check on another institution — which is still outstanding (§8).

### 2.10 Finding the ₹37.5 lakh discrepancy

This was not a search. It came out of reading the reconstructed page 1 line by line to sanity-check the rotation fix:

```
2018-19 | 480 | 378 | 2019-20 | 158 | 2021-22 | 478 | 389 | 3750000(Three Lakh Seventy Five Thousand) | 66
2019-20 | 480 | 257 | 2020-21 | 214 | 2022-23 | 370 | 306 | 520000(Five Lakh Twenty Thousand)         | 64
2020-21 | 480 | 295 | 2021-22 | 248 | 2023-24 | 320 | 294 | 550000(Five Lakh Fifty Thousand)          | 26
```

**[M]** The digits read 37,50,000; the words in the same cell read 3,75,000. Ten times apart.

**Verification that it is in the document and not in my reconstruction.** The `|` separators are mine; I had to rule out a join artifact. So I went back to raw, unmodified text runs:

js

```js
tc.items.map((it,i) => ({i, s: it.str, x: Math.round(it.transform[4]), y: Math.round(it.transform[5])}))
        .filter(o => /3750000|520000|550000/.test(o.s));
```

**[M]**

```
{i: 211, s: "3750000(Three Lakh",     x: 396, y: 674}
{i: 231, s: "520000(Five Lakh",       x: 427, y: 674}
{i: 251, s: "550000(Five Lakh Fifty", x: 451, y: 674}
```

A single unmodified text run containing both forms, at the same `y` (same column) as the two neighbouring salary cells. Not an artifact.

---

## 3. Session 2 — Excel defect verification

### 3.1 Reading the workbook

python

```python
import openpyxl
wb  = openpyxl.load_workbook('/mnt/user-data/uploads/kpi/DOC-20260901-WA0019.xlsx',
                             data_only=True)
ws  = wb['KPI_Dictionary']
hdr = [c.value for c in ws[1]]
rows = [dict(zip(hdr, [c.value for c in r])) for r in ws.iter_rows(min_row=2)]
rows = [r for r in rows if r['KPI_Code']]        # 229
```

`data_only=True` is safe here because the workbook contains no Excel formulas — the `Formula` column holds text. (It would be destructive if saved; the v2 build in §4 loads without it.)

### 3.2 The claims, and how each was tested

All of these are **[C]** — whole-population counts, not samples.

python

```python
from collections import Counter
Counter(r['Benchmark_Direction'] for r in rows)   # {'Higher': 229}
Counter(r['Priority_12M']        for r in rows)   # {'P2': 229}
Counter(r['Formula'] for r in rows if r['Formula'] not in (None,''))
# {'Lower': 9, 'integer': 3, 'Students/FTE faculty': 1, 'Publications/FTE faculty': 1,
#  'Citations/FTE faculty': 1, 'Faculty/Student': 1, 'Lower absolute variance': 1}
```

**Correcting the brief.** The working claim was *"11 Lower values shifted one column left."* The count is **10** (9 `Lower` + 1 `Lower absolute variance`), and 4 + 10 + 3 = 17 matches the 17 non-empty cells. The claim's arithmetic (5 + 11 + 3 = 19) did not close against the file.

**Testing "shifted one column left."** Printed the neighbouring columns for all 17 rows and compared a broken row against a structurally identical intact one:

python

```python
for n, r in rows_with_numbers:
    if r['Formula'] not in (None, ''):
        print(r['KPI_Code'], {c: r[c] for c in
              ['Variable_Name','Unit','Data_Type','Formula','Benchmark_Direction']})
```

**[M]** On all ten direction rows, `Unit` and `Data_Type` are **correct**:

```
A25  Unit='%'  Data_Type='numeric'  Formula='Lower'  Benchmark_Direction='Higher'
```

Nothing slid. And `Formula` is three columns left of `Benchmark_Direction`, not one:

```
Unit(6) · Data_Type(7) · Formula(8) · Scraping_Keywords(9) · Primary_Source(10) · Benchmark_Direction(11)
```

So the mechanism is a **mis-targeted write**, not a row shift. This changes the repair from "shift cells back" to "set ten cells individually".

### 3.3 A second defect, found by comparing against a control

The three `integer` values in `Formula` sit on A01–A03. Rather than call them strays, I compared A01 with A04, which is the same kind of KPI:

**[M]**

```
        Definition                              Unit                            Data_Type  Formula
  A04   Number of interdisciplinary programmes  count                           integer    —        ✅
  A01   Number of undergraduate programmes      Number of active UG programmes  count      integer  ❌
                                                └──── inserted ────┘             └─ shifted right ─┘
```

An extra label was inserted at `Unit`, pushing `Unit → Data_Type → Formula`. This corrupts **nine cells across three rows**, not three. It also explains a phantom in the type distribution:

python

```python
Counter(r['Data_Type'] for r in rows)
# {'numeric': 150, 'integer': 57, 'boolean': 16, 'count': 3, 'text': 3}
```

`count` appears on exactly A01–A03 and nowhere else — it is a leaked `Unit`, not a data type. **[C]**

### 3.4 The domain-constant columns

Rather than checking nine named columns, I computed the property across all of them:

python

```python
bydom = defaultdict(list)
for r in rows: bydom[r['Domain']].append(r)
for h in hdr[:21]:
    distinct   = len({str(r[h]) for r in rows})
    per_domain = [len({str(r[h]) for r in rs}) for rs in bydom.values()]
    constant   = all(p == 1 for p in per_domain)
```

**[C]** Exactly nine columns are constant within every domain: `Primary_Source`, `QS_Mapping`, `NIRF_Mapping`, `NAAC_Mapping`, `NBA_Mapping`, `AICTE_Mapping`, `UGC_Mapping`, `ISO_21001_Mapping`, `Best_Practice_To_Check`. `ISO_21001_Mapping` has **1** distinct value across all 229 rows.

This had a direct consequence for task 1: `NIRF_Mapping` reads `TLR / GO` for all 36 Academic KPIs and `RP` for all 32 Research KPIs — it maps domains to NIRF's scoring pillars. **It cannot route a KPI to a form field**, so the mapping in §5 had to be built from the forms.

### 3.5 `Scraping_Keywords`

Tested the exact hypothesis rather than eyeballing:

python

```python
ok = sum(1 for r in rows
         if str(r['Scraping_Keywords']).strip() ==
            f"{r['Sub_Parameter']}, {r['Variable_Name']}, {r['Definition']}".strip())
# 229

def toks(s): return set(re.findall(r'[a-z]+', str(s).lower()))
new = sum(1 for r in rows if toks(r['Scraping_Keywords'])
                           - toks(r['Sub_Parameter']) - toks(r['Variable_Name'])
                           - toks(r['Definition']))
# 0
```

**[C]** 229/229 character-exact, and zero rows contribute any token not already present. Stronger than "redundant" — it is a derived column presented as a source of search terms.

### 3.6 Empty columns

python

```python
for h in hdr:
    n = sum(1 for r in rows if r[h] in (None, ''))
    if n == len(rows): print('100% EMPTY:', h)
```

**[C]** 17 columns, not the 14 previously recorded. The phase-boundary argument is unaffected; the count was wrong.

---

## 4. Building `kpi_dictionary_v2.xlsx` — including a bug that nearly shipped silently

Script: `scripts/build_dictionary_v2.py`. Method: `shutil.copyfile` the original, then edit the copy. The original is never opened for writing.

### 4.1 The openpyxl `value=None` trap

**What I wrote first:**

python

```python
ws.cell(row=r, column=col['Formula'], value=None)     # intended: clear the cell
```

**What the verification pass reported:**

```
total cell changes: 43
VERIFY v2:
  Benchmark_Direction: {'Higher': 205, 'Lower': 17, ...}          ← correct
  Formula non-empty  : 17 -> ['Lower', 'integer', 'Citations/FTE faculty', ...]   ← WRONG
```

**How it was caught.** Only because the script re-opens its own output and prints distributions before exiting. The changelog said 43 changes had been made, the direction column was visibly correct, and `Formula` was silently unchanged. Without the read-back the workbook would have shipped with `Formula` still holding the ten directions it was supposed to have been cleared of — and the changelog would have *claimed* they were removed.

**Root cause.** In openpyxl, `Cell.__init__`-style `value=` on `ws.cell(...)` treats `None` as "no value argument supplied", so it is a no-op rather than a clear. Assigning through the property works:

python

```python
ws.cell(row=r, column=col['Formula']).value = None
```

**Generalisable lesson, now a rule:** a write path that reports success is not evidence the write happened. Every generated artifact in this project is re-read and re-counted by the script that produced it.

### 4.2 What the script does

python

```python
RECOVERED = {'A25':'Lower', 'F14':'Lower', 'S21':'Lower', 'I14':'Lower',
             'FIN14':'Lower (absolute variance)', 'FIN16':'Lower',
             'ESG02':'Lower','ESG03':'Lower','ESG04':'Lower','ESG05':'Lower'}
ASSIGNED  = {...8 codes with a one-line justification each...}
CONTEXT   = {'FIN02': ..., 'FIN07': ..., 'FIN10': ...}
NA        = {'G01': ..., 'X06': ..., 'X08': ...}
SHIFTED   = {'A01': ('count','integer','Number of active UG programmes'), 'A02': ..., 'A03': ...}
```

Two audit columns are appended — `Benchmark_Direction_Source` (`recovered-from-Formula` / `assigned-v2` / `needs-client-decision` / `no-direction` / `unchanged-Higher`) and `v2_Note` — plus a `CHANGELOG_v2` sheet with one row per changed cell. Every changed cell is filled `FFF2CC` so it is visible on opening.

**[C] Verified output:** 229 rows; `{'Higher':205,'Lower':17,'Lower (absolute variance)':1, 'Context':3,'N/A':3}`; `Data_Type` = `{numeric:150, integer:60, boolean:16, text:3}` with `count` gone; `Formula` down to the 4 genuine formulas; 43 changelog rows; original file re-checked and still single-valued on `Benchmark_Direction`.

**Deliberately not changed:** `Priority_12M` and `Scraping_Keywords`. The correct priorities cannot be recovered from the file, and guessing them would manufacture authority the data does not have. Documented in the workbook README instead.

---

## 5. Mapping 229 KPI codes to what NIRF supplies

Script: `scripts/build_mapping.py`. This is the most judgment-heavy deliverable in the set and the classification is **[R]** throughout.

### 5.1 Why it had to be hand-built

`NIRF_Mapping` is domain-level boilerplate (§3.4), so there was no column to join on. The inputs were the 72 metric concepts inventoried from the two 2025 Overall submissions, matched against the 229 dictionary definitions by reading both.

### 5.2 The classification rule

```
                        ┌─ Is the value printed in the form? ─┐
                       yes                                    no
                        │                                      │
                     DIRECT                 ┌─ Computable from ≥2 printed
                                            │  institution-level values, with
                                            │  compatible populations & periods?
                                           yes                     no
                                            │                       │
                                        DERIVED      ┌─ Only from the faculty annexure?
                                                    yes                 no
                                                     │                   │
                                                 ANNEXURE   ┌─ Does NIRF carry a WEAKER form —
                                                            │  boolean/ordinal where the KPI wants
                                                            │  a number, or a near-synonym with a
                                                            │  different definition?
                                                           yes            no
                                                            │              │
                                                        PARTIAL          NONE
```

**[C] Result:** DIRECT 13, DERIVED 16, ANNEXURE 6, PARTIAL 12, NONE 182.

### 5.3 The boundaries that are genuinely arguable — **[R]**

**DERIVED vs NONE.** `A25 Dropout rate` is classified DERIVED as `1 − (graduating in minimum stipulated time / admitted)`. This is an **approximation**: students who graduate late are counted as dropouts. I classified it DERIVED with an explicit low-confidence note rather than NONE, on the reasoning that a flagged approximation is more useful than a blank. *A stricter analyst would call it NONE, and I would not argue hard.* The row carries the caveat either way.

**DERIVED vs PARTIAL.** `S11 Yield rate` is defined as enrolled/admitted. NIRF gives admitted/sanctioned-intake. Same shape, different populations. Classified PARTIAL, not DERIVED, because the denominators are different objects — the computation would succeed and mean something else. This is the rule I applied consistently: **if the arithmetic works but the populations differ, it is PARTIAL, not DERIVED.**

**PARTIAL vs NONE.** `ESG07 Waste recycling rate` wants a percentage; NIRF asks *"What is the level of recycling infrastructure available on your campus?"* with ordinal answers. Classified PARTIAL because the answers genuinely discriminate (IIT Bombay: `Comprehensive infrastructure`; Sandip: `No recycling infrastructure on campus`). *An analyst who treats the dictionary's unit as binding would classify it NONE, and the domain-level "0% reachable" figure for ESG would become "0% reachable, and no usable proxies either."*

**What would change my mind on any of these:** a client decision that the dictionary's `Unit` column is contractual. If units are binding, every PARTIAL collapses to NONE and coverage falls from 47 to 29.

**Known softness in the NONE bucket.** 182 codes were classified NONE, most by not appearing in the explicit mapping table. I read all 229 definitions against the 72 concepts, but this is the one place where a miss is silent — an unmapped code defaults to NONE. A missed match would *understate* coverage, so the 29 figure is a floor rather than a point estimate.

### 5.4 The reverse count

**[C]** Of the 72 NIRF concepts, 33 have a KPI home and **39 do not** — checked by asserting every name in the unmapped list exists in `metric-inventory.csv` before counting, so a typo in the list could not silently shrink the number.

---

## 6. The digits-versus-words checksum study

Method: extract every `digits(words)` pair, parse the words into a number, compare.

### 6.1 Reassembling wrapped cells — a prerequisite that isn't obvious

The words routinely continue onto two or three further lines of the same cell. A line-by-line reader finds `3750000(Three Lakh` and no closing bracket, so the regex never matches. The fix is to cluster by **column start** and read down, breaking on a large vertical gap:

js

```js
const cols = {};
items.forEach(o => { const k = Math.round(o.b / 6); (cols[k] = cols[k] || []).push(o); });
Object.values(cols).forEach(arr => {
  arr.sort((x, y) => x.a - y.a);
  let buf = [], last = null;
  const flush = () => {
    if (buf.length) {
      const t = buf.join(' ').replace(/\s+/g, ' ');
      const re = /(\d[\d,]{2,})\s*\(([^()]{4,220}?)\)/g;
      let m; while ((m = re.exec(t)) !== null) pairs.push({p: i, digits: m[1], words: m[2].trim()});
    }
    buf = [];
  };
  arr.forEach(o => { if (last !== null && o.a - last > 22) flush(); buf.push(o.s); last = o.a; });
  flush();
});
```

The `22` gap threshold and the `/6` column bucket were tuned by inspecting output on the IITB file until all 29 known pairs reassembled. **[R]** — they are empirical constants fitted to this form's leading and column spacing, and would need re-tuning for a differently-typeset document.

### 6.2 The sample

**[C]** 14 documents: ten institutions from the 2025 Overall top-100 sampled at ranks **1, 2, 3, 5, 10, 20, 30, 50, 75, 100**, plus four Sandip submissions (2024/2025/2026 Overall, 2025 Engineering).

**Sampling rationale and its limits.** The rank-stratified pick was chosen to span the quality range rather than cluster at the top. It is not random, and ten is small. The headline 2.75% rate carries a wide interval — 11 events in 400 trials gives a 95% Wilson score interval of **1.54% – 4.86%**. **The rate should be quoted as "a few percent", not as 2.75%.** The *institution-level* observation — 4 of 10 ranked institutions affected, 0 at IIT Bombay, 6.2% at Sandip — is the more robust finding.

### 6.3 The parser failure — in full

**Version 1** merged units and tens into one map and accumulated each scale independently:

js

```js
const U  = {one:1, ..., ninety:90};              // ONES and TENS in one map
const SC = {thousand:1e3, lakh:1e5, crore:1e7, ...};
function w2n(s){
  let total = 0, cur = 0, any = false;
  for (const t of toks) {
    if (t in U)             { cur += U[t]; any = true; }
    else if (t === 'hundred'){ cur = (cur || 1) * 100; any = true; }
    else if (t in SC)       { total += (cur || 1) * SC[t]; cur = 0; any = true; }   // ← the bug
    else return null;
  }
  return any ? total + cur : null;
}
```

**[C] It reported 9 mismatches.** Four were its own fault:

| **#InstitutionDigitsParser saidCause** |             |                |               |                                                |
| -------------------------------------- | ----------- | -------------- | ------------- | ---------------------------------------------- |
| 1                                      | IR-O-U-0220 | 1,453,587,730  | 1,453,587,037 | idiom: `seven thirty` read as 7+30=37, not 730 |
| 2                                      | IR-O-U-0500 | 14,602,652,173 | 4,602,653,173 | scale: `One Thousand Four Hundred Sixty Crore` |
| 3                                      | IR-O-U-0500 | 16,202,283,739 | 6,202,284,739 | same                                           |
| 4                                      | IR-O-U-0253 | 839,068,856    | 839,068,064   | idiom: `eight fifty six` read as 8+50+6=64     |

Tracing #2 by hand: `one` → cur=1; `thousand` → total += 1×1000 = **1,000**; `four hundred sixty` → cur=460; `crore` → total += 460×10⁷, giving 4,600,001,000 — the stray 1,000 from the mis-scoped "One Thousand" is still sitting there, which is why the tail reads **653**,173 instead of **652**,173. The thousand should have multiplied the crore group, not stood alone.

**How I noticed, and how close it came.** Two different tells, with very different margins:

- **The scale bug announced itself.** Ratios of 3.17 and 2.61. Human transcription errors have characteristic shapes — 10×, a transposition, a dropped digit — and 3.17× is not one of them. That is what made me stop and hand-check rather than tabulate.
- **The idiom bug very nearly shipped.** Ratio 1.0000. Deltas of 693 and 792 on nine-figure numbers. That looks *exactly* like a plausible small typo in a hand-typed form, which is precisely the thing the study was looking for. I only caught it because I had decided to hand-verify all nine before publishing any of them, and on reading `eight fifty six` aloud it is obviously spoken English for 856.

**If I had tabulated the nine and shipped, roughly 44% of the reported defects would have been mine, two of them in a form indistinguishable from a real finding — and the report accusing four institutions of sloppy data entry would itself have been the sloppy artifact.**

**Version 2** fixed both:

js

```js
// scale absorption: a larger scale multiplies everything accumulated so far
else if (t in SC) {
  const s = SC[t];
  if (s >= prevScale) { result = (result + cur) * s; }   // "One Thousand ... Crore"
  else                { result += cur * s; }
  prevScale = s; cur = 0;
}

// idiom guard: a unit 1-9 immediately followed by a tens word, with no 'hundred' between
for (let i = 0; i + 1 < toks.length; i++) {
  if (ONES[toks[i]] >= 1 && ONES[toks[i]] <= 9 && toks[i+1] in TENS)
    return {v: null, why: 'idiom'};      // ABSTAIN — do not guess, do not accuse
}
```

**Self-test before re-running**, against six word forms whose digit values were already known:

js

```js
[['Eight Hundred Fifty Two Crore Thirty Nine Lakh Seventy Five Thousand One Hundred and One', 8523975101],
 ['One Thousand Four Hundred Sixty Crore Twenty Six Lakh Fifty Two Thousand One Hundred Seventy Three', 14602652173],
 ['Three Hundred Nine Crores Sixteen Lakhs Fifty Nine Thousand Four Hundred and Seventy Nine Only', 3091659479],
 ['Ninety One Lakhs Seventy Seven Thousand Six Hundred Twenty Five Only', 9177625],
 ['Twenty Lakhs Only', 2000000],
 ['Eighteen Lakhs Eighty Thousand', 1880000]].map(([w, exp]) => ({exp, got: w2n(w).v, ok: w2n(w).v === exp}))
// all six ok: true
```

**[C] After the fix:** 418 pairs → 18 unparseable (16 misspellings, 2 idioms) → 400 comparable → 389 agree, **11 disagree**. Each of the 11 was then hand-checked against raw text runs; the two most consequential (`999 (Zero)` and the ₹53 crore Engineering figure) were confirmed as single unmodified runs. All 11 survived.

**Design consequence.** The abstain state is not a nicety. 18 of 418 word forms (4.3%) are unparseable by any strict parser, because people write `Sevety`, `Hundered`, `Eiight`, `Twentyone` and `Thous and`. A two-state checker reports every one as a defect.

### 6.4 Deciding the ₹37.5 lakh words are right and the digits wrong — **[R]**

The check itself is symmetric; it says only that the two disagree. Concluding which side is wrong is a judgment, made on three pieces of evidence:

1. **Neighbouring years.** The same column reads ₹5.2 lakh (2022-23) and ₹5.5 lakh (2023-24). ₹3.75 lakh fits that series; ₹37.5 lakh does not.
2. **Error shape.** A stray trailing zero is among the commonest data-entry errors. Producing "Three Lakh Seventy Five Thousand" *in words* from a true value of 37,50,000 requires composing a wrong sentence, which is far rarer.
3. **Institutional plausibility.** A median UG salary of ₹37.5 lakh would exceed IIT Bombay's ₹19.6 lakh by nearly 2×, at a mid-tier private engineering college.

**This is inference, not measurement.** Only the institution can settle it. **The pipeline must not encode this conclusion** — it flags `CONFLICTING` and retains both. The judgment belongs in the report, where a human can see the reasoning, not in the data.

**What would change my mind:** an audited placement report showing ₹37.5 lakh, or the 2026 submission correcting the words rather than the digits. (Checked: **[M]** the same cell carries the same 10× discrepancy in the 2024 submission, so it is copied forward, which weakly supports the digits being the stale artifact.)

---

## 7. Judgment register

Every call where evidence constrained but did not determine the answer.

### 7.1 Assigning direction to the eight unmarked KPIs — **[R]**

These have no direction anywhere in the file, so there was nothing to recover. I assigned from the KPI's own definition and unit:

| **KPIUnitReasoningContestable?**   |                                   |                                                        |                                                                                     |
| ---------------------------------- | --------------------------------- | ------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| `X03/X04/X05` QS / THE / NIRF rank | rank                              | Rank 1 beats rank 200. Arithmetically unambiguous.     | No                                                                                  |
| `A18` Student-faculty ratio        | ratio, `Students/FTE faculty`     | Fewer students per faculty is better.                  | No                                                                                  |
| `A17` Average class size           | students/class                    | Smaller is the near-universal quality signal.          | Barely                                                                              |
| `P15` Career counsellor ratio      | ratio (students per professional) | Same shape as A18.                                     | No                                                                                  |
| `S10` Acceptance rate              | %                                 | Lower = more selective.                                | **Yes** — for an access-mission institution, higher acceptance is the goal          |
| `A09` Review frequency             | years                             | Shorter interval between curriculum reviews is better. | **Yes** — the unit is ambiguous; if it means "reviews per year" the direction flips |

`A09` is the weakest. `Unit` says `years` and `Definition` says *"Average frequency of formal curriculum review"* — "frequency" and "years" pull in opposite directions. I read it as an interval because the unit is authoritative over the prose. **A different analyst could read "frequency" as a count and assign Higher.** It is marked `assigned-v2` so it surfaces for review.

`S10` is a real values question, not a measurement one. I assigned `Lower` because this is a benchmarking exercise against elite peers, where selectivity is the conventional reading. If the president's framing is access and widening participation, it should be `Higher` or `Context`.

### 7.2 Marking three as `Context` rather than assigning — **[R]**

`FIN02` tuition revenue share, `FIN07` cost/student, `FIN10` faculty cost/revenue.

The criterion I used: **a KPI gets ****`Context`**** when two competent analysts with the same data would assign opposite directions because they hold different goals, not different facts.** Cost per student reads as resourcing (higher better) in QS/THE methodology and as efficiency (lower better) in a cost review. Nothing in the file resolves it.

The alternative was to pick the ranking-methodology convention and move on. I did not, because a guessed direction is indistinguishable in the file from a measured one, and this project's entire premise is that those should be distinguishable. `Context` is a visible unknown; a guess is an invisible one.

**Risk of my choice:** a Phase 2 gap engine now has three KPIs it cannot compute. That is the intended behaviour but it will look like an omission unless documented — which is why `Benchmark_Direction_Source` exists.

### 7.3 Token overlap for the parameters join — **[R]**

The two documents share no key (`1.4 Retention, Progression and Dropout` versus `Progression` and `Dropout` as separate Excel rows). Options considered:

| **ApproachWhy not chosen**      |                                                                                                            |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Manual mapping of all 160 × 229 | Correct, but hours of work for an output that turned out to be near-worthless (below)                      |
| Embedding similarity            | No offline model available in the container; would add an unverifiable dependency to a reconciliation task |
| **Token overlap within domain** | Transparent, re-runnable, and every match carries a score the reader can audit                             |

Implementation:

python

```python
STOP = {'and','or','of','the','a','an','for','to','in','on','with','by','per','rate','share',
        'count','number','total','university','institution','institutional','programme',
        'programmes','program','programs','kpis','kpi','academic','student','students',
        'faculty','annual','year','years'}
def toks(s): return {t for t in re.findall(r'[a-z]+', str(s).lower())
                     if len(t) > 2 and t not in STOP}
score = len(theme_tokens & kpi_tokens) / len(theme_tokens)
```

**Threshold tuning, and why it is arbitrary — [R].** The first run used `>= 0.34` and produced 116/229 matches. Spot-checking showed `A25 Dropout rate` was *unmatched* despite an obvious correct target: theme tokens `{retention, progression, dropout}`, KPI tokens including `dropout` → score exactly 1/3 = 0.333, just under. Lowering to `0.30` gave 164/229 with `A25` correctly matched to `1.4 Retention, Progression and Dropout`.

**That is threshold-fitting to a spot check, and I am flagging it as such.** A different analyst picking 0.25 or 0.40 gets a materially different match count. This is why every entry carries `match_score` and a `MATCHED` / `WEAK_MATCH` status rather than being presented as settled: the numbers 164 and 65 are properties of my threshold as much as of the documents.

**Why it stopped mattering.** Having built it, I measured what the routing actually contains:

python

```python
allsrc = Counter()
for theme in themes: allsrc.update(theme['sources'])
```

**[C]** `"University official website / annual report / statutory disclosures"` appears on **148 of 160 themes (93%)**. All 34 directory entries are organisation homepages (`https://www.naac.gov.in/`), not retrievable documents. The join is technically buildable and substantively empty — which became the finding, and is why `IN_sources.yaml` leads with three verified retrieval patterns and treats the join as an appendix.

### 7.4 Counts that contradict the documents themselves — **[C]**, not judgment

Worth separating from the above, because these are measurements:

python

```python
# parameters docx: 10 domain tables + 1 source directory
rows = [r for ti in range(10) for r in doc.tables[ti].rows[1:] if r.cells[0].text.strip()]
len(rows)                                # 160   (the docx TITLE claims 139)
len({r.cells[0].text.strip() for r in rows})  # 160, no duplicates

# requirement docx section 7
sum(1 for t in d2.tables[2:13] for r in t.rows[1:] if r.cells[0].text.strip())   # 234, 11 tables
```

Three documents give three different counts of nominally the same thing — 139 (claimed), 160 (actual), 137 (Excel `Sub_Parameter`), 229 (Excel KPIs), 234 (requirement docx §7). They are not all counting the same object, and the 10-vs-11 domain discrepancy is located precisely: the parameters docx has ten domain tables and no cross-cutting `X` section, while the requirement docx §7 and the Excel both have eleven.

---

## 8. Limitations

**Could not be determined.**

- **Whether the NONE bucket is exactly 182.** A code with no entry in the mapping table defaults to NONE. I read all 229 definitions, but a missed match fails silently and would *understate* coverage. Treat 29 as a floor.
- **Whether the 2.75% checksum rate generalises.** Ten institutions, non-random; 95% Wilson interval 1.54%–4.86%. The institution-level pattern is more robust than the pooled rate.
- **Whether ****`/Rotate 90`**** holds across all 537 ranked institutions.** Verified on 8 documents from 2 institutions. It is almost certainly a property of NIRF's form generator, but "almost certainly" is not "checked".
- **Whether rank-band institutions (101–300) are reachable.** Those list pages use a different filename convention than the top-100 pages I probed, so 537 is a floor.
- **Whether MIT's Common Data Set HTML is stable across years.** The 2025-26 page was confirmed **[M]**; earlier years are linked but were not opened.
- **Whether the 48/48 coincidence in Sandip's annexure recurs.** Verified as genuine for Sandip **[C]**, not tested elsewhere.

**What I would check next, in priority order.**

1. Run the §2.4 diagnostic across a random 30 of the 537 IDs — settles rotation, page count, and whether any institution's copy is a scan. About ten minutes of browser time.
2. Extend the checksum study to 50 institutions. Narrows the interval and tests whether disagreement rate correlates with rank, which would make it a usable quality signal rather than an observation.
3. Parse one NIRF *Engineering* and one *Management* submission fully, not just for pairs. Category-specific field sets are the most likely source of surprises in the 182.
4. Open three MIT Common Data Set years and diff the section structure.
5. Have a second person re-classify a random 30 of the 229 against the §5.2 decision tree, blind, and measure agreement. The DERIVED/PARTIAL boundary is the one I would expect to diverge.

**Conclusions most likely to be revised as more institutions are processed.**

| **ConclusionDirection of likely revision** |                                                                                                                                                |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| 29 KPIs populatable per submission         | **Up.** NONE is a silent default and some category forms carry more fields.                                                                    |
| 2.75% checksum disagreement                | **Wide.** Small sample; institution-level variance is large (0% to 6.2%).                                                                      |
| "One parser handles all NIRF years"        | **Down, slightly.** Field sets already vary by category and institution type; some institution-published copies will be differently generated. |
| The 6 annexure-derived KPIs                | **Down for most institutions.** Only institution-published copies carry the annexure; ranked institutions' portal copies do not.               |
| 164/229 routed in `IN_sources.yaml`        | Unstable — a property of a hand-tuned threshold, not of the documents.                                                                         |

## 9. The reusable pattern catalogue

This is the part that transfers. Each pattern cost real time once and near-zero afterward. Grouped by where it bites.

### Geometry and layout

**P1 — Page rotation is not applied to text coordinates.** *Breaks:* grouping by `transform[5]` groups columns and calls them rows; side-by-side tables merge; labels separate from values. No error raised. *Handled:* read `page.rotate`; when 90, group by `transform[4]` and sort by `transform[5]`. Always verify one known value end to end.

**P2 — Header cells wrap across up to five physical lines.** *Breaks:* each wrapped line is treated as its own row; header text never matches anything. *Handled:* assemble the full header block before matching.

**P3 — Data cells wrap too, and the regex spans the wrap.** *Breaks:* `3750000(Three Lakh` has no closing bracket on its line, so `\(([^)]+)\)` never fires and the checksum silently finds nothing to check. *Handled:* cluster items by column start, read down within a column, break on a large vertical gap, then regex the reassembled string.

**P4 — Header text varies between institutions for the same field in the same form year.** *Breaks:* `Median salary of placed graduates per annum(Amount in Rs.)` at one institution, `Median salary of placed graduates(Amount in Rs.)` at another. *Handled:* match columns by geometry; use header text only to verify.

**P5 — Field set varies by category, institution type and year.** *Breaks:* a template parser silently returns nulls for blocks that exist. *Handled:* discover sections by header, parse the table beneath. Never template.

### Document composition

**P6 — Mixed-mode PDFs: digital pages with scans spliced in.** *Breaks:* a document-level "has text layer?" test says yes and four pages are silently empty. *Handled:* decide per page. Under \~200 extracted chars *with images present* → OCR path.

**P7 — The published copy and the institution's own copy are different documents.** *Breaks:* one gives a stated total, the other a derivable detail table, and whichever arrives second overwrites the first. *Handled:* `source_id` in the row identity. Never dedupe on `(university, kpi, year)`.

### Values

**P8 — Value carries a parenthetical restatement.** *Breaks:* stripping non-digits concatenates the digits inside the words; casting after strip gives nonsense. *Handled:* anchored numeric prefix match (`^\d[\d,]*`), never a global strip.

**P9 — Indian numbering (lakh / crore) in both digits and words.** *Breaks:* `"12.5 crore"` → `12.5`. Five orders of magnitude, no exception. *Handled:* explicit scale parser with **scale absorption** — a larger scale multiplies everything accumulated so far, so `One Thousand Four Hundred Sixty Crore` = 1460 crore, not 1000 + 460 crore.

**P10 — The dual encoding is a free checksum, and a trap.** *Breaks both ways:* skipping it discards \~30 corroborations per document; implementing it two-state turns 4.3% unparseable word forms into false accusations. *Handled:* three states — CONFIRMED / CONFLICTING / **UNVERIFIED (abstain)**. Never auto-resolve.

**P11 — ****`-`**** is not zero.** *Breaks:* "programme not offered" becomes an intake of zero, dragging every derived average. *Handled:* distinguish empty, dash, and zero at parse time.

### Time

**P12 — One physical row carries several different year keys.** *Breaks:* placement rows hold intake year, lateral-entry year and graduation year side by side; reading the first misdates placements by up to three years. *Handled:* map each column to its own year key from the header block.

**P13 — "Current" blocks print no year at all.** *Breaks:* the year gets inferred from whatever year appeared last on the page. *Handled:* take the year from document identity, and record that it was inferred.

**P14 — Several period semantics coexist in one document.** *Breaks:* academic year (most blocks), calendar year (IPR/patents), validity window with dates (NAAC). A ratio across two of them is wrong even when both inputs are right. *Handled:* `period_type` travels with `year`; block ratios across incompatible types.

### Derivation

**P15 — Free-text categorical fields.** *Breaks:* `Ph.D`, `M.E.`, `M.Tech`, `M.Sc.`, `MSc(Mathematics)`, `MCA`, `M.A` all appear in one column. Any taxonomy is a mapping decision, not an extraction. *Handled:* extract verbatim, map explicitly, record the mapping version.

**P16 — Derived percentages have a denominator choice.** *Breaks:* "share of faculty holding PhD" over all 190 annexure rows and over the 142 currently employed are different numbers, and nothing in the output says which. *Handled:* the dictionary decides; the row records which was used.

**P17 — Ordinal or banded answers where the KPI wants a rate.** *Breaks:* `"Yes, more than 80% of the buildings"` is not 80%, and coercing it invents precision. *Handled:* store as ordinal, classify the KPI PARTIAL, require an explicit dictionary decision.

**P18 — Near-synonyms with different definitions.** *Breaks:* NIRF's `Total Amount Received` for sponsored research is not research *expenditure*; `Patents Published` is not `Patents Filed`. *Handled:* record the substitution on the row, or do not store the value.

### Acquisition

**P19 — Test for a CMS index before writing a crawler.** *Wins:* `/wp-json/wp/v2/media?search=nirf` returned a complete document inventory in one request, including four years of submissions linked from no navigation page.

**P20 — Look for a predictable URL pattern before building a frontier.** *Wins:* `nirfpdfcdn/{year}/pdf/{Category}/{ID}.pdf` turns 537 institutions into a list, not a crawl. Verify the pattern across at least three years before relying on it.

### Process

**P21 — Read back every artifact you write, in the script that wrote it.** *Breaks:* `openpyxl`'s `cell(value=None)` is a silent no-op; the changelog claimed 10 cells were cleared and they were not. *Handled:* every build script re-opens its output and prints distributions before exiting.

**P22 — Hand-verify every defect before reporting it.** *Breaks:* 4 of the first 9 checksum "defects" were parser bugs. Two of those four were indistinguishable from real findings by shape alone. *Handled:* self-test the parser against known-good values first; hand-check every survivor against raw, unmodified source before it reaches a document.

---

## 10. Tooling

| **ToolVersionUsed forNotes** |                  |                                    |                                                                                                                                              |
| ---------------------------- | ---------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Python                       | 3.11.15          | all Excel/docx work                | cloud container                                                                                                                              |
| openpyxl                     | 3.1.5            | reading and writing the dictionary | **`cell(value=None)`**** does not clear a cell** — assign `.value = None`. `data_only=True` is destructive if saved.                         |
| pandas                       | 3.0.2            | available, barely used             | 229 rows did not justify it over plain dicts                                                                                                 |
| python-docx                  | 1.2.0            | requirement and parameters docx    | `table.rows[0].cells` for headers; multi-line cells arrive as `\n`-joined text                                                               |
| PyYAML                       | 6.0.3            | validating emitted YAML            | `IN_sources.yaml` is hand-emitted then `yaml.safe_load`-checked                                                                              |
| pdf.js                       | 3.11.174         | **all** PDF work                   | ran in the laptop browser, not the container. `getTextContent()` for items, `getOperatorList()` for image counts, `page.rotate` for geometry |
| DOMParser                    | browser built-in | HTML table extraction              | used instead of a Python HTML parser because the network is on the laptop                                                                    |

**Where things performed worse than expected.**

- **WebFetch** fails closed on a robots.txt fetch error and reports it as a disallow. It also summarises through a small model: asked to reproduce a NIRF PDF verbatim it returned digit groupings like `1,77,10,56,28` for `177105628`. **Useful for discovery, never for extraction.**
- **The cloud container's egress allowlist** blocked every target host including Wikipedia, which forced the entire browser-side parsing architecture. Worth checking first on any similar task.
- **Browser session state** is lost on navigation or pane close — three times mid-session. Every JS block must be self-contained, re-loading its libraries with a `typeof` guard.
- **openpyxl's silent no-op** on `value=None`, covered above. The most expensive single defect in session 2 and it produced no error of any kind.

**Not used, and why.** Docling, PyMuPDF, LangExtract, Crawl4AI and Pandera are all in the v2 stack but none was exercised here — the container could not reach the documents and the laptop has no shell. Nothing in this investigation validates or invalidates those choices. The *rules* in `CLAUDE.md` are library-agnostic by design, and P1 in particular must be re-verified against whichever PDF library is finally chosen.

---

## 11. Reproducing this

1. Stage the three client documents into a working directory.
2. Run the three scripts in `scripts/` — they take the workbook and docx paths as module-level constants and are independent of each other:
   - `build_mapping.py` → `kpi-to-nirf-mapping.csv` plus the coverage counts
   - `build_dictionary_v2.py` → `kpi_dictionary_v2.xlsx` plus a verification read-back
   - `build_sources.py` → `IN_sources.yaml` plus the reconciliation counts
3. For the PDF work, on a machine with unrestricted network, replace the browser-side pdf.js calls with PyMuPDF. The rotation handling transfers directly — `page.rotation` and `page.get_text("dict")` expose the same information. **Verify P1 against a known value before trusting any output.**
4. Every number quoted in the other findings documents appears in the stdout of one of those three scripts, or in a browser JS block reproduced verbatim in this file.