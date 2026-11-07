# Histogram Curve Quality & Ranking Specification
**Scope:** Variable-bin-width differential histograms ($e^{-\lambda x}$ exponential tails, narrow peaks, and interspersed glitches) across multi-observable parameter sets.

---

## 0. Common Data Structures & Preprocessing Primitives

Before evaluating any metric on histogram $h \in \{1, \dots, M\}$ for candidate configuration $s \in \{1, \dots, K\}$, standardize the input arrays across bins $i \in \{1, \dots, N_h\}$:

* **Bin Geometry:** Left edge $x_{a,i}$, right edge $x_{b,i}$, bin width $\Delta x_i = x_{b,i} - x_{a,i}$, geometric midpoint $x_{\text{mid},i} = \frac{1}{2}(x_{a,i} + x_{b,i})$, and total axis span $L_x = x_{b,N_h} - x_{a,1}$.
* **Differential Densities & Uncertainties:** Candidate density $C_i \equiv dN_{C,i}/dx$ with error $\sigma_{C,i}$; Reference density $R_i \equiv dN_{R,i}/dx$ with error $\sigma_{R,i}$.
* **Expected Integrated Bin Counts:**
  $$n_{C,i} = C_i \Delta x_i, \qquad n_{R,i} = R_i \Delta x_i$$
* **Effective Unweighted Counts (when working with weighted MC or unfolded data):**
  $$n_{\text{eff},R,i} = \left(\frac{R_i}{\sigma_{R,i}}\right)^2, \qquad n_{\text{eff},C,i} = \left(\frac{C_i}{\sigma_{C,i}}\right)^2$$
* **Regularized Symmetric Log-Ratio ($\ell_i$):** Prevents $\ln(0)$ singularities on zero-sink dropouts ($C_i \le 0$) and treats $k\times$ blow-ups and $k\times$ dropouts symmetrically (default regularization floor $\epsilon = 0.01$):
  $$\ell_i = \ln\!\left(\frac{\max(C_i, 0) + \epsilon R_i}{R_i}\right), \qquad \sigma_{\ln r, i} = \sqrt{\left(\frac{\sigma_{C,i}}{\max(C_i, \epsilon R_i)}\right)^2 + \left(\frac{\sigma_{R,i}}{R_i}\right)^2}$$
* **Lafferty–Wyatt Exponential Bin Barycenter ($\langle x \rangle_i$):** Corrects wide-bin centering bias in steeply falling spectra using local decay rate $\hat{\lambda}_i = \max\!\left(0,\, -\frac{1}{\Delta x_i}\ln\frac{R_{\min(i+1, N_h)}}{R_i}\right)$:
  $$\langle x \rangle_i = \begin{cases} x_{\text{mid},i} & \text{if } \hat{\lambda}_i \Delta x_i < 10^{-3} \\ x_{a,i} + \frac{1}{\hat{\lambda}_i} - \frac{\Delta x_i}{e^{\hat{\lambda}_i \Delta x_i} - 1} \approx x_{\text{mid},i} - \frac{\hat{\lambda}_i (\Delta x_i)^2}{12} & \text{otherwise} \end{cases}$$

---

## Part 1: Reference-Based Quality Analysis (Candidate $C$ vs. Reference $R$)

### 1.1 Reference-Anchored Baker–Cousins Poisson Deviance ($\chi^2_{\lambda,\text{ref}} / \text{ndf}$)
* **Category:** Global statistical compatibility & low-count Poisson fit.
* **Formula:**
  $$\chi^2_{\lambda,\text{ref}} / \text{ndf} = \frac{1}{N_h} \sum_{i=1}^{N_h} d_{\text{ref},i}^2, \qquad d_{\text{ref},i}^2 = 2 \, s_{\text{scale},i} \left[ n_{C,i}^* - n_{R,i} + n_{R,i} \ln\!\left(\frac{n_{R,i}}{n_{C,i}^*}\right) \right]$$
  where $n_{C,i}^* = \max(C_i \Delta x_i,\, 0.5)$ is the Jeffreys prior floor and $s_{\text{scale},i} = \frac{n_{\text{eff},R,i}}{n_{R,i}}$ scales differential densities to true statistical count precision ($s_{\text{scale},i} = 1$ if $n_{R,i}$ is raw unweighted counts).
* **Signed Deviance Pull:** $d_{\text{ref},i} = \text{sign}(n_{C,i}^* - n_{R,i}) \sqrt{d_{\text{ref},i}^2}$.
* **Implementation Notes:**
  * Anchoring precision strictly to $R_i$ prevents an absurd MC spike ($C_i \gg R_i$ with $\sigma_{C,i} \approx C_i$) from masking itself via an inflated error denominator.
  * If $n_{R,i} = 0$, the logarithmic term $n_{R,i}\ln(n_{R,i}/n_{C,i}^*) \to 0$ and $d_{\text{ref},i}^2 = 2 n_{C,i}^*$.

### 1.2 Empirical-Bayes Shrunk Axis-Weighted Error ($\text{wMAPE}_{\text{shrunk}}$)
* **Category:** Phase-space ratio accuracy across variable bin widths.
* **Formula:**
  $$\text{wMAPE}_{\text{shrunk}} = \frac{\sum_{i=1}^{N_h} \Delta x_i \, s_i \, |\ell_i|}{\sum_{i=1}^{N_h} \Delta x_i}, \qquad s_i = \frac{\tau^2}{\tau^2 + \sigma_{\ln r, i}^2}$$
* **Implementation Notes:**
  * Set physical model tolerance $\tau = 0.10$ ($10\%$).
  * In high-precision narrow or wide bins ($\sigma_{\ln r, i} \ll \tau$), $s_i \to 1$, weighting ratio deviations strictly by physical bin width $\Delta x_i$.
  * In ultra-noisy wide tail bins ($\sigma_{\ln r, i} \gg \tau$), $s_i \to 0$, preventing random Poisson tail noise from multiplying huge $\Delta x_i$ weights.

### 1.3 Barycenter Log-Ratio Slope ($|\tilde{\beta}_1|$)
* **Category:** Dimensionless spectral tilt & exponential decay-rate mismatch.
* **Formula:**
  $$|\tilde{\beta}_1| = L_x \left| \frac{\sum_{i=1}^{N_h} w_i \left(\langle x \rangle_i - \bar{x}_w\right)\left(\ell_i - \bar{\ell}_w\right)}{\sum_{i=1}^{N_h} w_i \left(\langle x \rangle_i - \bar{x}_w\right)^2} \right|, \qquad w_i = \frac{1}{\sigma_{\ln r, i}^2 + \tau_0^2}$$
  where $\bar{x}_w = \frac{\sum w_i \langle x \rangle_i}{\sum w_i}$, $\bar{\ell}_w = \frac{\sum w_i \ell_i}{\sum w_i}$, and $\tau_0 = 0.01$ prevents a single ultra-high-count bin from monopolizing the regression weight.
* **Implementation Notes:**
  * Multiplying by the axis span $L_x = x_{b,N_h} - x_{a,1}$ yields the total fractional log-ratio change across the entire plot, making $|\tilde{\beta}_1|$ dimensionless across different physical observables.

### 1.4 Integrated Tail Pull ($|Z_{\text{tail}}|$)
* **Category:** Pooled high-uncertainty wide-tail accuracy.
* **Formula:**
  $$|Z_{\text{tail}}| = \frac{\left| \sum_{i \in \mathcal{T}} (C_i - R_i)\Delta x_i \right|}{\sqrt{\sum_{i \in \mathcal{T}} \left(\sigma_{C,i}^2 + \sigma_{R,i}^2\right)(\Delta x_i)^2}}$$
* **Tail Bin Selection ($\mathcal{T}$):** Define the cumulative reference yield $F_R(x_{b,i}) = \frac{\sum_{m=1}^i R_m \Delta x_m}{\sum_{m=1}^{N_h} R_m \Delta x_m}$. Select $\mathcal{T} = \{ i \mid F_R(x_{a,i}) \ge 0.90 \}$ (or at least the last $K_{\text{tail}} = \max(2, \lfloor 0.25 N_h \rfloor)$ wide bins).
* **Implementation Notes:**
  * Pooling $K_{\text{tail}}$ wide tail bins boosts signal-to-noise by $\sqrt{K_{\text{tail}}}$, catching systematic tail excesses/deficits while averaging out random $\pm 1\sigma$ bin-to-bin noise.

