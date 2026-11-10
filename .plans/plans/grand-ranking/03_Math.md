# 03 · The mathematics: the Grand Ranking and the quantity marginals

Notation. A **point** p has, on each of its pages k, one **curve** with metric values m_j(p, k), j over the metrics on. Every metric j has:
- a category κ(j);
- a polarity: `lower`, `higher`, `one` or `descriptor`;
- a scale T_j: the identity, or log₁₀;
- thresholds (g_j, b_j);
- a weight w_j > 0 (default 1).

A page k has a weight ω_k (default 1, then a figure's `weight`, then the first matching `[ranking].weights` glob). Every quantity below is computed from the curve's own row, so a point's loss does not depend on which other points are in the table (pool independence, V251).

## 1. The Grand Ranking

### 1.1 Integrity gates (the veto, first and lexicographic) · closed 2.1, 2.2

On each page, a curve fails a gate when either holds:
- **G1:** `peak_bin_ratio` = log₁₀ max_i \|y_i\| / ref_i ≥ 3, over the compared bins with ref_i > 0;
- **G2:** the page's yield Σ_i y_i Δx_i ≤ 0, on a page that is not normalised.

Let F(p) be the number of p's pages that fail a gate. p is **vetoed** when F(p) ≥ 1. An optional third gate, G3, is `[ranking].veto_loss = λ`: a page with page loss L(p, k) > λ fails.

Why lexicographic and not a large penalty:
- **No addition can buy a failed page back.** A penalty added to a sum is always outweighed by enough good pages; a lexicographic order never is.
- **It needs no constant tuned to the scale of the other metrics.** Today's demotion works only because `norm`'s linear cost reaches about 170 (05 §1). Under any bounded transform it would not.

### 1.2 Orientation and normalisation (directional alignment) · closed 3.1

Each metric value becomes an oriented excess q, then a hinged tolerance excess z, then a compressed cost c:

```
             ⎧ T(m)            polarity lower
q_j(m)  =    ⎨ −T(m)           polarity higher
             ⎩ |log₁₀ m|       polarity one            (m ≤ 0 → +∞)

z_j  =  max(0, (q_j(m) − q_j(g_j)) / (q_j(b_j) − q_j(g_j)))       0 within good, 1 at bad
c_j  =  log₂(1 + z_j)                                             0 within good, 1 at bad, 2 at z = 3, 7.4 at z = 170
```

- For `higher` with thresholds (g, b) = (1000, 100) on a log scale: q(g) = −3, q(b) = −2. A value of 316 gives z = 0.5.
- A missing value (NaN) is skipped. An infinite value is c = +∞ and makes the page loss +∞. Such a point ranks after every finite one that is not vetoed.
- `descriptor` metrics are never scored.

The map is monotone in m, so it preserves each metric's ordering; compression changes only how far a large excess reaches. A cost of 7.4 is about seven tolerance-doublings past bad, not 170 tolerance-widths. So a metric with a tight null (tilt's bad = 0.25 against real tilts of 1–3) cannot own the loss by its slope alone. The far tail is the gate's job, not the sum's.

The alternatives under `[ranking].cost` (`median`, `mad`, `minmax`, `surprisal`) are kept as opt-ins, defined as today, each computed on z before compression.

### 1.3 Aggregation · closed 3.1, 3.3

```
category cost   C_κ(p,k)  =  ( Σ_{j∈κ} w_j c_j² / Σ_{j∈κ} w_j )^{1/2}          over the metrics with a number
page loss       L(p,k)    =  ( (1/|K|) Σ_{κ∈K} C_κ² )^{1/2}                    K: categories with a cost on this page
point loss      L(p)      =  ( Σ_k ω_k L(p,k)² / Σ_k ω_k )^{1/2}               over the pages with a loss
worst page      k*(p)     =  argmax_k L(p,k)
```

Each step is the power mean with exponent 2, so it is monotone and Pareto-respecting: lowering any cost never raises a loss. The quadratic mean weighs an imbalance up, the all-rounder property. A point with C = (1, 1) has L = 1, one with (0, √2) also has L = 1, and one with (0, 2) has L = 1.41, worse than (1, 1). RMS inside a category keeps a pair of metrics at one category's weight (V251).

