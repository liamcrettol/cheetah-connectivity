# Cheetah connectivity capstone — project context

**September 4 update:** First read [the current handoff](handoff/2026-09-04/README.md).
The original context below includes earlier plans and setup instructions that are
now historical. The dated handoff distinguishes completed diagnostics from
pending production decisions; do not rerun completed work or treat old plans as results.

Read this before doing anything. It is the handoff from a previous session and
should save you from re-deriving decisions or rebuilding work that already exists.

---

## Who and what

Liam Crettol, senior at Weber State University, finishing a B.S. in Zoology with
a GIS certificate and a minor in Geospatial Studies. Also works as the sole GIS
technician/administrator at Pineview Water Systems, but **this project is
academic and must stay separate from that work** — including not using the
employer's ArcGIS licence for it.

The project is his capstone: a GIS study of landscape connectivity for
free-ranging cheetahs in southern Africa.

**Working title.** Changing connections: temporal potential structural
connectivity, unprotected pinch points, and monitoring priorities for
free-ranging cheetahs in southern Africa.

**The question.** Where has modelled landscape permeability between established
cheetah range cores deteriorated since the 2010–2016 range assessment, which
unprotected pinch points remain important across plausible assumptions, and
where should new monitoring be prioritised?

**Extent.** Namibia, Botswana, Zimbabwe, South Africa. Snapshots 2012, 2016,
2020, 2024. Working resolution 1 km, with 2 km and 5 km as sensitivity.

**Deadline assumption.** Capstone submission end of April 2027. Write to
capstone requirements first, restructure for a journal afterward.

---

## The two things that define this project

Get these wrong and the advice you give will be wrong.

**1. Range cores are FIXED at the historical baseline.** They come from the
Weise et al. 2017 Dryad archive (2010–2016 evidence) and do not move between
snapshots, because no comparable reassessment exists. Every bit of measured
temporal change is therefore landscape-side, not cheetah-side. This must be
stated in the abstract, not buried in limitations.

**2. This is structural, not functional, connectivity.** The model identifies
where the landscape is permeable. It is not evidence that cheetahs move there.
There is a claim dictionary in the protocol listing prohibited phrasings
("functional corridor", "validation", "conflict hotspot", "caused"). Respect it.

---

## What already exists — do not rebuild

- **Repo** `cheetah-connectivity`, developed in a GitHub Codespace. Liam is on
  Windows and has the Student Developer Pack (GitHub Pro, 3,000 Actions
  minutes, 180 Codespaces core-hours).
- **`protocol/protocol.tex`** — 10-page predeclared analysis protocol, drafted,
  **not yet signed**. Contains nine open decisions marked `\dec{}` in orange.
- **`tex/`** — LaTeX manuscript scaffold, capstone-first with a `\capstonetrue`
  flag for a journal version later. Compiles clean via `make`. Sections are
  scaffolded with `\TODO{}` markers that render red.
- **`refs/methods_canon.bib`** — 17 verified entries (McRae, Zeller ×2,
  Adriaensen, Beier, Saura ×2, Keeley, Roberts, Circuitscape.jl, Omniscape.jl,
  Naidoo, Brennan, Osipova, Melzheimer, Meijer, Kennedy). **Every DOI was
  resolved against the publisher record in August 2026. Do not re-verify.**
  Two entries need full author lists confirmed: `naidoo2024kaza`,
  `brennan2020multispecies`.
- **`refs/cheetah_lit.bib`** — empty, awaiting a Zotero export.
- **`tools/manifest.py`** — regenerates `manifest.csv`, an inventory of analysis
  outputs. Replaces a hand-maintained output register. Liam must edit
  `OUTPUT_ROOTS` to match his machine.
- **`.github/workflows/build.yml`** — CI builds both PDFs on push.
- **Execution guide spreadsheet** — 28 steps, 111 sub-steps, with ArcGIS Pro
  procedures, parameters, verification checks, output names, time estimates
  (~108 hours total), paper sections and sentence starters. Now a Google Sheet.
- **`CheetahTracker.gs`** — Apps Script for that sheet: import repair,
  conditional formatting, status roll-up from sub-steps to parent steps,
  auto-timestamping, a Next Up tab, remaining-effort calculation, late flagging,
  and a Monday email digest.

---

## Decisions already locked