### 1.5 Discrete Log-Ratio Second-Difference Roughness ($\mathcal{R}_{\Delta^2}$)
* **Category:** Interspersed blow-up spike and zero-sink detector.
* **Formula:**
  $$\mathcal{R}_{\Delta^2} = \sqrt{\frac{1}{N_h - 2} \sum_{i=2}^{N_h - 1} \kappa_i^2}, \qquad \kappa_i = \ell_i - \left[ \frac{\left(\langle x \rangle_{i+1} - \langle x \rangle_i\right)\ell_{i-1} + \left(\langle x \rangle_i - \langle x \rangle_{i-1}\right)\ell_{i+1}}{\langle x \rangle_{i+1} - \langle x \rangle_{i-1}} \right]$$
* **Implementation Notes:**
  * Measures the local discrete Laplacian (deviation of bin $i$ from the linear interpolation of neighbors $i-1$ and $i+1$).
  * Immune to global normalization shifts ($\ell_i = \text{const} \implies \kappa_i = 0$) and linear tilts ($\ell_i \propto \langle x \rangle_i \implies \kappa_i = 0$), firing exclusively on localized point glitches.

### 1.6 Top-$k$ Worst-Bin Conditional Value-at-Risk ($\text{CVaR}_k$)
* **Category:** Undiluted outlier & glitch penalty.
* **Formula:**
  $$\text{CVaR}_k = \frac{1}{k} \sum_{m=1}^{k} d_{\text{ref},(m)}^2, \qquad k = \max\!\left(3,\, \lceil 0.10 N_h \rceil\right)$$
  where $d_{\text{ref},(1)}^2 \ge d_{\text{ref},(2)}^2 \ge \dots \ge d_{\text{ref},(N_h)}^2$ are the per-bin Reference-Anchored Baker–Cousins deviances sorted in descending order.
* **Implementation Notes:**
  * Prevents $N_h - k$ well-behaved bins from diluting $1\text{–}3$ broken bins while distinguishing 1 glitch bin from 3 glitch bins.

### 1.7 Supplementary Reference Metrics (Targeted Diagnostics)
* **Yield-Weighted Ratio Error / Normalized $L^1$ Area ($\text{wMAPE}_{\text{yield}}$):**
  $$\text{wMAPE}_{\text{yield}} = \frac{\sum_{i=1}^{N_h} |C_i - R_i|\Delta x_i}{\sum_{i=1}^{N_h} R_i \Delta x_i} = \frac{\sum_{i=1}^{N_h} (R_i \Delta x_i)\,|r_i - 1|}{\sum_{i=1}^{N_h} R_i \Delta x_i}$$
* **Integrated Yield Bias ($|\Delta_{\text{norm}}|$):**
  $$|\Delta_{\text{norm}}| = \frac{\left|\sum_{i=1}^{N_h} C_i \Delta x_i - \sum_{i=1}^{N_h} R_i \Delta x_i\right|}{\sum_{i=1}^{N_h} R_i \Delta x_i}$$
* **Lag-1 Pull Autocorrelation ($\rho_1$):**
  $$\rho_1 = \frac{\sum_{i=1}^{N_h-1} (d_{\text{ref},i} - \bar{d})(d_{\text{ref},i+1} - \bar{d})}{\sum_{i=1}^{N_h} (d_{\text{ref},i} - \bar{d})^2}$$
* **Bounded Jensen–Shannon Shape Divergence ($D_{\text{JS}} \in [0,1]$):**
  $$D_{\text{JS}}(P \parallel Q) = \frac{1}{2\ln 2} \sum_{i=1}^{N_h} \left[ P_i \ln\!\left(\frac{2P_i}{P_i + Q_i}\right) + Q_i \ln\!\left(\frac{2Q_i}{P_i + Q_i}\right) \right], \qquad P_i = \frac{C_i \Delta x_i}{I_C}, \quad Q_i = \frac{R_i \Delta x_i}{I_R}$$
* **Anderson–Darling Tail-Weighted Shape Distance ($A^2$):**
  $$A^2 = \sum_{i=1}^{N_h-1} \frac{\left(F_C(x_{b,i}) - F_R(x_{b,i})\right)^2}{F_R(x_{b,i})\left(1 - F_R(x_{b,i})\right)} \, Q_i$$

---

## Part 2: Intrinsic & Reference-Free Ensemble Quality Analysis

Use these metrics when **no experimental or truth reference curve $R_i$ exists**. Define regularized log-density $\eta_i = \ln\!\big(\max(C_i, \epsilon \bar{C})\big)$ where $\bar{C} = \frac{\sum C_i \Delta x_i}{\sum \Delta x_i}$.

### 2.1 Intrinsic Log-Space Second-Difference Roughness ($\mathcal{R}_{\text{int}}$)
* **Category:** Reference-free spike & zero-sink detector.
* **Formula:**
  $$\mathcal{R}_{\text{int}} = \sqrt{\frac{1}{N_h - 2} \sum_{i=2}^{N_h - 1} \left( \eta_i - \left[ w_{i-1}\eta_{i-1} + w_{i+1}\eta_{i+1} \right] \right)^2}$$
  where $w_{i-1} = \frac{x_{\text{mid},i+1} - x_{\text{mid},i}}{x_{\text{mid},i+1} - x_{\text{mid},i-1}}$ and $w_{i+1} = 1 - w_{i-1}$.
* **Implementation Notes:** Smooth exponential ($e^{-\lambda x}$) and power-law curves have near-zero second derivatives in log-space; isolated spikes or dropouts trigger large $\mathcal{R}_{\text{int}}$.

### 2.2 Neighbour-Anchored Smoothness $\chi^2$ ($\chi^2_{\text{smooth}} / \text{ndf}$)
* **Category:** Error-calibrated intrinsic smoothness.
* **Formula:**
  $$\chi^2_{\text{smooth}} / \text{ndf} = \frac{1}{N_h - 2} \sum_{i=2}^{N_h - 1} \frac{\left(\eta_i - \left[w_{i-1}\eta_{i-1} + w_{i+1}\eta_{i+1}\right]\right)^2}{2 \left(w_{i-1}^2 \sigma_{\eta,i-1}^2 + w_{i+1}^2 \sigma_{\eta,i+1}^2\right)}, \qquad \sigma_{\eta,i} = \frac{\sigma_{C,i}}{\max(C_i, \epsilon \bar{C})}$$
* **Implementation Notes:** Anchoring the denominator to the neighbouring uncertainties $(\sigma_{\eta,i-1}, \sigma_{\eta,i+1})$ rather than $\sigma_{\eta,i}$ prevents a high-weight MC spike in bin $i$ from excusing itself via its own inflated error bar, while still forgiving normal Poisson scatter in wide tail bins.

### 2.3 Kish's Effective Sample Size ($N_{\text{eff}}$) & Minimum Tail Count
* **Category:** Monte Carlo convergence & weight-spike pathology.
* **Formula:**
  $$N_{\text{eff}} = \frac{\left(\sum_{i=1}^{N_h} C_i \Delta x_i\right)^2}{\sum_{i=1}^{N_h} \left(\sigma_{C,i} \Delta x_i\right)^2}$$
* **Implementation Notes:** If a single bin blows up due to one huge MC weight ($C_k \gg \text{others}, \sigma_{C,k} \approx C_k$), $N_{\text{eff}} \to 1.0$, immediately flagging the corrupted histogram.

### 2.4 Interior Zero-Sink / Hole Fraction ($f_{\text{holes}}$)
* **Category:** Unphysical dropout & negative-weight detector.
* **Formula:**
  $$f_{\text{holes}} = \frac{\sum_{i \in \mathcal{H}} \Delta x_i}{\sum_{i=1}^{N_h} \Delta x_i}, \qquad \mathcal{H} = \Big\{ i \;\Big|\; C_i \le 0 \;\text{ and }\; \max_{m > i}(C_m) > 0 \Big\}$$

