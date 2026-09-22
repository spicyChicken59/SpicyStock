# Fourteen retained mechanical A+ assessments — 22 September 2026

Generated from the [claim inventory](2026-09-22-reader-downgrade-audit.json) by
`tools/audit_reader_downgrades.py`. See the [audit](2026-09-22-reader-downgrade-audit.md)
for source hierarchy, historical contracts, limitations and verification.

Each revision is distinct. Check statuses and A+ flags below are recorded mechanical
evidence, not new grades. Reader text is quoted historical model assertion, not source
authority. All fourteen have no veto, red regime, no plan and no ticket.
The JSON retains exact threshold strings, rule identities and provenance hashes.

## 2026-09-11 · DGX · 7380a97

Publication `7380a97605c7f16eb902421486c491a95b957cd7`; inventory index 2; discovery **dollar**.
Mechanical **10.0/10, A+ tally 4** → recorded reader **3.5 / skip** → final **skip**.
Rules `015229b909b7`; prompt blob `b4c7ccb60da18c3f196dfb74178e7e6a344d5c9d`.
Pre-provenance: checklist and reply retained; exact chart, frame and request unavailable.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=0; prior_day_pct=-1.83 |
| L | PASS | true | er=0.47; r2=0.83; leg_sessions=48; leg_gain_pct=26.4 |
| Y | PASS | true | breakouts_in_move=0; sessions_since_move_start=57; gain_since_move_start_pct=21.4 |
| N | PASS | false | prior_day_pct=-1.83; prior_range_pct=3.4; negative=true; narrow=false; median_range_pct=1.8 |
| C | PASS | false | base_sessions=9; breakdowns=0; bursts_in_base=0; giveback=0.34; tightness=0.97; base_volume_vs_leg=0.98; base_volume_vs_avg=0.98 |
| H | PASS | true | close_pos=0.98; close_above_open=true |
| RE | FAIL | false | vs_prior_5=0.74; vs_prior_10=0.74; bar_range_pct=2.5 |
| VOL | FAIL | false | volume_vs_prior=0.92; volume_vs_avg50=1.04; volume_rank_60=17; cv_required=false |

**Exact recorded reader text**

reason:

> The burst bar gains only 1.68% — well below the 4% minimum Bonde requires for a range-expansion day — and the metrics confirm it: RE fails because the bar is not even the widest of the last five sessions, and volume actually came in below the prior session. The shaded base itself shows multiple wide overlapping red and green bars across a roughly 18-point range (~8% of price), which is loose rather than tight, and the consolidation sits below the prior highs rather than holding near them. These are not cosmetic flaws; the burst bar simply does not qualify as a burst.

key_risk:

> The base is a rolling distribution below the August high, not a tight coil, so any continuation attempt lacks the compressed energy the setup requires.

entry_note:

> Skip at the open regardless of price action — the burst bar itself does not meet the 4% range-expansion threshold, so there is no valid entry trigger to act on.

| Individual claim | Evidence status | Basis |
|---|---|---|
| RE fails its recorded quality test. | SUPPORTED | {"status": "FAIL", "threshold": "today's range over the largest of the prior 5 >= 1.0 (A+: also over the prior 10)", "values": {"bar_range_pct": 2.5, "vs_prior_10": 0.74, "vs_prior_5": 0.74}} |
| VOL fails its recorded quality test. | SUPPORTED | {"status": "FAIL", "threshold": "volume > prior session (A+: rank <= 3 of the last 60); a base over 21 sessions also needs >= 1.5x the 50-session average", "values": {"cv_required": false, "volume_rank_60": 17, "volume_vs_avg50": 1.04, "volume_vs_prior": 0.92}} |
| A Dollar-only candidate must meet the separate 4% discovery minimum (or its gain alone is disqualifying). | CONTRADICTED | Historical strategy opening imposed 4% universally, but historical method/scans admitted Dollar separately. Conflict is recorded, not silently reconciled. #68 removed the stale prompt; #72 later verified primary Dollar authorship. |
| The described base has adverse shape (overlap, chop, decline or distribution). | UNVERIFIABLE | Pre-provenance chart/source frame unavailable; C proxy is not proof of visual shape. |

**Offline comparison with verified main:** its existing discovery tripwire rejects these historical fields: reason, entry_note.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.

## 2026-09-11 · SSNC · 7380a97

Publication `7380a97605c7f16eb902421486c491a95b957cd7`; inventory index 4; discovery **dollar**.
Mechanical **10.0/10, A+ tally 4** → recorded reader **4.5 / skip** → final **skip**.
Rules `015229b909b7`; prompt blob `b4c7ccb60da18c3f196dfb74178e7e6a344d5c9d`.
Pre-provenance: checklist and reply retained; exact chart, frame and request unavailable.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=0; prior_day_pct=-0.53 |
| L | PASS | true | er=0.44; r2=0.88; leg_sessions=47; leg_gain_pct=36.4 |
| Y | PASS | true | breakouts_in_move=0; sessions_since_move_start=51; gain_since_move_start_pct=29.4 |
| N | PASS | true | prior_day_pct=-0.53; prior_range_pct=0.9; negative=true; narrow=true; median_range_pct=2.0 |
| C | PASS | false | base_sessions=4; breakdowns=0; bursts_in_base=0; giveback=0.26; tightness=0.87; base_volume_vs_leg=0.98; base_volume_vs_avg=0.98 |
| H | PASS | false | close_pos=0.87; close_above_open=true |
| RE | FAIL | false | vs_prior_5=0.67; vs_prior_10=0.67; bar_range_pct=2.0 |
| VOL | PASS | false | volume_vs_prior=1.12; volume_vs_avg50=0.82; volume_rank_60=42; cv_required=false |

**Exact recorded reader text**

reason:

> The burst bar gains only 1.71% and the RE criterion hard-fails — the bar is not the widest of the last five sessions, which is the core mechanical requirement for a momentum burst. Looking at the chart, the shaded base sits at the top of a 47-session, 36% leg that has already stalled into a choppy, overlapping cluster of red and green bars near the highs, and the burst bar itself is a modest up-day inside that chop rather than a clean range-expansion out of a tight shelf. The consolidation box shows several wide red bars and overlapping closes that undercut the 'tight and orderly' standard, and the name has already rolled off its peak toward $80 with the burst closing below the prior consolidation highs.