- 1 km working resolution, justified against the 10 km evidence grid.
- Africa Albers Equal Area Conic (ESRI:102022). Equal-area is required because
  areas are reported.
- Six resistance scenarios, predeclared, **none preferred**. RES-04 is
  illustrative only.
- Circuitscape.jl in **pairwise** mode, not Omniscape, because cores are defined
  a priori.
- Corridors are continuous current surfaces summarised by quantile. Thresholded
  polygons are cartographic only.
- Protected-area null compares against the modelled network, not the full extent.
- **Validation route: plausibility check only.** No resistance surface is fitted
  to occurrence data, so the word "validation" is prohibited. Independent
  evidence is the Limpopo tracking dataset and central-eastern Namibia
  camera-trap work.
- Roads, livestock, fences and terrain are STATIC covariates. Only GHSL
  built-up, VIIRS radiance and MODIS VCF carry temporal signal.
- Categorical land cover is never differenced between years (class instability
  would manufacture change).
- Only ArcGIS Pro **Basic + Spatial Analyst** is required. Nothing needs
  Advanced. Graph metrics go to Conefor or igraph, never Network Analyst.

## Decisions still open

1. Confirm the H1 revision (loss concentrated on high-betweenness links rather
   than distributed, which is falsifiable; the original H1 was tautological).
2. **k/n = 0.8 robustness threshold** — the most consequential number. High on
   purpose, because the six scenarios share input layers and would agree partly
   for that reason alone.
3. Core minimum-area thresholds (2000 / 1000 / 500 km²) against reported cheetah
   home ranges.
4. PC dispersal distance — currently a 100 km placeholder, needs a cited value.
5. The 100 km extent buffer and the 120-hour compute trigger.
6. Full CRS WKT to paste into the protocol.
7. Veterinary fence acquisition deadline and contingency.
8. Confirm RES-06 (composite gHM scenario) is added, RES-04 illustrative.
9. The three MCDA weight sets.

---

## Immediate task

Liam is moving to Claude Code specifically to get **direct cell-level access to
his Google Sheet**, which the previous session could not do (the available
Google connector was file-level only, and the Autosheet agent ran out of
credits).

**Step 1.** Set up a Google Sheets MCP server with read/write access. He is not
a developer, so walk him through it concretely: Google Cloud project, enable the
Sheets API, credentials, install the server, share the sheet with the service
account if that is the auth model. Do not assume familiarity.

**Step 2.** Once connected, verify the sheet and finish the repair. The Apps
Script `repairAfterImport()` may already have done most of it. Check:
- 8 tabs: Start Here, Master Workflow, Conventions, Questions, Paper Map,
  Sentence Starters, ArcGIS Tool Index, Progress
- Master Workflow: header row 4, data from row 5, 28 parent steps + 111
  sub-steps, ending around row 143, 16 columns
- Status is column N, Date column O, Est. mins column I, Stage column B
- Conditional formatting exists (it is lost on xlsx import and must be rebuilt)
- Progress formulas point at rows 5–143 and column N, not the old 5–32 / column L

A known bug was already fixed: the merged title banner in rows 1–3 blocks
`setFrozenColumns`, so merges must be broken first.

**Step 3.** Then get back to the real work, which is the nine open decisions and
verifying the nine literature rows still marked "Bibliographic Seed-Verify" in
his original planner workbook. Neither needs spreadsheet access.

---

## How Liam wants you to work

- Casual and concise. Lowercase-friendly. **No em-dashes.** No corporate speak.
- Paragraphs over bullets unless bullets are asked for.
- Short by default; go long only when depth is requested.
- Honest and direct. No sugarcoating, no cheerleading. He has explicitly asked
  for real assessments and has twice improved a deliverable by pushing back.
- Provide full scripts when asked for code. Work from actual error output when
  debugging. Do not assume packages or tools are installed.
- He prefers iterating in conversation over receiving large finished products.
  Check in before building something big.
- He got overwhelmed once by volume. Prefer one next step over a complete plan.
- Keep Pineview work context and academic context strictly separate.

## Things that will waste his time

- Re-verifying the 17 bibliography DOIs. Already done.
- Rebuilding the protocol, manuscript scaffold or execution guide. They exist.
- Suggesting Overleaf. Compile timeouts drove him off it.
- Suggesting Network Analyst for graph metrics. Wrong tool.
- Long setup detours. He has already spent a full session on tooling and wants
  to be doing the actual work.