### 2.5 Bin-Width Invariant Differential Entropy ($H_{\text{diff}}$)
* **Category:** Intrinsic dispersion / concentration measure.
* **Formula:**
  $$H_{\text{diff}} = -\sum_{i=1}^{N_h} P_i \ln\!\left(\frac{P_i}{\Delta x_i}\right), \qquad P_i = \frac{C_i \Delta x_i}{\sum_{m=1}^{N_h} C_m \Delta x_m}$$
* **Implementation Notes:** Dividing $P_i$ by $\Delta x_i$ inside the log makes $H_{\text{diff}}$ invariant to arbitrary bin splitting/merging.

### 2.6 Intrinsic Exponential Tail Decay Fit ($\hat{\lambda}, R^2_{\ln}$)
* **Category:** Tail integrity & spectral hardness characterization.
* **Formula:** Fit $\eta_i = \hat{\alpha} - \hat{\lambda} x_{\text{mid},i}$ across tail bins $i \in \mathcal{T}$ with weights $w_i = \sigma_{\eta,i}^{-2}$:
  $$\hat{\lambda} = -\frac{\sum_{i \in \mathcal{T}} w_i (x_{\text{mid},i} - \bar{x}_w)(\eta_i - \bar{\eta}_w)}{\sum_{i \in \mathcal{T}} w_i (x_{\text{mid},i} - \bar{x}_w)^2}, \qquad R^2_{\ln} = 1 - \frac{\sum_{i \in \mathcal{T}} w_i \left(\eta_i - (\hat{\alpha} - \hat{\lambda} x_{\text{mid},i})\right)^2}{\sum_{i \in \mathcal{T}} w_i (\eta_i - \bar{\eta}_w)^2}$$

### 2.7 Ensemble Consensus Log-Barycenter Distance ($D_{\text{consensus}}(s)$)
* **Category:** Reference-free comparative outlier / consensus ranking across $K$ curves.
* **Formula:** Construct the robust ensemble pseudo-reference in each bin via the cross-curve median density $\hat{R}_i^{\text{cons}} = \text{median}_{k \in \{1..K\}}(C_{k,i})$ and median error $\hat{\sigma}_{R,i}^{\text{cons}} = \text{median}_{k}(\sigma_{k,i})$, then evaluate **Metric 1.2 ($\text{wMAPE}_{\text{shrunk}}$)** or **Metric 1.1 ($\chi^2_{\lambda,\text{ref}}/\text{ndf}$)** against $\hat{R}_i^{\text{cons}}$.

---

## Part 3: Multi-Metric & Multi-Histogram Set Ranking Pipeline

To rank $K$ candidate configurations ($s = 1, \dots, K$) across $M$ distinct histograms ($h = 1, \dots, M$) using $J$ metrics ($j = 1, \dots, J$) fairly:

### Step 1: Metric Normalization (Choose One Mode)

* **Mode A — Floored Plot-Median Ratio (Best Default for Fixed Candidate Pools):**
  Normalizes each metric $j$ on plot $h$ by the cross-configuration median $\text{med}_{h,j} = \text{median}_{s}(m_{s,h,j})$, clamped by a noise floor $\tau_{\text{floor},j}$ so curves inside statistical noise ($\ll \tau_{\text{floor},j}$) are not falsely penalized:
  $$\tilde{m}_{s,h,j} = \frac{m_{s,h,j}}{\max\!\left(\text{med}_{h,j},\, \tau_{\text{floor},j}\right)}$$
* **Mode B — Hinged Physics Desirability Thresholds (Best Pool-Independent Mode):**
  Maps each metric between an ideal noise floor $\tau_{\text{good},j}$ (below which penalty is $0$) and an unacceptable threshold $\tau_{\text{bad},j}$ (where penalty reaches $1.0$):
  $$\tilde{m}_{s,h,j} = \max\!\left(0,\; \frac{m_{s,h,j} - \tau_{\text{good},j}}{\tau_{\text{bad},j} - \tau_{\text{good},j}}\right)$$

| Metric $j$ | Noise Floor $\tau_{\text{floor},j}$ (Mode A) | Ideal Threshold $\tau_{\text{good},j}$ (Mode B) | Veto Threshold $\tau_{\text{bad},j}$ (Mode B) |
|---|---|---|---|
| **1. $\chi^2_{\lambda,\text{ref}} / \text{ndf}$** | $1.00$ | $1.00$ | $3.00$ |
| **2. $\text{wMAPE}_{\text{shrunk}}$** | $0.03$ ($3\%$) | $0.02$ ($2\%$) | $0.15$ ($15\%$) |
| **3. $\|\tilde{\beta}_1\|$ (Log-Slope)** | $0.05$ ($5\%$) | $0.03$ ($3\%$) | $0.25$ ($25\%$) |
| **4. $\|Z_{\text{tail}}\|$ (Tail Pull)** | $1.00\sigma$ | $1.00\sigma$ | $3.00\sigma$ |
| **5. $\mathcal{R}_{\Delta^2}$ (Roughness)** | $0.05$ | $0.03$ | $0.30$ |
| **6. $\text{CVaR}_k$ (Top-$k$ Deviance)** | $2.50$ | $2.00$ | $9.00$ |

### Step 2: Per-Histogram Composite Loss ($L_{s,h}$)
Combine the $J$ normalized metrics on histogram $h$ via Quadratic RMS (with optional metric weights $u_j$, default $u_j = 1$):
$$L_{s,h} = \sqrt{\frac{\sum_{j=1}^{J} u_j \, \tilde{m}_{s,h,j}^2}{\sum_{j=1}^{J} u_j}}$$

### Step 3: Cross-Histogram Set Aggregation ($\mathcal{L}_2(s)$ & Hard Veto)
Aggregate $L_{s,h}$ across all $M$ histograms using the **Observable-Balanced Quadratic RMS** (with optional observable priority weights $w_h$, default $w_h = 1$):
$$\mathcal{L}_2(s) = \sqrt{\frac{\sum_{h=1}^{M} w_h \, L_{s,h}^2}{\sum_{h=1}^{M} w_h}}, \qquad \mathcal{L}_\infty(s) = \max_{h \in \{1..M\}} \left(\sqrt{w_h}\, L_{s,h}\right)$$
* **Ranking Rule:** Filter out Pareto-dominated configurations, apply a hard veto if $\mathcal{L}_\infty(s)$ exceeds your maximum single-plot failure tolerance, and rank surviving configurations in ascending order of $\mathcal{L}_2(s)$.

---

## Part 4: Reference Python / NumPy Implementation

