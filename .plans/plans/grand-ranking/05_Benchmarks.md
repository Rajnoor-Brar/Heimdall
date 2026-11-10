# 05 · Benchmarks: the four Runs, today's engine and the proposed one (Pillar 5)

## The Runs

Four Runs of a real study's work dir, named here B1–B4. The developer named them in the request; the mapping to their addresses stays out of the repository. Each is a jet cross-section analysis of 12 objects, measured against the same data.

| Run | Points | Pages | Varied quantities | Role |
|---|---|---|---|---|
| B1 | 24 | 48 | pdf (2) × jet radius (6) × jet algorithm (2); one generator | pathology: one PDF breaks it |
| B2 | 24 | 72 | pdf (4) × jet radius (3) × jet algorithm (2); one generator | pathology |
| B3 | 16 | 24 | generator (2) × pdf (8) | discrimination and marginals; one pathological point |
| B4 | 288 | 432 | pdf (8) × p_T,ref (9) × QED shower (2) × lepton PDF (2); one generator | marginals over a four-way sweep |

**How it was measured.**
- B1 and B2 carry Paint's `measured` bins already.
- B3 and B4 were measured before Paint wrote bins. Their page documents were copied into scratch, and `Paint.exe <page>.toml … --ranges-only` re-measured them there. The work dir was only read.
- Every one of the 27 registry metrics was computed for every curve, 4224 curves in all. Today's engine is `stats.score` with its defaults.
- **Reproducible:** `python -I -W ignore probe/bench.py LABEL=RESULTS:PAGES … --bad LABEL=GLOB`. The pathological points are named only so the probe can check that the engine finds them; scoring never uses the names.

## §1 Bad actors: what makes a point pathological, and what finds it

In B1, B2 and B3 the generator with the PDF MSHT20qed_lo produces events with huge weights of either sign. Its curves are:
- **page yields** from −1.9 × 10¹¹ to 3 × 10¹¹ times the data's;
- **bins** 10^10.7 times the data at the median;
- **effective event counts** below 1;
- **χ²/ndf about 1**, because their error bars are as large as their excursions.

| Test, on each page | Pathological: failed pages per point | Ordinary: most failed pages of any point |
|---|---|---|
| **G1** a bin ≥ 10³ × its reference | B1 12 of 12 (all 12 points) · B2 12 of 12 (all 6) · B3 12 of 12 | 0 in every Run, B4's 288 points included. Ordinary maximum: 10^2.01 |
| page yield ≤ 0 | B1 0–11 · B2 0–11 · B3 9 | 0 |
| \|ln yield ratio\| ≥ ln 10 | B1 1–12 · B2 1–12 · B3 3 | 0 |
| negative-weight share > 5 % | caught | false positives: ordinary curves reach 0.36 (B1), 0.22 (B2) |

G1 alone separates the two populations with no tuning. The margin is eight decades between the medians, and one decade between the ordinary maximum (2.01) and the gate (3).

**The inversion of today's compatibility ranking.** Ranking by the compatibility purpose with χ²/ndf alone:

| Run | Pathological points' ranks today | With `chi2_sigma` + `poisson_dev` |
|---|---|---|
| B1 | 1–12 of 24 | 13–24 of 24 |
| B2 | 1–6 of 24 | 19–24 of 24 |
| B3 | 1 of 16 | 16 of 16 |

**What today's total score does.** It already puts every pathological point at the bottom (B1–B3). The reason is `norm`'s linear cost: |ln ratio| ≈ 23 against bad = 0.15 is a cost of about 170, 79–99 % of the score. That margin vanishes under any bounded cost, so the proposal moves the demotion to the gate, where it does not depend on scale.

**Proposed:**
- **Vetoed:** 12/12 in B1, 6/6 in B2 and 1/1 in B3. In B4, 0 of 288.
- **Ordering:** every pathological point ranks after every ordinary one.

## §2 The ranking of ordinary points

| Run | Engine | Category shares of the loss (%) | Page-bootstrap stability (Spearman) | Spearman vs today |
|---|---|---|---|---|
| B1 | today | compat 30 · norm 5 · shape 1 · trend 63 · defects 1 | 0.945 | 1 |
| | today, compressed | 32 · 8 · 4 · 51 · 5 | 0.936 | 0.923 |
| | **proposed** | 39 · 8 · 14 · 33 · 6 | 0.898 | 0.594 |
| B2 | today | 9 · 9 · 0 · 81 · 0 | 0.854 | 1 |
| | today, compressed | 18 · 14 · 1 · 65 · 2 | 0.882 | 0.849 |
| | **proposed** | 42 · 9 · 14 · 28 · 6 | 0.891 | 0.255 |
| B3 | today | 33 · 5 · 1 · 60 · 1 | 0.907 | 1 |
| | today, compressed | 32 · 9 · 4 · 51 · 4 | 0.932 | 0.818 |
| | **proposed** | 35 · 10 · 17 · 32 · 6 | 0.968 | 0.821 |
| B4 | today | 51 · 4 · 1 · 41 · 2 | 0.939 | 1 |
| | today, compressed | 43 · 10 · 6 · 35 · 6 | 0.966 | 0.975 |
| | **proposed** | 33 · 15 · 17 · 27 · 8 | 0.941 | 0.961 |

**Reading it:**
- **Today, trend owns the loss** (41–81 %) and shape is mute (0–1 %), because:
  - **ordinary tilts are 1–3** against a bad of 0.25. Read bin by bin, they are real: a curve falling 20× faster than the data by its last bin;
  - **`shape`'s shrinkage counts a 20 %-error bin at a fifth.**

  Equal category weights then mean little. The proposed set and compression bring every category to between 6 and 42 %.
