# CoStar sponsor integration — status and demo guidance

Verified on branch `claude/sprint-recovery` against `data/runtime` (2026-11-15).

## 1. Is there a genuine CMS + CoStar + Vexcel building?

**No.** Run the read-only check:

```bash
python -m scripts.verify_sponsor_overlap --analysis-dir data/runtime
```

A building qualifies only if it has an exact CoStar match **and** Vexcel evidence with the same
building ID, the Vexcel address equals the normalized building address, the image hash matches
its manifest, and the independent LA County CAMS address point falls inside the 80 m image.

| | 3800 Barham Blvd | 12444 Victory Blvd |
| --- | --- | --- |
| Building ID | `bldg_1161264fd5dbc223` | `bldg_793ac00ed2ae2571` |
| CMS registrations / review level | 1 / no indicators (6.25) | 5 / worth a look |
| CoStar | **Exact match**, property 248351 (Barham Plaza) | No exact match |
| CoStar point vs CAMS address point | 28.5 m (consistent) | — |
| Vexcel | None | **Ortho image**, retrieved 2026-11-14, SHA-256 verified |
| CAMS point vs image centre | — | 35.3 m (18.8 m S, 30.0 m W; inside the 40 m half-width, off-centre) |
| Matterport | Model `cqDGKrH5ZTu` linked to property 248351 in the sponsor CSV | — |

The two properties are different buildings several kilometres apart. Any same-building
CoStar + Vexcel example (evaluation scenario S10) is **synthetic**.

## 2. Exact next action to create a genuine overlap

Fetch Vexcel imagery for the existing exact CoStar match, using the LA County CAMS
address point (not the CoStar coordinate), during the hackathon access window:

```bash
export VEXCEL_API_KEY=...   # event-provided; never commit or paste in chat
python -m pipeline.vexcel_imagery \
  --target-id bldg_1161264fd5dbc223 \
  --address "3800 BARHAM BLVD LOS ANGELES CA 90068" \
  --latitude 34.14369882488044 --longitude -118.34099924727045 \
  --output-dir data/runtime
python -m scripts.verify_sponsor_overlap --analysis-dir data/runtime
```

This is a single bounded request (one 80 m ortho extract). The second command must then
report `"overlap_found": true`; only then may Barham be described as a real three-source
building. `VEXCEL_API_KEY` was **not** available in the environment where this document was
written, so the lookup has not been performed.

## 3. What the dashboard now shows

- **Stages:** Registration anomaly → Physical-property evidence → Cross-source
  comparison → Uncertainty → Human action.
- **Source labels:** every fusion layer carries a data-class badge: *Public CMS record*,
  *Derived · owners masked*, *Licensed CoStar data*, *Vexcel aerial imagery*.
- **CoStar card:** property type, class, area, floors, occupancy records (current or past),
  unique tenant locations, and an in-app "licensed data" note.
- **Cross-source comparison** (deterministic, built only from tools that actually ran):
  what combining sources clarifies, what stays uncertain, which records to request.
- **Matterport:** a link to Matterport's own hosted Showcase for the sponsor-linked model,
  labelled as showing the property, not any hospice suite. No embed and no SDK.
  Matterport's bot protection blocked validation from the build environment, so **check
  the link on the demo laptop before judging**. If it does not load, do not show it.

## 4. Best CoStar judging demonstration

1. Search `12444 VICTORY` to show the registration anomaly: 5 registrations, "worth a look",
   real Vexcel exterior context, and an honest "no exact CoStar property" card. Without
   property data, building type and area stay unknown, so the building is capped below
   high priority.
2. Search `3800 BARHAM` to show what CoStar adds: a real exact match with 85,831 sq ft, 6
   stories, class B office, and 44 tenant locations. Click **Investigate**. The comparison
   shows about 85,831 sq ft per registration in a multi-tenant office: property data
   *lowers* concern here. This shows CoStar context preventing a false lead.
3. Say: *"Our one CoStar match and our one Vexcel image are different buildings; the
   fused three-source case is a labelled synthetic test."*

## 5. Safest sponsor claims

Supported:
- "We match CMS hospice registration addresses to CoStar property records exactly and show
  property type, area, floors and occupancy-record context beside each building."
- "CoStar context feeds two explainable indicators: building-type fit and area per registration."
- "When CoStar data is missing we say so, and the building cannot reach high priority."
- "Vexcel aerial imagery is shown with retrieval date and provenance as exterior context."
- "Matterport model IDs from the CoStar dataset are linked from the property card."

Do not say:
- That any building was verified across CMS, CoStar and Vexcel together (not yet true).
- That imagery, occupancy records or a 3D tour show whether a hospice operates.
- That the Matterport link was validated (it was not, from the build environment).
- Any fraud-detection accuracy figure.

## 6. Licensing and exposure review

Verified:
- No credentials reach the browser: the only client env var is `NEXT_PUBLIC_API_URL`, and
  the production build's static bundle contains no sponsor key names or endpoints.
- No raw CoStar ZIP/JSONL, occupancy extract or floor plan appears anywhere in git history
  (all branches). `work/`, `cache/` and `data/raw/` are git-ignored.
- Owner masking: 1,559 individual owners appear only as "Individual owner <hash>"; 98
  organizations are named from public CMS records.
- Downloadable case files contain only derived CoStar fields (property ID, type, name, area,
  source line number and row hash), not raw records.

Unresolved; needs a decision from the team and sponsor:
1. **Public repository republication.** `data/runtime/building_analysis.json` (CoStar-derived
   fields for property 248351) and `data/runtime/vexcel/bldg_793ac00ed2ae2571.jpg` are
   committed to a **public** GitHub repository and served by the public API. In-app display
   and screenshots are permitted, but a downloadable file in a public repo may count as
   independent republication. Ask the sponsor, or make the repository private.
2. **Post-hackathon availability.** Access is limited to the hackathon period. Plan to
   remove CoStar-derived context and Vexcel imagery from `data/runtime` (and from git
   history, if required) and redeploy once the event ends. Nothing currently expires
   automatically.
3. **Matterport Showcase content.** The hosted tour may include Matterport's own floor-plan
   view. Linking to Matterport's hosted page is not republishing, but do not screenshot or
   record floor plans for public videos.
4. **Demo videos:** show sponsor data inside the app only; avoid frames that show raw JSON
   responses or the API's `/analysis/buildings/{id}` output for property 248351.