key_risk:

> The prior leg is mature and the price is already pulling back from the $85 area, meaning any continuation attempt faces immediate overhead supply from the recent distribution cluster.

entry_note:

> Skip if the open is below today's burst close of $80.27 or if the first 30 minutes show no ability to reclaim $81, confirming the rollover rather than a resumption.

| Individual claim | Evidence status | Basis |
|---|---|---|
| RE fails its recorded quality test. | SUPPORTED | {"status": "FAIL", "threshold": "today's range over the largest of the prior 5 >= 1.0 (A+: also over the prior 10)", "values": {"bar_range_pct": 2.0, "vs_prior_10": 0.67, "vs_prior_5": 0.67}} |
| The described base has adverse shape (overlap, chop, decline or distribution). | UNVERIFIABLE | Pre-provenance chart/source frame unavailable; C proxy is not proof of visual shape. |
| Measured volume rank/average context is too weak for a convincing burst. | PARTIALLY SUPPORTED | {"limit": "Source supports volume context, but no extra hard cutoff at this observed rank/average and no direct institutional-identity evidence.", "measurements": {"cv_required": false, "volume_rank_60": 42, "volume_vs_avg50": 0.82, "volume_vs_prior": 1.12}} |

**Offline comparison with verified main:** its discovery tripwire does not reject this historical response.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.

## 2026-09-11 · DGX · ece47f1

Publication `ece47f1e34ab4b795a79be7674355409ce5aaf8e`; inventory index 15; discovery **dollar**.
Mechanical **10.0/10, A+ tally 4** → recorded reader **3.5 / skip** → final **skip**.
Rules `2fe10c171341`; prompt blob `b4c7ccb60da18c3f196dfb74178e7e6a344d5c9d`.
Pre-provenance: checklist and reply retained; exact chart, frame and request unavailable.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=0; prior_day_pct=-1.83 |
| L | PASS | true | er=0.47; r2=0.83; leg_sessions=48; leg_gain_pct=26.4 |
| Y | PASS | true | breakouts_in_move=0; sessions_since_move_start=57; gain_since_move_start_pct=21.4 |
| N | PASS | false | prior_day_pct=-1.83; prior_range_pct=3.4; negative=true; narrow=false; median_range_pct=1.8 |
| C | PASS | false | base_sessions=9; breakdowns=0; bursts_in_base=0; giveback=0.34; tightness=0.97; base_volume_vs_leg=0.98; base_volume_vs_avg=0.98 |
| H | PASS | true | close_pos=0.98; close_above_open=true |
| RE | FAIL | false | vs_prior_5=0.74; vs_prior_10=0.74; bar_range_pct=2.5 |
| VOL | FAIL | false | volume_vs_prior=0.92; volume_vs_avg50=1.04; volume_rank_60=17; cv_required=false |

**Exact recorded reader text**

reason:

> The burst bar gains only 1.68% — well below the 4% minimum Bonde requires for a range-expansion day — and the metrics confirm it: RE fails because the bar is not even the widest of the last five sessions, and VOL fails because volume did not exceed the prior session. The shaded base itself shows multiple wide overlapping red and green bars spanning roughly 18 points (~8% of price), which is loose rather than tight, and the consolidation sits below the prior highs rather than holding near them. These three failures together — sub-4% burst, no range expansion, no volume confirmation — mean there is no burst here by definition.

key_risk:

> The stock is already rolling over from its highs with a series of lower closes inside the base, and a sub-4% 'burst' on below-average volume offers no edge for a 3–5 day momentum trade.

entry_note:

> Skip regardless of the open — the burst bar itself does not qualify under the 4% minimum gain rule, so no open price rescues this setup.

| Individual claim | Evidence status | Basis |
|---|---|---|
| RE fails its recorded quality test. | SUPPORTED | {"status": "FAIL", "threshold": "today's range over the largest of the prior 5 >= 1.0 (A+: also over the prior 10)", "values": {"bar_range_pct": 2.5, "vs_prior_10": 0.74, "vs_prior_5": 0.74}} |
| VOL fails its recorded quality test. | SUPPORTED | {"status": "FAIL", "threshold": "volume > prior session (A+: rank <= 3 of the last 60); a base over 21 sessions also needs >= 1.5x the 50-session average", "values": {"cv_required": false, "volume_rank_60": 17, "volume_vs_avg50": 1.04, "volume_vs_prior": 0.92}} |
| A Dollar-only candidate must meet the separate 4% discovery minimum (or its gain alone is disqualifying). | CONTRADICTED | Historical strategy opening imposed 4% universally, but historical method/scans admitted Dollar separately. Conflict is recorded, not silently reconciled. #68 removed the stale prompt; #72 later verified primary Dollar authorship. |
| The described base has adverse shape (overlap, chop, decline or distribution). | UNVERIFIABLE | Pre-provenance chart/source frame unavailable; C proxy is not proof of visual shape. |
| Signal volume is below average. | CONTRADICTED | VOL volume_vs_avg50=1.04; below prior=0.92 is a different fact. |

**Offline comparison with verified main:** its existing discovery tripwire rejects these historical fields: reason, key_risk, entry_note.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.

## 2026-09-11 · SSNC · ece47f1

Publication `ece47f1e34ab4b795a79be7674355409ce5aaf8e`; inventory index 17; discovery **dollar**.
Mechanical **10.0/10, A+ tally 4** → recorded reader **4.5 / skip** → final **skip**.
Rules `2fe10c171341`; prompt blob `b4c7ccb60da18c3f196dfb74178e7e6a344d5c9d`.
Pre-provenance: checklist and reply retained; exact chart, frame and request unavailable.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=0; prior_day_pct=-0.53 |
| L | PASS | true | er=0.44; r2=0.88; leg_sessions=47; leg_gain_pct=36.4 |
| Y | PASS | true | breakouts_in_move=0; sessions_since_move_start=51; gain_since_move_start_pct=29.4 |
| N | PASS | true | prior_day_pct=-0.53; prior_range_pct=0.9; negative=true; narrow=true; median_range_pct=2.0 |
| C | PASS | false | base_sessions=4; breakdowns=0; bursts_in_base=0; giveback=0.26; tightness=0.87; base_volume_vs_leg=0.98; base_volume_vs_avg=0.98 |
| H | PASS | false | close_pos=0.87; close_above_open=true |
| RE | FAIL | false | vs_prior_5=0.67; vs_prior_10=0.67; bar_range_pct=2.0 |
| VOL | PASS | false | volume_vs_prior=1.12; volume_vs_avg50=0.82; volume_rank_60=42; cv_required=false |