### 1.4 The order · closed 2.2

```
rank order:  (vetoed(p) ascending,  F(p) descending among vetoed,  L(p) ascending,  label)
```

Ties in L at display precision share a rank: 1, 2, 2, 4. A point with no scored page has no loss and ranks after every point with one, but before the vetoed ones. The ranking is flat across cells when every cell's pages are the same objects against the same reference; otherwise it is ranked within cells, as today (04 §1).

## 2. Quantity-wise marginals (the trimmed mean over orthogonal variations)

### 2.1 Sets

- Q is the set of varied quantities among the scored points. For quantity q with values V_q, the **slice** of v is S_v = {p : q(p) = v, p not vetoed}.
- The **stratum** of p is r(p) = (q′(p))_{q′ ∈ Q∖{q}}, its values on every other varied quantity.
- R_v is the set of strata that have a point in S_v.
- Each point has the log loss ℓ(p) = ln(δ + L(p)), δ = 0.01. Since L ≥ 0 and is ratio-scaled, differences of ℓ are relative: Δℓ = −0.1 reads "×0.90, a tenth lower". δ keeps a point that is within good everywhere finite.

### 2.2 The two statistics a row reports

```
level            M_v  =  TM_α { ℓ(p) : p ∈ S_v }                          shown as e^{M_v}, a typical point loss
matched effect   E_v  =  TM_α { ℓ(p) − ℓ̄(r(p)) : p ∈ S_v, |r(p)| ≥ 2 }   shown as e^{E_v}, × against its strata
                 ℓ̄(r) =  the mean of ℓ over the non-vetoed points of stratum r
```

The table is **ordered by E_v**. M_v is what the request asked for, the trimmed mean across the orthogonal variations. It stays beside E_v, but it does not order the table. The reasons:

- **On a balanced, gate-free design, E_v = M_v − const**, so the order is the same.
- **When the gate or the sweep makes the design unbalanced, M_v is confounded and E_v is not.** On B3 the vetoed Sherpa point leaves MSHT20qed_lo with only its Pythia point. Its M_v (1.42) then looks best because Pythia is the better generator, not because of the PDF. E_v compares each point with its own generator's mean instead.
- **Strata with one surviving value** cannot say anything about q. They are counted as *unmatched*, never dropped quietly.

### 2.3 The trimmed mean and its error

For n values x₍₁₎ ≤ … ≤ x₍ₙ₎ and trim α (default 0.2):

```
g(n)    =  0                    n ≤ 2
           max(1, ⌊α n⌋)        n ≥ 3
TM_α    =  (1/(n − 2g)) Σ_{i=g+1}^{n−g} x₍ᵢ₎
SE      =  s_w / ((1 − 2g/n) √n)        s_w: the SD (n − 1) of the winsorised sample, x₍ᵢ₎ clamped to [x₍g+1₎, x₍n−g₎]
```

SE is Tukey and McLaughlin's. It is not given when n − 2g < 2.

**Against the best.** Let b be the value with the smallest E. For each other value v, d_r = ℓ(p_v,r) − ℓ(p_b,r) over the strata holding both. Its TM_α and SE give "vs best: ×e^{TM} ± SE".
- A value is **indistinguishable from the best** when |TM(d)| < 2 SE(d), and is shaded with it.
- The test is paired, because strata are shared.
- It is one test per value against the best, not all pairs. K − 1 tests stay readable, and the note says they are not corrected for multiplicity.

### 2.4 Small n, and what each row says

| n (matched strata) | Trim | What is shown |
|---|---|---|
| 0 | — | `–`, with the reason: every point vetoed (k of k), or no stratum holds another value |
| 1 | none | the value, SE `–`, marked "one stratum" |
| 2 | none (the mean) | the mean, SE from the pair, marked "n = 2: not robust" |
| 3–4 | g = 1 (the median, or the mean of the middle two) | as below |
| ≥ 5 | g = ⌊0.2 n⌋, at least 1 | as below |