```python
import numpy as np
from typing import Dict, List

def compute_reference_metrics(
    edges: np.ndarray,
    C: np.ndarray,
    sigma_C: np.ndarray,
    R: np.ndarray,
    sigma_R: np.ndarray,
    eps: float = 0.01,
    tau_wmape: float = 0.10,
    tail_cdf_thresh: float = 0.90
) -> Dict[str, float]:
    """
    Computes the core 6 reference-based metrics on a variable-bin-width histogram.
    Inputs C, sigma_C, R, sigma_R are differential densities (dN/dx); edges has length N_bins + 1.
    """
    dx = np.diff(edges)
    x_a, x_b = edges[:-1], edges[1:]
    x_mid = 0.5 * (x_a + x_b)
    L_x = edges[-1] - edges[0]
    N_bins = len(dx)

    # Safe reference floor to prevent division by zero in empty reference bins
    R_pos = R[R > 0]
    R_floor = 1e-12 if len(R_pos) == 0 else 1e-6 * np.min(R_pos)
    R_safe = np.maximum(R, R_floor)
    sigma_R_safe = np.where(sigma_R > 0, sigma_R, R_safe)

    # 1. Ref-Anchored Baker-Cousins Poisson Deviance (Chi2_lambda_ref / ndf)
    n_R = R_safe * dx
    n_C_star = np.maximum(np.maximum(C, 0.0) * dx, 0.5 * (R_safe / np.maximum(R, R_floor)))
    n_eff_R = (R_safe / sigma_R_safe) ** 2
    scale_i = np.where(n_R > 0, n_eff_R / n_R, 1.0)
    d2_ref = 2.0 * scale_i * (n_C_star - n_R + n_R * np.log(n_R / n_C_star))
    d2_ref = np.maximum(0.0, d2_ref)
    chi2_lambda_ref = float(np.mean(d2_ref))

    # Regularized Symmetric Log-Ratio l_i and uncertainty sigma_ln_r
    C_reg = np.maximum(C, 0.0) + eps * R_safe
    ell = np.log(C_reg / R_safe)
    sigma_ln_r = np.sqrt((sigma_C / C_reg) ** 2 + (sigma_R_safe / R_safe) ** 2)

    # 2. Empirical-Bayes Shrunk Axis-Weighted Error (wMAPE_shrunk)
    s_shrink = (tau_wmape ** 2) / (tau_wmape ** 2 + sigma_ln_r ** 2)
    wmape_shrunk = float(np.sum(dx * s_shrink * np.abs(ell)) / L_x)

    # Lafferty-Wyatt Exponential Bin Barycenters <x>_i
    ratio_next = R_safe[1:] / R_safe[:-1]
    lam_local = np.zeros(N_bins)
    lam_local[:-1] = np.maximum(0.0, -np.log(np.maximum(ratio_next, 1e-12)) / dx[:-1])
    lam_local[-1] = lam_local[-2] if N_bins > 1 else 0.0
    u = lam_local * dx
    x_bary = np.where(
        u > 1e-3,
        x_a + (1.0 / np.maximum(lam_local, 1e-12)) - dx / np.expm1(np.maximum(u, 1e-12)),
        x_mid
    )

    # 3. Barycenter Log-Ratio Slope (|tilde_beta_1|)
    w_slope = 1.0 / (sigma_ln_r ** 2 + 0.01 ** 2)
    x_bar = np.sum(w_slope * x_bary) / np.sum(w_slope)
    ell_bar = np.sum(w_slope * ell) / np.sum(w_slope)
    denom_slope = np.sum(w_slope * (x_bary - x_bar) ** 2)
    beta1_norm = float(L_x * np.abs(np.sum(w_slope * (x_bary - x_bar) * (ell - ell_bar)) / denom_slope)) if denom_slope > 0 else 0.0

    # 4. Integrated Tail Pull (|Z_tail|)
    cum_R = np.cumsum(n_R) / np.sum(n_R)
    cdf_left = np.concatenate(([0.0], cum_R[:-1]))
    tail_mask = cdf_left >= tail_cdf_thresh
    if np.sum(tail_mask) < 2:
        tail_mask = np.zeros(N_bins, dtype=bool)
        tail_mask[-max(2, N_bins // 4):] = True
    tail_diff = np.sum((C[tail_mask] - R[tail_mask]) * dx[tail_mask])
    tail_err = np.sqrt(np.sum((sigma_C[tail_mask] ** 2 + sigma_R_safe[tail_mask] ** 2) * (dx[tail_mask] ** 2)))
    z_tail = float(np.abs(tail_diff) / tail_err) if tail_err > 0 else 0.0

    # 5. Discrete Log-Ratio Second-Difference Roughness (R_Delta2)
    if N_bins >= 3:
        dx_span = x_bary[2:] - x_bary[:-2]
        w_left = (x_bary[2:] - x_bary[1:-1]) / dx_span
        w_right = (x_bary[1:-1] - x_bary[:-2]) / dx_span
        kappa = ell[1:-1] - (w_left * ell[:-2] + w_right * ell[2:])
        r_delta2 = float(np.sqrt(np.mean(kappa ** 2)))
    else:
        r_delta2 = 0.0

    # 6. Top-k Worst-Bin Conditional Value-at-Risk (CVaR_k)
    k_worst = max(3, int(np.ceil(0.10 * N_bins)))
    cvar_k = float(np.mean(np.sort(d2_ref)[::-1][:k_worst]))

    return {
        "chi2_lambda_ref": chi2_lambda_ref,
        "wmape_shrunk": wmape_shrunk,
        "beta1_norm": beta1_norm,
        "z_tail": z_tail,
        "r_delta2": r_delta2,
        "cvar_k": cvar_k,
    }


def compute_intrinsic_metrics(
    edges: np.ndarray,
    C: np.ndarray,
    sigma_C: np.ndarray,
    eps: float = 0.01
) -> Dict[str, float]:
    """
    Computes singular (reference-free) intrinsic quality metrics for a single curve.
    """
    dx = np.diff(edges)
    x_mid = 0.5 * (edges[:-1] + edges[1:])
    L_x = edges[-1] - edges[0]
    N_bins = len(dx)

    total_yield = np.sum(np.maximum(C, 0.0) * dx)
    C_bar = total_yield / L_x if L_x > 0 else 1.0
    C_star = np.maximum(C, eps * max(C_bar, 1e-12))
    eta = np.log(C_star)
    sigma_eta = np.where(sigma_C > 0, sigma_C / C_star, 1.0)

    # 1 & 2. Intrinsic Log-Roughness (R_int) & Smoothness Chi2 (chi2_smooth)
    if N_bins >= 3:
        dx_span = x_mid[2:] - x_mid[:-2]
        w_l = (x_mid[2:] - x_mid[1:-1]) / dx_span
        w_r = (x_mid[1:-1] - x_mid[:-2]) / dx_span
        jump = eta[1:-1] - (w_l * eta[:-2] + w_r * eta[2:])
        r_int = float(np.sqrt(np.mean(jump ** 2)))
        nbr_var = 2.0 * ((w_l * sigma_eta[:-2]) ** 2 + (w_r * sigma_eta[2:]) ** 2)
        chi2_smooth = float(np.mean((jump ** 2) / np.maximum(nbr_var, 1e-12)))
    else:
        r_int, chi2_smooth = 0.0, 0.0

    # 3. Kish's Effective Sample Size (N_eff)
    denom_neff = np.sum((sigma_C * dx) ** 2)
    n_eff = float((total_yield ** 2) / denom_neff) if denom_neff > 0 else 0.0

    # 4. Interior Zero-Sink / Hole Fraction (f_holes)
    pos_indices = np.where(C > 0)[0]
    last_pos = pos_indices[-1] if len(pos_indices) > 0 else 0
    hole_mask = (C <= 0) & (np.arange(N_bins) < last_pos)
    f_holes = float(np.sum(dx[hole_mask]) / L_x)

    # 5. Bin-Width Invariant Differential Shannon Entropy (H_diff)
    P = (np.maximum(C, 0.0) * dx) / max(total_yield, 1e-12)
    valid = P > 0
    h_diff = float(-np.sum(P[valid] * np.log(P[valid] / dx[valid])))

    return {
        "r_int": r_int,
        "chi2_smooth": chi2_smooth,
        "n_eff": n_eff,
        "f_holes": f_holes,
        "h_diff": h_diff,
    }


def rank_parameter_sets(
    metrics_tensor: np.ndarray,
    floors: np.ndarray,
    metric_weights: np.ndarray = None,
    plot_weights: np.ndarray = None
) -> Dict[str, np.ndarray]:
    """
    Ranks K configurations across M plots and J metrics using Floored Median-Normalized L2 RMS.
    metrics_tensor shape: (K_configs, M_plots, J_metrics)
    floors shape: (J_metrics,)
    """
    K, M, J = metrics_tensor.shape
    if metric_weights is None:
        metric_weights = np.ones(J) / J
    if plot_weights is None:
        plot_weights = np.ones(M) / M

    # Step 2 & 3: Per-plot cross-configuration median with noise floor
    medians = np.median(metrics_tensor, axis=0, keepdims=True)  # shape (1, M, J)
    denom = np.maximum(medians, floors.reshape(1, 1, J))
    norm_metrics = metrics_tensor / denom  # shape (K, M, J)

    # Per-histogram composite RMS loss L_{s,h}
    L_sh = np.sqrt(np.sum(metric_weights.reshape(1, 1, J) * (norm_metrics ** 2), axis=2))  # shape (K, M)

    # Step 4: Observable-balanced L2 RMS and L_inf Minimax across M plots
    L2_score = np.sqrt(np.sum(plot_weights.reshape(1, M) * (L_sh ** 2), axis=1))
    L_inf_score = np.max(L_sh, axis=1)
    ranking_order = np.argsort(L2_score)

    return {
        "L2_score": L2_score,
        "L_inf_score": L_inf_score,
        "L_sh_matrix": L_sh,
        "ranking_order": ranking_order,
    }
```