**Exact recorded reader text**

reason:

> The burst bar gains only 1.71% and the RE criterion hard-fails — the bar is not the widest of the last five sessions, which is the core mechanical requirement for a momentum burst. Looking at the chart, the shaded consolidation sits at the top of a 47-session, 36% advance, and the last several weeks show a cluster of overlapping red and green bars churning sideways-to-down from the ~$85 peak, with the burst bar itself closing at $80.27 — well off the recent highs and inside a visible distribution zone. The 'burst' is really a one-day bounce inside a topping structure, not a range-expansion breakout from a tight base.

key_risk:

> The stock is breaking down from a multi-week top with several large red bars visible in the consolidation box; a bounce here is more likely to fail into the prior decline than launch a 3–5 day momentum burst.

entry_note:

> Skip regardless of open price — the RE failure and the topping chart structure disqualify this setup entirely.

| Individual claim | Evidence status | Basis |
|---|---|---|
| RE fails its recorded quality test. | SUPPORTED | {"status": "FAIL", "threshold": "today's range over the largest of the prior 5 >= 1.0 (A+: also over the prior 10)", "values": {"bar_range_pct": 2.0, "vs_prior_10": 0.67, "vs_prior_5": 0.67}} |
| The described base has adverse shape (overlap, chop, decline or distribution). | UNVERIFIABLE | Pre-provenance chart/source frame unavailable; C proxy is not proof of visual shape. |
| Measured volume rank/average context is too weak for a convincing burst. | PARTIALLY SUPPORTED | {"limit": "Source supports volume context, but no extra hard cutoff at this observed rank/average and no direct institutional-identity evidence.", "measurements": {"cv_required": false, "volume_rank_60": 42, "volume_vs_avg50": 0.82, "volume_vs_prior": 1.12}} |

**Offline comparison with verified main:** its discovery tripwire does not reject this historical response.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.

## 2026-09-14 · GKOS · fbaed5c

Publication `fbaed5cdc43a84755f61840ba9e1fc74379c797d`; inventory index 31; discovery **dollar**.
Mechanical **10.0/10, A+ tally 4** → recorded reader **3.5 / skip** → final **skip**.
Rules `953f37fb787a`; prompt blob `b4c7ccb60da18c3f196dfb74178e7e6a344d5c9d`.
Pre-provenance: checklist and reply retained; exact chart, frame and request unavailable.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=0; prior_day_pct=-1.84 |
| L | PASS | true | er=0.5; r2=0.94; leg_sessions=57; leg_gain_pct=79.3 |
| Y | PASS | true | breakouts_in_move=0; sessions_since_move_start=1; gain_since_move_start_pct=2.3 |
| N | PASS | false | prior_day_pct=-1.84; prior_range_pct=5.2; negative=true; narrow=false; median_range_pct=2.8 |
| C | PASS | false | base_sessions=15; breakdowns=1; bursts_in_base=1; giveback=0.27; tightness=0.79; base_volume_vs_leg=0.68; base_volume_vs_avg=0.82 |
| H | PASS | true | close_pos=0.95; close_above_open=true |
| RE | FAIL | false | vs_prior_5=0.52; vs_prior_10=0.52; bar_range_pct=3.5 |
| VOL | PASS | false | volume_vs_prior=1.64; volume_vs_avg50=1.18; volume_rank_60=14; cv_required=false |

**Exact recorded reader text**

reason:

> The burst bar gains only 2.3% and the range expansion explicitly fails — it is not the widest bar of the last five sessions, which is the mechanical heart of the setup. Looking at the chart, the shaded base sits well below the prior August highs (~191), meaning the stock has already given back roughly 12–15% from its peak and the 'burst' is a weak bounce inside a visible downtrend from those highs, not a breakout from a tight shelf at highs. The base itself shows multiple wide overlapping red bars with the price drifting lower throughout, which is a downtrend with a bounce rather than an orderly consolidation.

key_risk:

> The stock is in a declining channel from its August peak with the burst bar failing range expansion, making this a low-probability bounce rather than a momentum burst.

entry_note:

> Skip if tomorrow opens below today's burst close of 171.09 or if the first 30 minutes show any continuation of the recent downward drift without a clear surge in volume.

| Individual claim | Evidence status | Basis |
|---|---|---|
| RE fails its recorded quality test. | SUPPORTED | {"status": "FAIL", "threshold": "today's range over the largest of the prior 5 >= 1.0 (A+: also over the prior 10)", "values": {"bar_range_pct": 3.5, "vs_prior_10": 0.52, "vs_prior_5": 0.52}} |
| The described base has adverse shape (overlap, chop, decline or distribution). | UNVERIFIABLE | Pre-provenance chart/source frame unavailable; C proxy is not proof of visual shape. |

**Offline comparison with verified main:** its discovery tripwire does not reject this historical response.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.

## 2026-09-14 · ROKU · fbaed5c

Publication `fbaed5cdc43a84755f61840ba9e1fc74379c797d`; inventory index 32; discovery **dollar**.
Mechanical **10.0/10, A+ tally 4** → recorded reader **4.5 / skip** → final **skip**.
Rules `953f37fb787a`; prompt blob `b4c7ccb60da18c3f196dfb74178e7e6a344d5c9d`.
Pre-provenance: checklist and reply retained; exact chart, frame and request unavailable.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=2; prior_day_pct=0.53 |
| L | PASS | true | er=0.5; r2=0.77; leg_sessions=53; leg_gain_pct=36.6 |
| Y | PASS | true | breakouts_in_move=0; sessions_since_move_start=55; gain_since_move_start_pct=16.9 |
| N | PASS | false | prior_day_pct=0.53; prior_range_pct=0.6; negative=false; narrow=true; median_range_pct=1.2 |
| C | PASS | true | base_sessions=12; breakdowns=0; bursts_in_base=0; giveback=0.18; tightness=0.59; base_volume_vs_leg=0.54; base_volume_vs_avg=0.98 |
| H | PASS | false | close_pos=0.88; close_above_open=true |
| RE | PASS | false | vs_prior_5=1.18; vs_prior_10=0.83; bar_range_pct=2.0 |
| VOL | PASS | false | volume_vs_prior=1.18; volume_vs_avg50=0.64; volume_rank_60=53; cv_required=false |

