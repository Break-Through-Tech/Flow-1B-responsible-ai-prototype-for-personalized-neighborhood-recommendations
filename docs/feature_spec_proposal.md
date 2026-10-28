# Proposed feature definitions

October 21, 2026. For team review; no source or new feature is approved by this document. Provided features remain the default. Proposed owners follow existing workstreams and need confirmation.

| Tag | User-facing meaning to confirm | Preferred measurement to investigate | Current candidate / limitation | Proposed owner |
|---|---|---|---|---|
| transit | Practical access to useful public transit | GTFS stops and service frequency, with documented spatial aggregation | ACS commute/no-car shares describe resident behavior, not service access | Amelie/Joana; Om/Anna validate |
| social | Access to places for social activities | Restaurants/bars and arts venues per land area | Business Patterns uses mailing ZIPs, not ZCTA boundaries; venues do not measure belonging | Data owners; Nadia supplies separate evidence |
| walkable | Ability to reach everyday destinations on foot | Pedestrian access to ordinary destinations | Walk-to-work share covers workers/work trips only | Data owners; Anna checks independence from social |
| quiet | Low environmental noise at relevant times | Dated noise/traffic measurements with time coverage | Unresolved; low density or owner occupancy does not establish quietness | Advisor/Om define; data owners investigate |
| pet_friendly | Access to usable pet amenities | Dog parks and documented pet facilities | Constant starter value 0.6 provides no ranking signal or building-policy evidence | Advisor decides retention; data owners investigate |
| co_living | Fit for explicitly requested shared housing | Approved housing-mode data with availability limitations | Existing score provenance undocumented; area rents are not room prices | Advisor/data owners; Om implements contract |

Land area in `data/zcta_land_area.csv` remains useful as a denominator for the experiment even if density prototype code is removed.

## Data contract before implementation

- One five-character ZIP/ZCTA key per row; raw measure, units, denominator, source period/URL, geography type, transformation version, missingness reason, and quality flags.
- Document mailing-ZIP/ZCTA alignment. Equal five-digit strings do not establish equal boundaries.
- Preserve raw measurements alongside scaled values. If percentile scaling is selected, freeze the comparison population and tie rule in the feature version.
- Missing measurements remain unknown. Report requested-feature coverage; preserve the known, unscaled rent hard filter.
- Measure dependence between candidates. Do not define quiet as one minus social or equate walkable with social.
- Expose feature versions and measurement limitations. Review evidence stays separate from ranking and preserves source/demo/polarity fields.

## Decisions required

1. Advisor/team: define quiet; retain or remove pet_friendly without a useful measurement.
2. Advisor/data owners: approve sources and whether any resident-behavior measures are appropriate. None are promoted here.
3. Data owners: approve geographic alignment, periods, missingness, and transformations.
4. Anna/advisor: resolve mean-versus-cosine requirements in #11 and ARCHITECTURE.md; preserve both baselines.
5. Amelie/advisor: provide independent development/holdout labels, including suburban and conflicting-priority requests. Five fixtures cannot choose among 720 candidates.

## Future implementation gates

Keep `provided` as default until adoption. Include reproducible extraction or small documented snapshots with hashes. Test percentile ties, missing/invalid denominators, missing requested inputs, and constant features. Verify social-plus-quiet cannot cancel by construction. Report all profile results and regressions, coverage, ties, and budget compliance; never claim generalization from five fixtures. Unapproved features retain documented limitations rather than being silently replaced.

## Experiment check

Reran `pick.py` from the repository location on October 21. With proposed transit/social/walkable and provided quiet: P@3 0.53, P@5 0.32, MRR 0.71. Owner-occupancy quiet yields MRR 0.73 but is not adopted. P4 remains weak. The experiment and Census inputs are preserved untracked; no source files were modified.

## Work that can proceed now

Resolve the NLP review findings, draft the evidence adapter with Daniel/Azibator, and prepare independent evaluation labels with Amelie. These do not require choosing an unapproved ranking feature.