---

## Part 5: Master Quick-Reference Matrix (0–5 Performance Rating)

| Metric | Mode | Global Norm Shift | Smooth Spectral Tilt | $e^{-\lambda x}$ Wide-Tail Fit | Noisy True Tail Immunity | Interspersed Blow-Up Spikes | Interspersed Zero-Sinks | Multi-Plot Set Ranking |
|---|---|---|---|---|---|---|---|---|
| **1.1 $\chi^2_{\lambda,\text{ref}} / \text{ndf}$** | Ref | **5** | 4 | 3 | **5** | 4 | 4 | 2 |
| **1.2 $\text{wMAPE}_{\text{shrunk}}$** | Ref | **5** | 4 | 4 | **5** | 3 | 3 | 3 |
| **1.3 $\|\tilde{\beta}_1\|$ (Log-Slope)** | Ref | 0 | **5** | **5** | 4 | 1 | 1 | 2 |
| **1.4 $\|Z_{\text{tail}}\|$ (Tail Pull)** | Ref | 2 | 4 | **5** | **5** | 1 | 1 | 2 |
| **1.5 $\mathcal{R}_{\Delta^2}$ (Roughness)** | Ref | 0 | 0 | 1 | 3 | **5** | **5** | 2 |
| **1.6 $\text{CVaR}_k$ (Top-$k$ Bins)** | Ref | 3 | 2 | 3 | 4 | **5** | **5** | 3 |
| **1.7 $\text{wMAPE}_{\text{yield}}$ ($L^1$ Area)** | Ref | **5** | 4 | 0 | **5** | 4 | 1 | 2 |
| **2.1 $\mathcal{R}_{\text{int}}$ (Intrinsic Roughness)** | Intrinsic | 0 | 0 | 3 | 3 | **5** | **5** | 1 |
| **2.2 $\chi^2_{\text{smooth}} / \text{ndf}$** | Intrinsic | 0 | 0 | 4 | 4 | **5** | **5** | 1 |
| **2.3 Kish's $N_{\text{eff}}$** | Intrinsic | 0 | 0 | 2 | 3 | **5** *(MC Weight)* | 1 | 1 |
| **2.4 Hole Fraction $f_{\text{holes}}$** | Intrinsic | 0 | 0 | 3 | 4 | 0 | **5** | 1 |
| **2.7 Consensus $D_{\text{consensus}}$** | Ensemble | 4 | 4 | 4 | 4 | 4 | 4 | 4 |
| **Part 3: Floored Median $\mathcal{L}_2$ RMS** | Aggregator | **5** | **5** | **5** | **5** | **5** | **5** | **5** |



# 1. Reduced Gaussian Chi-Squared ($\chi^2 / \text{ndf}$)

$$\chi^2 / \text{ndf} = \frac{1}{N_{\text{bins}}} \sum_{i=1}^{N_{\text{bins}}} \frac{(C_i - R_i)^2}{\sigma_{C,i}^2 + \sigma_{R,i}^2} = \frac{1}{N_{\text{bins}}} \sum_{i=1}^{N_{\text{bins}}} \left(\frac{r_i - 1}{\sigma_{r,i}}\right)^2$$

## Description

Measures the average squared statistical pull per bin across the histogram, testing whether the candidate curve $C_i$ is compatible with the reference $R_i$ within combined Gaussian uncertainties $\sigma_i = \sqrt{\sigma_{C,i}^2 + \sigma_{R,i}^2}$. The bin width $\Delta x_i$ cancels identically in the numerator and denominator.

## Strength

Performs best on high-statistics bulk distributions ($n_i \gt 20$ events per bin) where uncertainties are symmetric and Gaussian. Heavily penalizes curves that deviate across multiple narrow, high-precision peak or bulk bins.

## Weakness

Suffers from three major blind spots:

* **Bulk Tyranny:** High-uncertainty wide tail bins have tiny weights ($\sigma_i^{-2} \to 0$), so severe tail mismodeling goes unnoticed.
* **Dilution ($1/N_{\text{bins}}$):** One or two broken bins in a 50-bin histogram are averaged out by 48 good bins.
* **Self-Masking Spikes:** If a candidate bin blows up due to a high-weight Monte Carlo event ($C_i \gg R_i$), its error bar $\sigma_{C,i}$ blows up proportionally, yielding a tiny pull ($\sim 1\sigma$) that hides the spike.

---

# 2. Reference-Anchored Baker–Cousins Poisson Deviance ($\chi^2_{\lambda,\text{ref}} / \text{ndf}$)

$$\chi^2_{\lambda,\text{ref}} / \text{ndf} = \frac{2}{N_{\text{bins}}} \sum_{i=1}^{N_{\text{bins}}} \left[ n_{C,i}^* - n_{R,i} + n_{R,i} \ln\!\left(\frac{n_{R,i}}{n_{C,i}^*}\right) \right], \qquad n_{C,i}^* = \max(C_i \Delta x_i,\, 0.5), \quad n_{R,i} = R_i \Delta x_i$$

## Description

Measures the exact log-likelihood ratio between candidate and reference integrated bin counts ($n_i = y_i \Delta x_i$) anchored to the reference statistical precision, with a Jeffreys floor ($\epsilon_n = 0.5$) preventing $\ln(0)$ singularities when a candidate bin sinks to zero.

## Strength

Performs best on variable-width exponential spectra ($e^{-\lambda x}$) extending into low-count tail bins ($n_{R,i} \le 10$). Unlike Gaussian $\chi^2$, it handles asymmetric Poisson errors exactly, refuses to let an inflated candidate error bar $\sigma_{C,i}$ mask an upward blow-up spike ($2n_{C,i}^*$ grows linearly with spike height), and imposes a steep logarithmic penalty when a candidate bin drops to zero ($n_{C,i}^* = 0.5$).

## Weakness

Still averages across $N_{\text{bins}}$, meaning a single moderate anomaly in a histogram with many bins can be diluted if not paired with a tail-specific or outlier-specific metric.

---

# 3. Integrated Yield Bias ($\vert{}\Delta_{\text{norm}}\vert{}$)

$$\vert{}\Delta_{\text{norm}}\vert{} = \frac{\left\vert{} \sum_{i=1}^{N_{\text{bins}}} C_i \Delta x_i - \sum_{i=1}^{N_{\text{bins}}} R_i \Delta x_i \right\vert{}}{\sum_{i=1}^{N_{\text{bins}}} R_i \Delta x_i} = \frac{\vert{}I_C - I_R\vert{}}{I_R}$$

## Description

Measures the fractional error in the total integrated area (total cross-section or event yield) of the candidate curve relative to the reference curve, explicitly weighting differential densities by their bin widths $\Delta x_i$.

## Strength

Directly penalizes curves with a global normalization or luminosity offset ($C_i = \alpha R_i$).

## Weakness

Easily gamed by **cancellation**: a curve that overpredicts the low-$x$ bulk by $+15\%$ and underpredicts the high-$x$ region by $-15\%$ achieves $\vert{}\Delta_{\text{norm}}\vert{} = 0$. Furthermore, in exponential distributions ($e^{-\lambda x}$), over $90\%$ of the integral sits in the first few narrow bins, making it completely blind to the tail.

---

# 4. Barycenter Log-Ratio Slope ($\vert{}\tilde{\beta}_1\vert{}$)