**Exact recorded reader text**

reason:

> The burst bar gains only 1.63%, well below the 4% minimum Bonde requires for a range-expansion day to qualify as a burst — this is not a momentum burst, it is a routine up day inside a choppy consolidation zone. The base itself shows multiple overlapping red and green bars of similar size with no clear compression toward a breakout point, and the last several sessions in the shaded box are visibly whippy with bars crossing each other repeatedly. Volume on the burst day ranks 53rd of the last 60 sessions and comes in at only 0.64x the 50-session average, confirming there is no institutional conviction behind this move.

key_risk:

> The 'burst' is too small and too low-volume to signal genuine demand absorption; the stock is more likely to continue churning sideways or rolling over within the range.

entry_note:

> Skip at the open regardless of price action — the burst-day gain of 1.63% does not meet the 4% threshold and no gap or volume surge at the open can retroactively validate yesterday's bar as a qualifying burst.

| Individual claim | Evidence status | Basis |
|---|---|---|
| A Dollar-only candidate must meet the separate 4% discovery minimum (or its gain alone is disqualifying). | CONTRADICTED | Historical strategy opening imposed 4% universally, but historical method/scans admitted Dollar separately. Conflict is recorded, not silently reconciled. #68 removed the stale prompt; #72 later verified primary Dollar authorship. |
| The described base has adverse shape (overlap, chop, decline or distribution). | UNVERIFIABLE | Pre-provenance chart/source frame unavailable; C proxy is not proof of visual shape. |
| Measured volume rank/average context is too weak for a convincing burst. | PARTIALLY SUPPORTED | {"limit": "Source supports volume context, but no extra hard cutoff at this observed rank/average and no direct institutional-identity evidence.", "measurements": {"cv_required": false, "volume_rank_60": 53, "volume_vs_avg50": 0.64, "volume_vs_prior": 1.18}} |

**Offline comparison with verified main:** its existing discovery tripwire rejects these historical fields: reason, entry_note.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.

## 2026-09-15 · RGLD · 442db48

Publication `442db489342660d7588d16dcc18e6c126187c1e6`; inventory index 40; discovery **dollar**.
Mechanical **10.0/10, A+ tally 4** → recorded reader **4.5 / skip** → final **skip**.
Rules `e1032aa5ee21`; prompt blob `b4c7ccb60da18c3f196dfb74178e7e6a344d5c9d`.
Pre-provenance: checklist and reply retained; exact chart, frame and request unavailable.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=0; prior_day_pct=-1.56 |
| L | PASS | true | er=0.53; r2=0.93; leg_sessions=30; leg_gain_pct=40.3 |
| Y | PASS | false | breakouts_in_move=1; sessions_since_move_start=40; gain_since_move_start_pct=34.1 |
| N | PASS | true | prior_day_pct=-1.56; prior_range_pct=2.2; negative=true; narrow=false; median_range_pct=2.5 |
| C | PASS | false | base_sessions=10; breakdowns=0; bursts_in_base=0; giveback=0.32; tightness=0.83; base_volume_vs_leg=0.78; base_volume_vs_avg=0.83 |
| H | PASS | true | close_pos=0.94; close_above_open=true |
| RE | PASS | false | vs_prior_5=1.0; vs_prior_10=0.91; bar_range_pct=3.0 |
| VOL | PASS | false | volume_vs_prior=1.02; volume_vs_avg50=1.12; volume_rank_60=21; cv_required=false |

**Exact recorded reader text**

reason:

> The burst bar gains only 1.14% — well below the 4% minimum range-expansion threshold the method requires for a burst day, and the bar range of 3.0% is the smallest in the visible consolidation zone rather than clearly larger than the prior 5–10 bars. The base itself shows several wide, overlapping red and green candles with bodies that span 2–3% of price, and the last few sessions inside the shaded box drift visibly lower, making this a loose, declining consolidation rather than a tight flat shelf. Volume rank of 21 out of 60 sessions is mediocre and volume is barely above the prior day (1.02x), so there is no conviction behind the move.

key_risk:

> The 'burst' is a routine inside-day bounce off a declining base, not a range-expansion breakout, so there is no momentum to sell into over the next 3–5 days.

entry_note:

> Skip regardless of open price — the burst day itself does not qualify under the 4% gain and range-expansion rules, so no open-price condition rescues this setup.

| Individual claim | Evidence status | Basis |
|---|---|---|
| A Dollar-only candidate must meet the separate 4% discovery minimum (or its gain alone is disqualifying). | CONTRADICTED | Historical strategy opening imposed 4% universally, but historical method/scans admitted Dollar separately. Conflict is recorded, not silently reconciled. #68 removed the stale prompt; #72 later verified primary Dollar authorship. |
| The described base has adverse shape (overlap, chop, decline or distribution). | UNVERIFIABLE | Pre-provenance chart/source frame unavailable; C proxy is not proof of visual shape. |
| Measured volume rank/average context is too weak for a convincing burst. | PARTIALLY SUPPORTED | {"limit": "Source supports volume context, but no extra hard cutoff at this observed rank/average and no direct institutional-identity evidence.", "measurements": {"cv_required": false, "volume_rank_60": 21, "volume_vs_avg50": 1.12, "volume_vs_prior": 1.02}} |
| The 3.0% signal range is the smallest in the visible consolidation. | CONTRADICTED | RE vs_prior_5=1.0 and status PASS; vs_prior_10=0.91. It is not smaller than the prior five maximum on the decision grid. |

**Offline comparison with verified main:** its existing discovery tripwire rejects these historical fields: reason, entry_note.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.

## 2026-09-18 · IDT · 8387cce