Every row carries:
- **v** and **n**: the strata matched;
- **g**: the number trimmed at each end;
- **the vetoed points of the slice**, and the strata left unmatched;
- **e^{E_v}** with SE, and **e^{M_v}**;
- **vs best:** "×1.07 ± 0.02", or "≈ best".

A quantity whose every stratum has one value, such as a quantity varied only together with another, has no matched effect. The table says so and shows M_v alone, with today's confounding sentence.

### 2.5 What changes from today

Today a marginal is the RMS of the slice's scores (`score.py:497`). It is neither trimmed, gated nor matched, and its note calls it a mean (`bars.py:708`). On B1, half of every jet-radius slice is pathological: today's order of dr values is noise, with a bootstrap Kendall τ of 0.09. Gated, it rises to 0.56, and the trend (dr32 ×1.38) is visible (05 §3).

## 3a. The method record (the developer's transparency rule)

Every engine call returns, beside its numbers, a `Method` value: what was applied, with where each choice came from. A choice's source is the registry default, `[ranking]`, a set's `ranking = {…}`, a figure's `weight`, or a CLI flag. The presenters only render the record. They never restate a rule in their own words, so a note cannot drift from the computation, as today's marginal note ("mean") does over an RMS.

| Stage | The record names |
|---|---|
| Gates | each gate on, its level and its source; per vetoed point, which gate, how many pages, the largest value found · closed 2.2 |
| Metrics | each metric scored: its polarity, its scale T, its thresholds (g, b) with their source and reason (`why`), its weight w_j with its source; each metric computed but not scored, and why (a descriptor, shown only) · closed 3.1 |
| Cost | the orientation per polarity; the normalisation (`thresholds`, or the opt-in in use, with its pool dependence said); the compression c = log₂(1 + z), with the fixed points 0 and 1 · closed 3.1 |
| Category | the mean inside it (RMS, metric weights counting), and which metrics fell in it · closed 3.1 |
| Page loss | the mean across categories (RMS, equal), and which categories had a cost · closed 3.1 |
| Pages | each page's weight ω_k and its source (figure `weight` > first matching glob, named > 1); the mean across pages (`over_pages`, RMS by default); the pages left out and why (a reference curve, pages against a curve when others are against data, no bins) · closed 3.3 |
| Order | the rank rule (03 §1.4), ties, and the cells the ranking is flat across or banded within, with the reason · closed 2.2 |
| Marginals | α, g(n), δ, log scale; E vs M and which orders the table; the strata's quantities; per row n, g, vetoed, unmatched; the paired test against the best and that it is uncorrected for multiplicity |
| Opt-in aggregators | `aggregate`, `weights_by = "critic"` (the learned weights, printed), `dominated`, each with what it costs · closed 3.1 |

The record lives in the sidecar (`statistics.json`, `"method"`), in `rank --json`, in the summary's and the report's method section, and in a short form under every table (04 §Method).

## 3. Properties the tests hold (P2–P4)

1. **Pool independence:** adding a point to the table changes no other point's loss. · closed 3.1
2. **Monotone:** raising any one metric's excess never lowers a loss. · closed 3.1
3. **Lexicographic veto:** a vetoed point ranks after every passing point, for any losses. · closed 2.2
4. **Category balance:** n metrics of one category on a page weigh as one category (today's test, kept). · closed 3.1
5. **Compression fixed points:** c(0) = 0, c(1) = 1; c is concave beyond 1. · closed 3.1
6. **Matched effects are invariant to a stratum's difficulty:** adding a constant to every point of one stratum leaves every E_v unchanged.
7. **Small-n rules,** as the table in §2.4.
8. **Trimmed mean:** TM₀ is the mean, and TM at g = ⌊(n−1)/2⌋ is the median. The SE matches a reference value computed by hand on a built sample.
9. **The method record is complete.** For each setting of `[ranking]`, a set's `ranking`, a figure's `weight` and each CLI flag, changing it from its default changes either the numbers and the record together, or neither. A setting that moves a number the record does not name fails the test.