$$\vert{}\tilde{\beta}_1\vert{} = (x_{\max} - x_{\min}) \left\vert{} \frac{\sum_{i=1}^{N_{\text{bins}}} w_i (\langle x \rangle_i - \bar{x}_w)(\ell_i - \bar{\ell}_w)}{\sum_{i=1}^{N_{\text{bins}}} w_i (\langle x \rangle_i - \bar{x}_w)^2} \right\vert{}, \qquad \ell_i = \ln\!\left(\frac{C_i + \epsilon R_i}{R_i}\right), \quad w_i = \sigma_{\ln r, i}^{-2}$$

$$\langle x \rangle_i = x_{a,i} + \frac{1}{\hat{\lambda}_i} - \frac{\Delta x_i}{e^{\hat{\lambda}_i \Delta x_i} - 1} \approx x_{\text{mid},i} - \frac{\hat{\lambda}_i (\Delta x_i)^2}{12}$$

## Description

Measures the dimensionless first-order spectral tilt (hardness/softness bias) across the full horizontal range by fitting a weighted straight line to the log-ratio $\ell_i$ as a function of the true exponential bin barycenters $\langle x \rangle_i$ rather than geometric midpoints $x_{\text{mid},i}$.

## Strength

Performs best for catching curves with the wrong exponential decay rate ($e^{-\lambda_C x}$ vs. $e^{-\lambda_R x}$, where $\ln(C/R) = -(\lambda_C - \lambda_R)x$ is strictly linear) or systematic momentum/energy-scale tilts. Using $\langle x \rangle_i$ eliminates Lafferty–Wyatt wide-bin centering bias, and normalizing by $(x_{\max} - x_{\min})$ makes the slope dimensionless across histograms with different physical units.

## Weakness

Blind to symmetric U-shaped curvature (where the curve is high at both ends and low in the middle, yielding zero linear slope) and blind to isolated, interspersed spikes or dropouts that cancel out across the linear regression.

---

# 5. Integrated Tail Pull ($\vert{}Z_{\text{tail}}\vert{}$)

$$\vert{}Z_{\text{tail}}\vert{} = \frac{\left\vert{} \sum_{i \in \mathcal{T}} (C_i - R_i) \Delta x_i \right\vert{}}{\sqrt{\sum_{i \in \mathcal{T}} (\sigma_{C,i}^2 + \sigma_{R,i}^2) (\Delta x_i)^2}}, \qquad \mathcal{T} = \left\{ i \;\middle\vert{}\; F_R(x_{a,i}) \ge 0.90 \right\}$$

## Description

Pools all wide bins in the upper tail region $\mathcal{T}$ (e.g., the top $5\%\text{–}10\%$ of the reference distribution or all bins above a threshold $x_{\text{tail}}$) into a single integrated tail yield and measures its statistical pull in standard deviations ($\sigma$).

## Strength

Specifically built to catch systematic tail breakdowns in $e^{-\lambda x}$ histograms where individual wide bins have large statistical uncertainties ($\sigma_{r,i} \sim 30\%\text{–}60\%$). By summing over $K_{\text{tail}}$ bins, it boosts signal-to-noise by $\sqrt{K_{\text{tail}}}$: four consecutive wide bins each sitting at an inconclusive $+1.1\sigma$ combine into a decisive $+2.2\sigma$ penalty, while random $\pm 1\sigma$ Poisson noise cancels out.

## Weakness

Ignores the bulk/peak entirely, and can be gamed if a curve oscillates from strongly positive in the mid-tail to strongly negative in the far-tail within $\mathcal{T}$.

---

# 6. Unregularized Axis-Weighted Ratio Error ($\text{wMAPE}_{\text{axis}}$)

$$\text{wMAPE}_{\text{axis}} = \frac{\sum_{i=1}^{N_{\text{bins}}} \Delta x_i \, \vert{}r_i - 1\vert{}}{\sum_{i=1}^{N_{\text{bins}}} \Delta x_i}, \qquad r_i = \frac{C_i}{R_i}$$

## Description

Measures the average relative deviation from $r = 1.0$ on the ratio pad weighted strictly by the physical bin width $\Delta x_i$, treating every unit of the horizontal $x$-axis as equally important regardless of event counts.

## Strength

Performs well when all bins—including wide bins—have high statistical precision ($\sigma_{r,i} \lt 5\%$), preventing 30 narrow peak bins from masking a $25\%$ ratio error across 3 wide bins.

## Weakness

Fails severely in **noisy exponential tails** and **zero-sink dropouts**:

* **Tail Noise Amplification:** In $e^{-\lambda x}$ spectra, the widest tail bins span over $50\%$ of the $x$-axis but have huge statistical noise ($\pm 50\%$). Multiplying random noise by the largest $\Delta x_i$ weights causes true physics curves to get falsely penalized.
* **Zero-Floor Asymmetry:** Because $\vert{}r_i - 1\vert{}$ cannot exceed $1.0$ when $C_i \to 0$, an isolated zero-sink in a narrow bin of width $\Delta x_i / \sum \Delta x = 2\%$ adds only $0.02$ ($2\%$) to $\text{wMAPE}_{\text{axis}}$, going completely under the radar.

---

# 7. Empirical-Bayes Shrunk Axis-Weighted Error ($\text{wMAPE}_{\text{shrunk}}$)

$$\text{wMAPE}_{\text{shrunk}} = \frac{\sum_{i=1}^{N_{\text{bins}}} \Delta x_i \, s_i \, \vert{}\ell_i\vert{}}{\sum_{i=1}^{N_{\text{bins}}} \Delta x_i}, \qquad s_i = \frac{\tau^2}{\tau^2 + \sigma_{\ln r, i}^2}, \quad \ell_i = \ln\!\left(\frac{C_i + \epsilon R_i}{R_i}\right)$$

## Description

Measures the bin-width-weighted symmetric log-ratio error across the physical axis, damped by an Empirical-Bayes shrinkage factor $s_i \in [0, 1]$ controlled by a target model tolerance $\tau$ (typically $\tau = 0.10$).

## Strength

Cures both flaws of unregularized $\text{wMAPE}_{\text{axis}}$. In well-measured narrow or wide bins ($\sigma_{\ln r, i} \ll \tau$), $s_i \approx 1$, giving full $\Delta x_i$ phase-space weighting. In ultra-noisy far-tail bins ($\sigma_{\ln r, i} \gg \tau$), $s_i \to \tau^2/\sigma_{\ln r, i}^2 \ll 1$, automatically filtering out random Poisson spikes so they cannot corrupt the wide-bin weight. Using $\vert{}\ell_i\vert{}$ also treats upward spikes and downward drops symmetrically.

## Weakness

If a single narrow bin ($\Delta x_i \ll \sum \Delta x$) has an isolated glitch, the small geometric factor $\Delta x_i / \sum \Delta x$ still dilutes its contribution unless paired with a glitch metric ($\mathcal{R}_{\Delta^2}$ or $\text{CVaR}_k$).

---

# 8. Discrete Log-Ratio Second-Difference Roughness ($\mathcal{R}_{\Delta^2}$)

$$\mathcal{R}_{\Delta^2} = \sqrt{\frac{1}{N_{\text{bins}}-2} \sum_{i=2}^{N_{\text{bins}}-1} \kappa_i^2}, \qquad \kappa_i = \ell_i - \left[ \frac{(\langle x \rangle_{i+1} - \langle x \rangle_i)\,\ell_{i-1} + (\langle x \rangle_i - \langle x \rangle_{i-1})\,\ell_{i+1}}{\langle x \rangle_{i+1} - \langle x \rangle_{i-1}} \right]$$

## Description

Measures the root-mean-square discrete second derivative (local Laplacian curvature jump $\kappa_i$) of the regularized log-ratio $\ell_i = \ln((C_i + \epsilon R_i)/R_i)$ across adjacent triplets of variable-width bins $(i-1, i, i+1)$.

## Strength