Publication `8387ccedae22fbf30ddebdb6f52e1e42326a7ec5`; inventory index 73; discovery **dollar**.
Mechanical **9.0/10, A+ tally 5** → recorded reader **7.5 / B** → final **B**.
Rules `e2cace0f7bc6`; prompt blob `3da7500efe0a269283926a60b4426943a6e34139`.
Source frame/chart/request identity retained; original source replay available.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=0; prior_day_pct=-0.72 |
| L | PASS | true | er=0.45; r2=0.85; leg_sessions=60; leg_gain_pct=35.8 |
| Y | PASS | true | breakouts_in_move=0; sessions_since_move_start=60; gain_since_move_start_pct=25.4 |
| N | PASS | true | prior_day_pct=-0.72; prior_range_pct=2.2; negative=true; narrow=false; median_range_pct=2.6 |
| C | PARTIAL | false | base_sessions=2; breakdowns=0; bursts_in_base=0; giveback=0.18; tightness=0.95; base_volume_vs_leg=1.19; base_volume_vs_avg=1.28 |
| H | PASS | false | close_pos=0.87; close_above_open=true |
| RE | PASS | false | vs_prior_5=1.03; vs_prior_10=0.82; bar_range_pct=3.1 |
| VOL | PASS | true | volume_vs_prior=4.34; volume_vs_avg50=6.44; volume_rank_60=1; cv_required=false |

**Exact recorded reader text**

reason:

> The burst bar itself is honest — a clean green candle closing near its high on volume that is the highest in 60 sessions — and the prior leg is a smooth, persistent staircase over 60 sessions with no visible chop. However, the base is only 2 sessions, which is visually confirmed: there is no real consolidation box to speak of, just a one-day pullback followed by today's move, and the chart shows the stock has been grinding sideways-to-slightly-lower for several weeks near the $68–72 range, making the 'base' indistinguishable from the broader chop in that zone. The C criterion is PARTIAL for this reason, and the chart does not rescue it — two bars is not a consolidation.

key_risk:

> The stock has been range-bound near $68–72 for roughly six weeks with multiple failed attempts to push higher, meaning overhead supply from that congestion zone is the primary threat to follow-through.

entry_note:

> Skip if tomorrow opens above the $72.12 base high (gap over the ceiling) or if the first 30 minutes show weak price action with volume fading back toward the prior session's pace.

| Individual claim | Evidence status | Basis |
|---|---|---|
| The described base has adverse shape (overlap, chop, decline or distribution). | PARTIALLY SUPPORTED | Retained chart inspected; the source permits shape review, but loose/orderly is qualitative and the reader does not identify exact bars. No invented numerical tightness gate is endorsed. |
| The selected base has two sessions and C is PARTIAL. | SUPPORTED | Recorded C base_sessions=2, status PARTIAL; the 3-session pass minimum is the actual contract. |
| Two bars are categorically no consolidation under any reading. | PARTIALLY SUPPORTED | Short-base concern is authorized; historical code explicitly gives two bars partial credit, not a veto. |
| The stock was range-bound at 68–72 for six weeks. | CONTRADICTED | Retained chart/source show the advance from lower prices during that interval; the last six weeks were not confined to that band. |
| 72.12 is the entry ceiling. | UNSUPPORTED | 72.12 is the measured base high; no plan/ticket/ceiling was computed in red regime. |

**Offline comparison with verified main:** its discovery tripwire does not reject this historical response.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.

## 2026-09-21 · MRK · 25eb5b2

Publication `25eb5b2688a3ba1ceecc01083a7cb6046cc62aea`; inventory index 86; discovery **dollar**.
Mechanical **10.0/10, A+ tally 4** → recorded reader **5.5 / C** → final **C**.
Rules `d5d62f525e0f`; prompt blob `3da7500efe0a269283926a60b4426943a6e34139`.
Source frame/chart/request identity retained; original source replay available.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=0; prior_day_pct=-0.19 |
| L | PASS | true | er=0.42; r2=0.63; leg_sessions=47; leg_gain_pct=37.4 |
| Y | PASS | false | breakouts_in_move=1; sessions_since_move_start=48; gain_since_move_start_pct=23.8 |
| N | PASS | true | prior_day_pct=-0.19; prior_range_pct=1.4; negative=true; narrow=true; median_range_pct=1.9 |
| C | PASS | false | base_sessions=17; breakdowns=0; bursts_in_base=0; giveback=0.32; tightness=0.7; base_volume_vs_leg=0.92; base_volume_vs_avg=0.98 |
| H | PASS | false | close_pos=0.8; close_above_open=true |
| RE | PASS | true | vs_prior_5=1.57; vs_prior_10=1.22; bar_range_pct=3.3 |
| VOL | FAIL | false | volume_vs_prior=0.26; volume_vs_avg50=0.79; volume_rank_60=38; cv_required=false |

**Exact recorded reader text**

reason:

> The base box on the chart shows 17 sessions of wide, overlapping red and green bars with multiple wicks piercing both the upper and lower boundaries — this is a loose, choppy consolidation, not the tight orderly shelf Bonde requires. Volume on the burst bar is only 26% of the prior session's and 79% of the 50-day average, a VOL FAIL that is visually confirmed by the tiny volume bar relative to the surrounding sessions. The prior leg's linearity is borderline (ER 0.42, R² 0.63) and the chart shows the move stalled and churned for nearly a month at the highs before this base formed, suggesting distribution rather than a clean pause.

key_risk:

> The base is visually loose with overlapping bars and the burst occurred on dramatically lower volume than the prior session, meaning institutional participation is absent on the breakout day.

entry_note:

> Skip if tomorrow opens below today's close of 149.50 or if the first 30 minutes show no follow-through buying above the entry ceiling.

| Individual claim | Evidence status | Basis |
|---|---|---|
| VOL fails its recorded quality test. | SUPPORTED | {"status": "FAIL", "threshold": "volume > prior session (A+: rank <= 3 of the last 60); a base over 21 sessions also needs >= 1.5x the 50-session average", "values": {"cv_required": false, "volume_rank_60": 38, "volume_vs_avg50": 0.79, "volume_vs_prior": 0.26}} |
| The described base has adverse shape (overlap, chop, decline or distribution). | PARTIALLY SUPPORTED | Retained chart inspected; the source permits shape review, but loose/orderly is qualitative and the reader does not identify exact bars. No invented numerical tightness gate is endorsed. |
| Multiple base wicks pierce both measured box boundaries. | CONTRADICTED | The measured box high/low bound the retained base bars; no lower-bound breach in the base. |
| ER=0.42 and R2=0.63 are borderline. | PARTIALLY SUPPORTED | Both values are accurately quoted and both pass; borderline is qualitative, not another threshold. |
| Institutional participation is absent. | UNVERIFIABLE | Lower relative volume does not identify participant types or prove their absence. |