- **Compression alone steadies the ranking** in three Runs of four (B2, B3, B4) and costs 0.01 in B1.
- **The proposed set reorders B2 the most** (Spearman 0.255 against today). Today's B2 order is 81 % one metric (tilt); the proposed one is not. There is no ground truth to score this against. The claim is only that it is no longer one metric's ranking, and is as stable or more (0.854 → 0.891).
- **B4, the clean Run, barely moves** (0.961): the change is not churn.
- **A category exponent of 3 instead of 2** moved no top-3 and changed the gap by under 20 % (tried in the session's probe). RMS stays.

## §3 Marginals: separating trends across the sweeps

Each row is the matched effect ×e^E against the point's strata, ± SE, with n strata and g trimmed per end. "today" is today's marginal, the RMS of scores. The trim α was tried at 0, 0.1, 0.2, 0.25 and the median. The bootstrap Kendall τ of the order moved by ≤ 0.1 on every quantity once gated, so 0.2 stands.

**B4** (no pathology; every slice n = 32–144):

| Quantity | Proposed: best → worst | Today (RMS) | Reading |
|---|---|---|---|
| lepton PDF | on ×0.930 ± 0.011 · off ×1.075 ± 0.011 | 5.46 · 5.82 | on is better by ×0.865, 9σ by the two SEs (P4's paired test is tighter); τ 1.00 |
| p_T,ref | 40 ×0.920 · 36 0.945 · 32 0.949 · 38 0.954 · 34 0.965 · 30 0.971 · **28 1.052 · 26 1.136 · 24 1.186** | 4.59 … 8.23 | a step below 30, a plateau from 30 to 40 (the plateau's order is within its SEs); τ 0.70 |
| pdf | NNPDF23lo 0.933 · MSTW08lo90cl 0.946 · MSTW08lo 0.959 · MSHT20qed_lo 0.978 · MSHT20lo_as130 1.022 · PDF4LHC21 1.059 · NNPDF40nnlo 1.066 · NNPDF23nlo 1.069 | 4.79 … 6.54 | the LO sets beat the NLO and NNLO ones, as an LO generator would; τ 0.76 |
| QED shower | off ×0.985 ± 0.007 · on 1.015 | 5.50 · 5.78 | a 3 % effect, 3σ by the two SEs; τ 0.87 |

On a clean, balanced Run, today's RMS marginal already orders these values much the same. The proposed tables add the error, n and the trimming, and state effects as ratios.

**B1 and B2** (pathology in half or a quarter of every slice):

| Run, quantity | Proposed (gated, matched) | Today (RMS) | Bootstrap τ, gated vs not |
|---|---|---|---|
| B1 jet radius | dr01 0.908 · dr04 0.914 · dr16 0.934 · dr08 0.938 · dr02 0.996 · **dr32 1.380 ± 0.059** | 41.7 · 44.8 · 28.4 · 39.5 · 39.9 · 30.7: dr32 looks second best | 0.56 vs 0.09 |
| B1 jet algorithm | anti-kt ×0.948 ± 0.022 · kt 1.055 | 31.8 · 43.2 | 1.00 vs 0.20 |
| B1 pdf | MSHT20qed_lo: every point vetoed (12 of 12), so no matched effect | 53.4 vs 5.3 | — |
| B2 pdf | MSHT20lo_as130 ×0.934 ± 0.019 · NNPDF23lo 0.999 · MSTW08lo 1.039 · MSHT20qed_lo vetoed (6 of 6) | 4.6 · 4.4 · 5.1 · 67.0 | 0.91 ungated |
| B2 jet radius | dr08 0.963 · dr04 1.003 · dr16 1.030 | 30.5 · 32.8 · 37.5 | 0.53 vs 0.20 |

Today's marginals in B1 and B2 measure how many pathological points a slice holds, not the quantity: the RMS follows them. Gating first, then trimming, recovers the radius and algorithm trends. No trim fraction could do it alone: with half a slice contaminated, a 20 % trim removes none of it.

**B3** (generator × pdf, one point vetoed, n = 2 per pdf value):

| Quantity | Proposed | Today (RMS) | Reading |
|---|---|---|---|
| generator | Pythia ×0.889 ± 0.031 · Sherpa 1.125 ± 0.031 | 4.69 · 16.04 | Pythia better by ×0.79; today's 3.4× gap is the one vetoed point |
| pdf | MSHT20lo_as130 0.860 ± 0.064 · MSHT20qed_lo 0.928 (n = 1, Pythia only) · NNPDF23lo 0.948 ± 0.142 · … · PDF4LHC21 1.124 | MSHT20qed_lo 30.55, worst by far | today blames the PDF for both generators; matched, its Pythia point is fine. Its level (1.43) looked best only because its one survivor is Pythia's: the case for ordering by E, not M |

With n = 2 per value, B3's pdf order is not robust (τ 0.51), and the table must say so (03 §2.4). It does: every row is marked "n = 2: not robust".

## Acceptance for P7 (on the implemented engine, same Runs)

1. G1 vetoes exactly the pathological points: 12, 6, 1 and 0.
2. In every category ranking, vetoed points are last.
3. No category exceeds 50 % of the loss on any of B1–B4.
4. B4's rank correlation with today ≥ 0.9; its marginal orders as in the table above, lepton PDF and the p_T,ref step distinguishable.
5. B1's jet-radius marginal puts dr32 last, distinguishable from the best.
6. The probe and the engine agree on every point's loss to 1e-9.