**The #1 metric for penalizing interspersed "funky" bins** (both absurd upward blow-ups $C_i \gg R_i$ and sudden sinks to zero $C_i \to 0$). Because it evaluates local point-to-point jumps in symmetric log-space, an isolated spike of $20\times$ ($\ell_i \approx +3.0$) or a zero-dropout with $\epsilon = 0.01$ ($\ell_i \approx -4.6$) surrounded by good bins ($\ell_{i\pm 1} \approx 0$) creates a massive penalty in bin $i$ and both neighboring stencils, completely immune to inflated error bars $\sigma_{C,i}$.

## Weakness

Completely blind to **smooth global errors**: a curve with a uniform $+50\%$ normalization offset ($\ell_i = \text{const}$) or a steady linear tilt across the entire axis ($\ell_i \propto \langle x \rangle_i$) has $\kappa_i = 0$ everywhere and scores a perfect $\mathcal{R}_{\Delta^2} = 0$.

---

# 9. Top-$k$ Worst-Bin Conditional Value-at-Risk ($\text{CVaR}_k$)

$$\text{CVaR}_k = \frac{1}{k} \sum_{m=1}^{k} d_{\text{ref},(m)}^2, \qquad d_{\text{ref},(1)}^2 \ge d_{\text{ref},(2)}^2 \ge \dots \ge d_{\text{ref},(N_{\text{bins}})}^2$$

## Description