**Offline comparison with verified main:** its discovery tripwire does not reject this historical response.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.

## 2026-09-21 · WBD · 25eb5b2

Publication `25eb5b2688a3ba1ceecc01083a7cb6046cc62aea`; inventory index 87; discovery **both**.
Mechanical **10.0/10, A+ tally 6** → recorded reader **5.0 / C** → final **C**.
Rules `d5d62f525e0f`; prompt blob `3da7500efe0a269283926a60b4426943a6e34139`.
Source frame/chart/request identity retained; original source replay available.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=0; prior_day_pct=-1.56 |
| L | PASS | true | er=0.6; r2=0.95; leg_sessions=24; leg_gain_pct=14.2 |
| Y | PASS | true | breakouts_in_move=0; sessions_since_move_start=39; gain_since_move_start_pct=21.8 |
| N | PASS | false | prior_day_pct=-1.56; prior_range_pct=1.4; negative=true; narrow=true; median_range_pct=1.0 |
| C | PASS | false | base_sessions=15; breakdowns=0; bursts_in_base=0; giveback=0.33; tightness=0.59; base_volume_vs_leg=0.92; base_volume_vs_avg=0.88 |
| H | PASS | true | close_pos=0.91; close_above_open=true |
| RE | PASS | true | vs_prior_5=2.93; vs_prior_10=1.78; bar_range_pct=4.1 |
| VOL | PASS | true | volume_vs_prior=5.29; volume_vs_avg50=10.77; volume_rank_60=1; cv_required=false |

**Exact recorded reader text**

reason:

> The burst bar is almost entirely an overnight gap (gap_pct 7.1% of the 10.79% gain, leaving only ~3.7% of intraday move), meaning the actionable range expansion happened in pre-market, not during the session — this is the hallmark of an Episodic Pivot or news-driven gap, not a clean momentum burst out of a base. The base itself (shaded box) shows multiple overlapping red and green bars with the price drifting lower through the consolidation period, giving it a mild downtrend character rather than a tight, flat coil. Combined with a 10.79% single-day gain that is near the 15% danger threshold and a base giveback of 0.33 (right at the A+ limit), the gap-dominated bar makes the entry plan structurally wrong — the stop at the burst-day low is now far below the open, and the move is largely spent before the open.

key_risk:

> The majority of the gain was a pre-market gap, so buying at the open on day 1 means chasing a move that already happened, with a wide stop and little intraday edge.

entry_note:

> Skip if the stock opens anywhere near or below the prior close (~27.80) or if it gaps further above 31 without a clean first-30-minute consolidation near the high.

| Individual claim | Evidence status | Basis |
|---|---|---|
| The described base has adverse shape (overlap, chop, decline or distribution). | PARTIALLY SUPPORTED | Retained chart inspected; the source permits shape review, but loose/orderly is qualitative and the reader does not identify exact bars. No invented numerical tightness gate is endorsed. |
| Most close-to-close gain occurred in the overnight gap. | SUPPORTED | gap_pct=7.1 vs gain_pct=10.79; source/chart retain open=29.76, prior close=27.80, close=30.80. |
| The actionable high-low range expansion happened before the session. | CONTRADICTED | The overnight gap is not part of high-low range. The quoted 3.7 percentage-point contribution is on the prior-close denominator; actual intraday high-low range is 4.1% of close. |
| A gap proves an EP/news catalyst. | UNVERIFIABLE | The prompt permits flagging an apparent catalyst; no news/catalyst source is retained. |
| 10.79% is disqualifying because near 15%. | CONTRADICTED | 10.79<15, and the high-gain note has no grade vote. |
| 0.33 is at the A+ giveback limit. | CONTRADICTED | A+ giveback limit is 0.25; normal pass limit 0.34. |
| The published stop/entry plan is structurally wrong. | UNVERIFIABLE | Red regime contains no plan, stop, or ticket to validate; chart-review concern is not evidence of a published plan defect. |

**Offline comparison with verified main:** its discovery tripwire does not reject this historical response.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.

## 2026-09-21 · PTGX · 25eb5b2

Publication `25eb5b2688a3ba1ceecc01083a7cb6046cc62aea`; inventory index 94; discovery **dollar**.
Mechanical **9.0/10, A+ tally 4** → recorded reader **4.5 / skip** → final **skip**.
Rules `d5d62f525e0f`; prompt blob `3da7500efe0a269283926a60b4426943a6e34139`.
Source frame/chart/request identity retained; original source replay available.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=0; prior_day_pct=-0.49 |
| L | PASS | false | er=0.38; r2=0.88; leg_sessions=55; leg_gain_pct=66.2 |
| Y | PASS | true | breakouts_in_move=0; sessions_since_move_start=3; gain_since_move_start_pct=1.5 |
| N | PASS | true | prior_day_pct=-0.49; prior_range_pct=2.9; negative=true; narrow=false; median_range_pct=3.7 |
| C | PARTIAL | false | base_sessions=21; breakdowns=0; bursts_in_base=0; giveback=0.3; tightness=0.86; base_volume_vs_leg=0.81; base_volume_vs_avg=1.03 |
| H | PASS | true | close_pos=0.91; close_above_open=true |
| RE | FAIL | false | vs_prior_5=0.71; vs_prior_10=0.65; bar_range_pct=3.0 |
| VOL | FAIL | false | volume_vs_prior=0.45; volume_vs_avg50=1.46; volume_rank_60=9; cv_required=false |

**Exact recorded reader text**

reason:

> The base shaded on the chart is a 21-session sideways-to-declining range sitting well below the August peak at ~160, with multiple wide overlapping red bars and no tightening — it looks like a distribution top, not an orderly consolidation. RE fails (burst bar is not the widest of the last five) and VOL fails hard (today's volume is less than half the prior session's, rank 9 of 60), meaning there is no range expansion and no volume confirmation of any kind. The notes confirm prior breakouts worked only 1 of 4 times in the last 60 sessions, and the base sits under visible overhead supply from the August high cluster.

key_risk:

> This is a biotech breaking out of what looks like a topping base with collapsing volume — a failed breakout here has no nearby support and could retrace sharply toward the 140 base low.

entry_note:

> Skip entirely at the open; if somehow taking it, skip if the open is below today's close of 144.98 or if the first 30 minutes show no buying interest above 145.

| Individual claim | Evidence status | Basis |
|---|---|---|
| RE fails its recorded quality test. | SUPPORTED | {"status": "FAIL", "threshold": "today's range over the largest of the prior 5 >= 1.0 (A+: also over the prior 10)", "values": {"bar_range_pct": 3.0, "vs_prior_10": 0.65, "vs_prior_5": 0.71}} |
| VOL fails its recorded quality test. | SUPPORTED | {"status": "FAIL", "threshold": "volume > prior session (A+: rank <= 3 of the last 60); a base over 21 sessions also needs >= 1.5x the 50-session average", "values": {"cv_required": false, "volume_rank_60": 9, "volume_vs_avg50": 1.46, "volume_vs_prior": 0.45}} |
| Prior-breakout success/failure is used as a quality strike or evidence of poor future odds. | CONTRADICTED | Every audited strategy prompt calls the prior-breakout note a measurement with no vote. A risk-only mention does not prove a grade vote. Only its use as authority is audited; no prior or subsequent return is recomputed or used to decide this finding. |
| The described base has adverse shape (overlap, chop, decline or distribution). | PARTIALLY SUPPORTED | Retained chart inspected; the source permits shape review, but loose/orderly is qualitative and the reader does not identify exact bars. No invented numerical tightness gate is endorsed. |
| There is no volume confirmation of any kind. | PARTIALLY SUPPORTED | Below-prior 0.45 is true, but average ratio=1.46 and rank=9 provide mixed context; no participation-absence proof. |

**Offline comparison with verified main:** its discovery tripwire does not reject this historical response.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.

## 2026-09-21 · WBD · 49e2724

Publication `49e2724c94b60963d914d55a2bf98598ac6507ad`; inventory index 96; discovery **both**.
Mechanical **10.0/10, A+ tally 6** → recorded reader **7.5 / B** → final **B**.
Rules `d5d62f525e0f`; prompt blob `3da7500efe0a269283926a60b4426943a6e34139`.
Source frame/chart/request identity retained; original source replay available.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=0; prior_day_pct=-1.56 |
| L | PASS | true | er=0.6; r2=0.95; leg_sessions=24; leg_gain_pct=14.2 |
| Y | PASS | true | breakouts_in_move=0; sessions_since_move_start=39; gain_since_move_start_pct=21.8 |
| N | PASS | false | prior_day_pct=-1.56; prior_range_pct=1.4; negative=true; narrow=true; median_range_pct=1.0 |
| C | PASS | false | base_sessions=15; breakdowns=0; bursts_in_base=0; giveback=0.33; tightness=0.59; base_volume_vs_leg=0.92; base_volume_vs_avg=0.88 |
| H | PASS | true | close_pos=0.91; close_above_open=true |
| RE | PASS | true | vs_prior_5=2.93; vs_prior_10=1.78; bar_range_pct=4.1 |
| VOL | PASS | true | volume_vs_prior=5.29; volume_vs_avg50=10.77; volume_rank_60=1; cv_required=false |

**Exact recorded reader text**

reason:

> The burst bar itself is largely a gap: open at 29.76 against a prior close of 27.80 means roughly 7.1% of the 10.79% gain was overnight, leaving only about 3.7% of actual intraday range — the bar looks tall on the chart but most of the work was done before the open, which is an EP-style gap rather than a clean momentum burst out of the base. The base (shaded box) is visually acceptable — 15 sessions of relatively tight, sideways action — but the consolidation sits well below the prior August highs near 29, so the burst is launching into that overhead supply zone rather than from a fresh high. The close near the top of the bar (0.91) is honest, and volume is exceptional, but the gap-dominated structure and the overhead supply from the August cluster reduce quality below A+.

key_risk:

> The burst is predominantly a gap, meaning the intraday range expansion is modest; if the catalyst fades, there is no clean intraday support level and the stock could fill back toward the base top quickly.

entry_note:

> Skip if tomorrow opens above 31.50 (extended gap over the ceiling) or if the first 30 minutes show a fade back below 30.00, signaling the gap is being sold.

| Individual claim | Evidence status | Basis |
|---|---|---|
| Most close-to-close gain occurred overnight. | SUPPORTED | Same retained signal facts as earlier Sep 21 WBD revision. |
| 3.7% is actual intraday range. | CONTRADICTED | High-low range is recorded 4.1%; open-to-close body is about 3.49%, a different measurement. |
| Gap appearance proves EP/news identity. | UNVERIFIABLE | No retained catalyst source; only an apparent visual possibility is authorized. |
| August highs near 29 form overhead above the signal. | CONTRADICTED | Signal open=29.76 and close=30.80, above base high=28.99. |
| 31.50 is the entry ceiling. | UNSUPPORTED | No plan exists and no rule/source establishes that level as the ceiling. |

**Offline comparison with verified main:** its discovery tripwire does not reject this historical response.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.

## 2026-09-21 · MRK · 49e2724

Publication `49e2724c94b60963d914d55a2bf98598ac6507ad`; inventory index 99; discovery **dollar**.
Mechanical **10.0/10, A+ tally 4** → recorded reader **5.5 / C** → final **C**.
Rules `d5d62f525e0f`; prompt blob `3da7500efe0a269283926a60b4426943a6e34139`.
Source frame/chart/request identity retained; original source replay available.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=0; prior_day_pct=-0.19 |
| L | PASS | true | er=0.42; r2=0.63; leg_sessions=47; leg_gain_pct=37.4 |
| Y | PASS | false | breakouts_in_move=1; sessions_since_move_start=48; gain_since_move_start_pct=23.8 |
| N | PASS | true | prior_day_pct=-0.19; prior_range_pct=1.4; negative=true; narrow=true; median_range_pct=1.9 |
| C | PASS | false | base_sessions=17; breakdowns=0; bursts_in_base=0; giveback=0.32; tightness=0.7; base_volume_vs_leg=0.92; base_volume_vs_avg=0.98 |
| H | PASS | false | close_pos=0.8; close_above_open=true |
| RE | PASS | true | vs_prior_5=1.57; vs_prior_10=1.22; bar_range_pct=3.3 |
| VOL | FAIL | false | volume_vs_prior=0.26; volume_vs_avg50=0.79; volume_rank_60=38; cv_required=false |