Sorts all bins from worst to best by their Reference-anchored Baker–Cousins deviance $d_{\text{ref},i}^2$ (from Metric #2) and computes the mean of only the **$k$ worst bins** (typically $k = \max(3, \lceil 0.10 N_{\text{bins}} \rceil)$).

## Strength

Eliminates the $1/N_{\text{bins}}$ dilution trap while outperforming the single-bin maximum ($\max_i \vert{}z_i\vert{}$). If a 50-bin curve matches the reference in 47 bins but has 3 interspersed bins that blow up or sink to zero, $\text{CVaR}_3$ averages only those 3 broken bins—delivering the full, undiluted penalty and distinguishing a curve with 3 funky bins from a curve with 1 funky bin.

## Weakness

Ignores performance across the remaining $N_{\text{bins}} - k$ bins; two curves that share the same 3 worst bins will tie on $\text{CVaR}_3$ even if one curve is much cleaner across the other 47 bins.

---

# 10. Symmetric Log-Ratio $L_4$ Norm ($\mathcal{L}_4$)

$$\mathcal{L}_4 = \left( \frac{1}{N_{\text{bins}}} \sum_{i=1}^{N_{\text{bins}}} \left\vert{} \ln\!\left(\frac{\max(C_i, 0) + \epsilon R_i}{R_i}\right) \right\vert{}^4 \right)^{1/4}$$

## Description

Computes the 4th-order power mean ($L_4$ norm) of the regularized log-ratio across all bins.

## Strength

Acts as a smooth, algebraic amplifier for extreme ratio outliers in either direction. Raising $\vert{}\ell_i\vert{}$ to the 4th power weights a $10\times$ blow-up or $10\times$ dropout ($\vert{}\ell_i\vert{} = 2.30 \implies \vert{}\ell_i\vert{}^4 = 28.1$) **$3,500\times$ more heavily** than a normal $10\%$ fluctuation ($\vert{}\ell_i\vert{} = 0.095 \implies \vert{}\ell_i\vert{}^4 = 0.00008$), penalizing both spikes and zero-sinks equally without sorting bins.

## Weakness

Because it does not weight by statistical precision $\sigma_{\ln r, i}^{-1}$, a single noisy wide tail bin with 1 expected event that fluctuates to 0 or 4 events can trigger a high $\mathcal{L}_4$ penalty unless tail bins with $n_{R,i} \lt 5$ are shrinkage-weighted ($s_i \ell_i$).

---

# 11. Lag-1 Deviance Pull Autocorrelation ($\rho_1$)

$$\rho_1 = \frac{\sum_{i=1}^{N_{\text{bins}}-1} (d_i - \bar{d})(d_{i+1} - \bar{d})}{\sum_{i=1}^{N_{\text{bins}}} (d_i - \bar{d})^2}$$

## Description

Measures the serial correlation between adjacent bin pulls $d_i$ and $d_{i+1}$ from left to right across the histogram.

## Strength

Separates **benign statistical scatter** ($\rho_1 \approx 0$, where pulls flip sign randomly from bin to bin) from **systematic shape mismodeling** ($\rho_1 \gt 0.3$, where a curve sits continuously above the reference for 8 bins and continuously below for the next 8 bins), even when both curves have the exact same $\chi^2 / \text{ndf}$.

## Weakness

Unreliable when $N_{\text{bins}} \lt 8$, and gives a **negative** or near-zero value on isolated interspersed spikes (where a single high bin is flanked by normal bins), so it cannot be used alone to penalize point glitches.

---

# 12. Bounded Jensen–Shannon Shape Divergence ($D_{\text{JS}}$)

$$D_{\text{JS}}(P \parallel Q) = \frac{1}{2 \ln 2} \sum_{i=1}^{N_{\text{bins}}} \left[ P_i \ln\!\left(\frac{2 P_i}{P_i + Q_i}\right) + Q_i \ln\!\left(\frac{2 Q_i}{P_i + Q_i}\right) \right] \in [0, 1], \qquad P_i = \frac{C_i \Delta x_i}{I_C}, \quad Q_i = \frac{R_i \Delta x_i}{I_R}$$

## Description

Measures the pure information-theoretic divergence between the unit-normalized probability shapes $P_i$ and $Q_i$, independent of overall normalization $I_C$ and $I_R$.

## Strength

Strictly bounded between $0$ and $1$, symmetric, and—unlike Kullback–Leibler divergence $D_{\text{KL}}$—never blows up to $+\infty$ when a candidate bin sinks to zero ($P_i = 0$ simply contributes $\frac{1}{2\ln 2} Q_i \ln 2$).

## Weakness

Completely blind to global normalization errors ($C_i = 10 R_i$ gives $D_{\text{JS}} = 0$), ignores statistical uncertainties $\sigma_i$, and in $e^{-\lambda x}$ histograms is dominated by the high-probability low-$x$ bulk ($Q_i \gg 0$) while ignoring the far tail ($Q_i \to 0$).

---

# 13. Anderson–Darling Tail-Weighted Shape Distance ($A^2$)

$$A^2 = \sum_{i=1}^{N_{\text{bins}}-1} \frac{\left(F_C(x_i) - F_R(x_i)\right)^2}{F_R(x_i)\left(1 - F_R(x_i)\right)} \, Q_i, \qquad F_C(x_i) = \sum_{m=1}^{i} P_m, \quad F_R(x_i) = \sum_{m=1}^{i} Q_m$$

## Description

Measures the discrepancy between the candidate and reference cumulative distribution functions ($F_C$ vs. $F_R$), inverse-weighted by the binomial tail variance $F_R(x_i)[1 - F_R(x_i)]$.

## Strength

Fixes the tail blindness of $D_{\text{JS}}$, Kolmogorov–Smirnov, and Wasserstein $W_1$ on normalized distributions. Because $1 - F_R(x_i) \propto e^{-\lambda x_i}$ in an exponential tail, dividing by $1 - F_R(x_i)$ amplifies tail shape discrepancies so the high-$x$ tail carries equal statistical weight to the peak.

## Weakness

Like $D_{\text{JS}}$, it operates on unit-normalized cumulative probabilities ($F_C, F_R$), so it is blind to overall normalization offsets and moderately insensitive to narrow, self-canceling bin-to-bin oscillations.

---

# 14. Observable-Balanced Quadratic RMS ($\mathcal{L}_2$ Set Aggregator)

$$\mathcal{L}_2(s) = \sqrt{\frac{1}{M} \sum_{h=1}^{M} w_h \, L_{s,h}^2}$$

## Description

Aggregates the standardized per-histogram loss $L_{s,h}$ of parameter set $s$ across $M$ distinct histograms by taking the root-mean-square over observables (with optional physics priority weights $w_h$).

## Strength

**The most reliable primary ranker across multiple histograms.** Dividing by $M$ (rather than total bins $\sum N_h$) prevents a 60-bin inclusive histogram from drowning out a 6-bin variable-width observable, while squaring $L_{s,h}$ penalizes any parameter set that tries to compensate for a terrible fit on one histogram with slightly better fits on four others.

## Weakness

If one histogram has a much higher irreducible baseline loss across *all* parameter sets (e.g., $L_{s,h_1} \in [3.5, 4.0]$ while $L_{s,h_2} \in [0.8, 1.5]$), that difficult histogram will dominate the sum of squares unless $L_{s,h}$ is standardized across sets or paired with TOPSIS.

---

# 15. Partitioned Fisher's Combined Probability ($X^2_{\text{Fisher}}$ Set Aggregator)

$$X^2_{\text{Fisher}}(s) = -2 \sum_{h=1}^{M} \Big[ \ln(p_{\lambda,s,h}) + \ln(p_{\text{tail},s,h}) \Big]$$

## Description

Combines the exact degrees-of-freedom-adjusted $p$-value of the full histogram ($p_{\lambda,s,h} = 1 - F_{\chi^2}(\chi^2_{\lambda,s,h}; N_h)$) with the integrated tail-pull $p$-value ($p_{\text{tail},s,h} = 2[1 - \Phi(\vert{}Z_{\text{tail},s,h}\vert{})]$) across all $M$ histograms.

## Strength

Automatically corrects for unequal bin counts $N_h$ across histograms (recognizing that $\chi^2/N_h = 1.4$ is fine for $N_h = 5$ but poor for $N_h = 60$) and explicitly prevents bulk bins from masking a $3\sigma$ tail failure. Because $-\ln(p) \to \infty$ as $p \to 0$, a single broken observable immediately demotes the parameter set.

## Weakness

If all candidate parameter sets have very poor absolute fits on a high-precision histogram ($p_{\lambda,s,h} \lt 10^{-16}$), floating-point underflow caps $\ln(p)$, requiring you to fall back to $\mathcal{L}_2(s)$ or TOPSIS.

---

# 16. TOPSIS Relative Closeness ($C_{\text{TOPSIS}}$ Set Aggregator)

$$C_{\text{TOPSIS}}(s) = \frac{D^-(s)}{D^+(s) + D^-(s)} \in [0, 1], \qquad D^+(s) = \sqrt{\sum_{h=1}^{M} w_h^2 \left(\frac{L_{s,h} - L^+_h}{L^-_h - L^+_h}\right)^2}, \quad D^-(s) = \sqrt{\sum_{h=1}^{M} w_h^2 \left(\frac{L^-_h - L_{s,h}}{L^-_h - L^+_h}\right)^2}$$

## Description

Measures each parameter set's relative Euclidean closeness to the virtual ideal best performance ($L^+_h = \min_s L_{s,h}$) and distance from the worst performance ($L^-_h = \max_s L_{s,h}$) achieved across the candidate sets on each histogram.

## Strength

Excels when your $M$ histograms have vastly different baseline modeling difficulties. Normalizing by the empirical range $[L^+_h, L^-_h]$ ensures every observable has equal dynamic range $[0, 1]$ in the final ranking.

## Weakness

Because $L^+_h$ and $L^-_h$ depend on the candidate pool, adding a terrible "dummy" parameter set stretches $L^-_h$ and compresses differences among the top contenders (rank reversal).

---

# 17. Minimax Chebyshev Norm ($\mathcal{L}_\infty$ Set Aggregator)

$$\mathcal{L}_\infty(s) = \max_{h \in \{1, \dots, M\}} \left( w_h \, L_{s,h} \right)$$

## Description

Scores each parameter set strictly by its **single worst-performing histogram** across the entire suite of $M$ observables.

## Strength

Provides an ironclad robustness guarantee: the top-ranked set under $\mathcal{L}_\infty$ is guaranteed to have zero catastrophic failures on any observable.

## Weakness

Too coarse to use as your sole ranker because it completely ignores improvements or degradations across the other $M - 1$ histograms below the maximum. Best used as a **hard veto gate** alongside $\mathcal{L}_2(s)$.

---

# Summary Performance Table (0–5 Rating Across Curve Types)

Ratings range from **$0$ (Completely Blind / Misled)** to **$5$ (Ideal Detection & Penalty)**:

* **Type 1 (Global Norm Shift):** Curve is uniformly scaled up/down ($C_i = \alpha R_i$).
* **Type 2 (Smooth Spectral Tilt):** Curve tilts across $x$, canceling out in total yield.
* **Type 3 ($e^{-x}$ Wide-Tail Breakdown):** Curve diverges systematically in high-uncertainty wide tail bins.
* **Type 4 (Noisy True Tail — False-Positive Immunity):** Curve is physically exact, with random Poisson noise in wide tail bins (*$5$ = does not falsely penalize*).
* **Type 5 (Interspersed Blow-Up Spikes):** Curve has 1–3 isolated $C_i \gg R_i$ spikes (with inflated MC $\sigma_{C,i}$).
* **Type 6 (Interspersed Zero-Sinks):** Curve drops to $C_i \to 0$ in 1–3 isolated bins.
* **Type 7 (Multi-Histogram Compensation):** Set overfits high-$N_h$ bulk histograms while failing a low-$N_h$ observable.

| Metric | Type 1: Global Norm Shift | Type 2: Smooth Spectral Tilt | Type 3: $e^{-x}$ Wide-Tail Breakdown | Type 4: Noisy True Tail (Immunity) | Type 5: Interspersed Blow-Up Spikes | Type 6: Interspersed Zero-Sinks | Type 7: Multi-Hist Compensation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **1. Gaussian $\chi^2 / \text{ndf}$** | 5 | 4 | 1 | 5 | 1 | 2 | 1 |
| **2. Ref-Anchored Poisson $\chi^2_{\lambda,\text{ref}} / \text{ndf}$** | 5 | 4 | 3 | 5 | 4 | 4 | 2 |
| **3. Integrated Yield Bias $\Vert{}\Delta_{\text{norm}}\Vert{}$** | 5 | 0 | 0 | 5 | 2 | 1 | 1 |
| **4. Barycenter Log-Ratio Slope $\Vert{}\tilde{\beta}_1\Vert{}$** | 0 | 5 | 5 | 4 | 1 | 1 | 2 |
| **5. Integrated Tail Pull $\Vert{}Z_{\text{tail}}\Vert{}$** | 2 | 4 | 5 | 5 | 1 | 1 | 2 |
| **6. Unregularized $\text{wMAPE}_{\text{axis}}$** | 4 | 4 | 4 | 0 | 4 | 1 | 2 |
| **7. Shrunk $\text{wMAPE}_{\text{shrunk}}$** | 5 | 4 | 4 | 5 | 3 | 3 | 3 |
| **8. Log-Ratio Roughness $\mathcal{R}_{\Delta^2}$** | 0 | 0 | 1 | 3 | 5 | 5 | 2 |
| **9. Top-$k$ Worst-Bin $\text{CVaR}_k$** | 3 | 2 | 3 | 4 | 5 | 5 | 3 |
| **10. Symmetric Log-Ratio $\mathcal{L}_4$ Norm** | 3 | 3 | 3 | 2 | 5 | 5 | 2 |
| **11. Lag-1 Pull Autocorrelation $\rho_1$** | 0 | 5 | 4 | 4 | 0 | 0 | 1 |
| **12. Jensen–Shannon Divergence $D_{\text{JS}}$** | 0 | 4 | 1 | 4 | 3 | 2 | 2 |
| **13. Anderson–Darling Distance $A^2$** | 0 | 4 | 4 | 3 | 2 | 2 | 2 |
| **14. Observable-Balanced $\mathcal{L}_2$ RMS (Set)** | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| **15. Partitioned Fisher's $X^2_{\text{Fisher}}$ (Set)** | 5 | 4 | 5 | 5 | 4 | 4 | 5 |
| **16. TOPSIS Closeness $C_{\text{TOPSIS}}$ (Set)** | 4 | 4 | 4 | 4 | 4 | 4 | 5 |
| **17. Minimax Chebyshev $\mathcal{L}_\infty$ (Set)** | 3 | 3 | 4 | 4 | 5 | 5 | 5 |