**Exact recorded reader text**

reason:

> The base box on the chart shows 17 sessions of wide, overlapping red and green bars with multiple bars spanning 1–2% of price and no clear tightening — visually loose rather than the orderly compression Bonde requires. Volume on the burst bar is only 26% of the prior session's already-modest volume and sits at rank 38 of the last 60, a hard VOL FAIL that is the single most decisive flaw: a dollar-scan burst with no volume confirmation and a base that never quieted down is a low-conviction signal. The prior leg is legitimate (47 sessions, 37% gain, ER/R² both passing), but the base quality and absent volume expansion undermine follow-through odds.

key_risk:

> MRK is a large-cap pharma with biotech flag; any adverse drug-trial or pricing headline inside the 3–5 day hold window can gap the stock well below the entry-day low stop.

entry_note:

> Skip if the open is below today's burst close of $149.50 or if the first 30 minutes show no buying interest and price drifts back toward the base high near $147.

| Individual claim | Evidence status | Basis |
|---|---|---|
| VOL fails its recorded quality test. | SUPPORTED | {"status": "FAIL", "threshold": "volume > prior session (A+: rank <= 3 of the last 60); a base over 21 sessions also needs >= 1.5x the 50-session average", "values": {"cv_required": false, "volume_rank_60": 38, "volume_vs_avg50": 0.79, "volume_vs_prior": 0.26}} |
| The described base has adverse shape (overlap, chop, decline or distribution). | PARTIALLY SUPPORTED | Retained chart inspected; the source permits shape review, but loose/orderly is qualitative and the reader does not identify exact bars. No invented numerical tightness gate is endorsed. |
| The base high is near 147. | CONTRADICTED | Recorded base high=156.92; no alternate base or plan level is identified. |
| The prior volume was already modest. | CONTRADICTED | Prior=31,158,866; signal/average=.79 and signal/prior=.26 imply prior about 3x the signal-relative average; chart shows a large spike. |

**Offline comparison with verified main:** its discovery tripwire does not reject this historical response.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.

## 2026-09-21 · PTGX · 49e2724

Publication `49e2724c94b60963d914d55a2bf98598ac6507ad`; inventory index 105; discovery **dollar**.
Mechanical **9.0/10, A+ tally 4** → recorded reader **4.5 / skip** → final **skip**.
Rules `d5d62f525e0f`; prompt blob `3da7500efe0a269283926a60b4426943a6e34139`.
Source frame/chart/request identity retained; original source replay available.

| Check | Recorded status | A+ flag | Measurements |
|---|---|---|---|
| 2 | PASS | true | up_run=0; up_closes=0; prior_day_pct=-0.49 |
| L | PASS | false | er=0.38; r2=0.88; leg_sessions=55; leg_gain_pct=66.2 |
| Y | PASS | true | breakouts_in_move=0; sessions_since_move_start=3; gain_since_move_start_pct=1.5 |
| N | PASS | true | prior_day_pct=-0.49; prior_range_pct=2.9; negative=true; narrow=false; median_range_pct=3.7 |
| C | PARTIAL | false | base_sessions=21; breakdowns=0; bursts_in_base=0; giveback=0.3; tightness=0.86; base_volume_vs_leg=0.81; base_volume_vs_avg=1.03 |
| H | PASS | true | close_pos=0.91; close_above_open=true |
| RE | FAIL | false | vs_prior_5=0.71; vs_prior_10=0.65; bar_range_pct=3.0 |
| VOL | FAIL | false | volume_vs_prior=0.45; volume_vs_avg50=1.46; volume_rank_60=9; cv_required=false |

**Exact recorded reader text**

reason:

> The base shaded on the chart is a 21-session sideways-to-declining range sitting well below the August peak at ~160, with multiple wide overlapping red bars and no tightening — it looks like a distribution top drifting lower, not an orderly consolidation. RE fails (burst bar is not the widest of the last five) and VOL fails hard (today's volume is less than half the prior session's), so the two expansion signals that confirm a real burst are both absent. The notes confirm prior breakouts worked only 1 of 4 times in the last 60 sessions, and the base sits under visible overhead supply from the August high cluster.

key_risk:

> This is a biotech name breaking out of what visually resembles a post-peak distribution base with declining price structure and heavy overhead supply near 155–160; a failed breakout here has room to fall back toward 140.

entry_note:

> Skip if the open is below today's close of 144.98 or if volume in the first 30 minutes is tracking below the prior session's pace — there is no expansion evidence to lean on.

| Individual claim | Evidence status | Basis |
|---|---|---|
| RE fails its recorded quality test. | SUPPORTED | {"status": "FAIL", "threshold": "today's range over the largest of the prior 5 >= 1.0 (A+: also over the prior 10)", "values": {"bar_range_pct": 3.0, "vs_prior_10": 0.65, "vs_prior_5": 0.71}} |
| VOL fails its recorded quality test. | SUPPORTED | {"status": "FAIL", "threshold": "volume > prior session (A+: rank <= 3 of the last 60); a base over 21 sessions also needs >= 1.5x the 50-session average", "values": {"cv_required": false, "volume_rank_60": 9, "volume_vs_avg50": 1.46, "volume_vs_prior": 0.45}} |
| Prior-breakout success/failure is used as a quality strike or evidence of poor future odds. | CONTRADICTED | Every audited strategy prompt calls the prior-breakout note a measurement with no vote. A risk-only mention does not prove a grade vote. Only its use as authority is audited; no prior or subsequent return is recomputed or used to decide this finding. |
| The described base has adverse shape (overlap, chop, decline or distribution). | PARTIALLY SUPPORTED | Retained chart inspected; the source permits shape review, but loose/orderly is qualitative and the reader does not identify exact bars. No invented numerical tightness gate is endorsed. |

**Offline comparison with verified main:** its discovery tripwire does not reject this historical response.
Contradicted/unsupported authority claims above remain impermissible under the current source hierarchy;
supported independent quality concerns remain eligible. No current model response, score or final grade is inferred.
