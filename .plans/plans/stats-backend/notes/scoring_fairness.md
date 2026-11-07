Dividing by the median only solves **one** type of unfairness: **Scale Location** (putting a metric whose typical value is $1.5$ on the same footing as one whose typical value is $0.04$).

However, four other types of unfairness can still skew a multi-metric score even after median normalization:

1. **Spread / Variance Unfairness:** Metric A might cluster tightly around its median ($[0.95, 1.05]$), while Metric B swings wildly around its median ($[0.20, 4.00]$). When added together, Metric B completely dictates the winner because its spread is $20\times$ wider.
2. **Overfitting Unfairness:** A curve with $\chi^2/\text{ndf} = 0.4$ gets a "twice as good" score as $\chi^2/\text{ndf} = 0.8$, even though both are completely inside statistical noise ($< 1.0$) and $0.4$ is just fitting random noise.
3. **Pool-Dependence Unfairness:** If you add or remove candidate curves, the median shifts, which can flip the ranking between two remaining curves.
4. **Double-Counting (Collinearity) Unfairness:** If 3 of your metrics are slightly different ways of measuring bulk fit and only 1 measures the tail, bulk fit gets a $3\text{-to-}1$ voting majority.

Below are the **7 primary academic alternatives** to median normalization, each targeting a specific definition of "fairness."

---

# 1. Scale-Invariant Geometric Mean (Log-Additive Scoring)

$$S_{\text{geom}}(s) = \left( \prod_{j=1}^{J} \left( m_{s,j} + \tau_j \right)^{w_j} \right)^{1 / \sum w_j} = \exp\!\left( \frac{\sum_{j=1}^{J} w_j \ln(m_{s,j} + \tau_j)}{\sum_{j=1}^{J} w_j} \right)$$

## Description

Combines multiple metrics $j = 1, \dots, J$ by multiplying them together (with small noise floors $\tau_j$ to prevent zeros) rather than adding them, which is equivalent to averaging their logarithms.

## Strength (Scale-Free Without Any Reference Statistic)

In decision theory, the Geometric Mean is the **only** aggregation function that achieves **exact scale fairness without normalizing by a median, mean, or min-max across candidates**. If Metric 1 is measured in units $100\times$ larger than Metric 2 ($m_1 \to 100 m_1$), multiplying by $100$ simply pulls out front as a constant factor $100^{w_1/\sum w}$ for *every* candidate curve. Therefore, a $20\%$ improvement in Metric 1 always trades off equally against a $20\%$ improvement in Metric 2, and the ranking is $100\%$ immune to which other curves are in your candidate pool.

## Weakness

Because it is multiplicative, it rewards percentage reductions equally across the board; it does not equalize metrics that have naturally different dynamic spreads across candidates.

---

# 2. Robust Median–MAD Standardization (Robust $Z$-Score)

$$Z_{\text{rob}}(s, j) = \frac{m_{s,j} - \text{med}_j}{\max\!\left(\text{MAD}_j,\, \tau_{\text{spread},j}\right)}, \qquad \text{MAD}_j = 1.4826 \times \text{median}_{s}\!\Big( \big\vert{} m_{s,j} - \text{med}_j \big\vert{} \Big)$$

## Description

Centers each metric at its cross-candidate median ($\text{med}_j$) and divides by the **Median Absolute Deviation ($\text{MAD}_j$)**—the outlier-proof equivalent of standard deviation (or the Interquartile Range, $\text{IQR}_j = Q_{75} - Q_{25}$).

## Strength (Equalizes Spread & Sensitivity)

Fixes the biggest flaw of simple median division (**Spread Unfairness**). If all candidate curves are clustered within $\pm 5\%$ on $\chi^2/\text{ndf}$ but vary by $\pm 80\%$ on Log-Ratio Slope $\vert{}\tilde{\beta}_1\vert{}$, simple median division lets the slope metric dominate $16\text{-to-}1$. Dividing by $\text{MAD}_j$ forces every metric to have the **exact same unit spread ($\pm 1\text{ MAD}$)** across the candidate curves, while remaining completely immune to a single broken curve blowing up to $1,000$ (which would ruin a standard mean/$\sigma$ $Z$-score).

## Weakness

Can produce negative values (for curves better than the median), so before plugging into an RMS ($L_2$) sum, shift it via $\tilde{Z}_{s,j} = \ln(1 + e^{Z_{\text{rob}}(s,j)})$ (Softplus) so better-than-median curves approach $0$ rather than squaring negative numbers back into positive penalties.

---

# 3. Hinged Physics-Threshold Scaling (Harrington Desirability Functions)

$$\tilde{m}_{s,j} = \max\!\left( 0,\; \frac{m_{s,j} - \tau_{\text{good},j}}{\tau_{\text{bad},j} - \tau_{\text{good},j}} \right)$$

## Description

Instead of normalizing metrics against *other candidate curves* (like median or min-max), you normalize each metric against **two fixed, physically meaningful thresholds**:

* $\tau_{\text{good},j}$ (**Indifference / Ideal Threshold**): The level below which a curve is statistically indistinguishable from truth (e.g., $\chi^2/\text{ndf} \le 1.0$, $\vert{}Z_{\text{tail}}\vert{} \le 1.0\sigma$, $\text{wMAPE}_{\text{shrunk}} \le 2\%$).
* $\tau_{\text{bad},j}$ (**Unacceptable / Veto Threshold**): The level at which a curve is clearly broken (e.g., $\chi^2/\text{ndf} = 3.0$, $\vert{}Z_{\text{tail}}\vert{} = 3.0\sigma$, $\text{wMAPE}_{\text{shrunk}} = 15\%$).

## Strength (Stops Overfitting & Pool Manipulation)

1. **Zero Reward for Overfitting Noise:** Any curve scoring better than $\tau_{\text{good},j}$ is clamped to $\tilde{m}_{s,j} = 0$. A curve with $\chi^2/\text{ndf} = 0.5$ gets no unfair credit over a curve with $\chi^2/\text{ndf} = 0.98$—both have zero penalty beyond statistical noise.
2. **100% Pool-Independent:** Your score depends only on the curve and the reference data, never on whether other curves in the plot are terrible or good.
3. **Universal Meaning:** Across every metric and every plot, $\tilde{m} = 0$ means *"statistically ideal"* and $\tilde{m} \ge 1.0$ means *"outside acceptable tolerance."*

## Weakness

Requires you to choose sensible domain thresholds $(\tau_{\text{good},j}, \tau_{\text{bad},j})$ for each of your 5–6 metrics once at the start of the analysis.

---

# 4. Exact $p$-Value / Surprisal Transformation (Statistical Probability Currency)

$$S_{\text{surprisal}}(s, j) = -\ln\!\Big( p_j(m_{s,j}) \Big) \qquad \text{or} \qquad Z_{\text{eq}}(s, j) = \Phi^{-1}\!\Big( 1 - p_j(m_{s,j}) \Big)$$

## Description

Converts each raw metric $m_{s,j}$ into its exact null-hypothesis tail probability $p_j(m_{s,j})$ (the probability that a true model would produce a metric value that large purely by random fluctuations), and maps it to **Shannon Surprisal ($-\ln p$)** or **Equivalent Gaussian $\sigma$ ($Z_{\text{eq}}$)**.

## Strength (Accounts for Degrees of Freedom & Non-Linearity)

Makes metrics fair in terms of **statistical evidence**. For example, $\chi^2/\text{ndf} = 1.5$ in a 6-bin plot has $p = 0.17$ ($Z_{\text{eq}} = 0.95\sigma$), whereas $\chi^2/\text{ndf} = 1.5$ in a 100-bin plot has $p = 0.0013$ ($Z_{\text{eq}} = 3.0\sigma$). Surprisal normalization automatically adjusts for bin counts $N_h$ and sampling distributions without any empirical tuning parameters.

## Weakness

Only works cleanly for metrics with known analytical null distributions ($\chi^2_\lambda$, $\vert{}Z_{\text{tail}}\vert{}$, Runs test $Z_{\text{runs}}$, Anderson–Darling $A^2$). For empirical shape metrics like $\mathcal{R}_{\Delta^2}$ or $\text{wMAPE}_{\text{shrunk}}$, $p_j$ must be estimated via toy Monte Carlo bootstrap.

---

# 5. Mahalanobis / CRITIC Decorrelation Weighting (Anti-Double-Counting Fairness)

$$D_{\text{Mahal}}(s) = \sqrt{ \tilde{\mathbf{m}}_s^T \, R_{\text{corr}}^{-1} \, \tilde{\mathbf{m}}_s } \qquad \text{or} \qquad w_j^{\text{CRITIC}} = \frac{c_j}{\sum_{l=1}^J c_l}, \quad c_j = \sum_{k=1}^{J} \left( 1 - \vert{}\rho_{jk}\vert{} \right)$$

## Description

Measures the correlation $\rho_{jk}$ between every pair of metrics $(j, k)$ across your plots and configurations, and downweights metrics that strongly overlap with each other using either the inverse correlation matrix $R_{\text{corr}}^{-1}$ (Mahalanobis distance) or **Diakoulaki's CRITIC weights** ($w_j^{\text{CRITIC}}$).

## Strength (Eliminates Metric Redundancy Bias)

Solves **Collinearity / Double-Counting Unfairness**. Suppose you compute 4 metrics that all respond to bulk normalization/shape ($\rho \approx 0.85$ with each other) and 1 metric that catches isolated spikes ($\mathcal{R}_{\Delta^2}$, $\rho \approx 0.05$ with the others). An unweighted average gives bulk behavior $80\%$ of the total score and spike behavior only $20\%$. CRITIC or Mahalanobis weighting automatically detects that the first 4 metrics are saying the same thing and scales down their individual weights so each **independent physical feature** gets equal representation.

## Weakness

Requires enough data points (configurations $\times$ plots $\ge 15$) to estimate the rank correlation matrix $\rho_{jk}$ reliably.

---

# 6. Pairwise Outranking with Indifference Zones (PROMETHEE II)

$$\pi(A, B) = \sum_{j=1}^{J} w_j \, \Psi_j\!\big( m_{B,j} - m_{A,j} \big), \qquad \Psi_j(\Delta) = \begin{cases} 0 & \text{if } \Delta \le q_j \text{ (Noise/Tie)} \\ \frac{\Delta - q_j}{p_j - q_j} & \text{if } q_j \lt \Delta \lt p_j \\ 1 & \text{if } \Delta \ge p_j \text{ (Clear Win)} \end{cases}$$

$$\Phi_{\text{net}}(A) = \frac{1}{K-1} \sum_{B \neq A} \Big[ \pi(A, B) - \pi(B, A) \Big] \in [-1, +1]$$

## Description

Compares every pair of configurations $(A, B)$ head-to-head on each metric $j$ using a bounded preference function $\Psi_j(\Delta) \in [0, 1]$ with an **Indifference Threshold ($q_j$)** and a **Strict Preference Threshold ($p_j$)**, then ranks configurations by their net head-to-head win margin $\Phi_{\text{net}}(A)$.

## Strength (Fixes Both Borda Rank Noise and Cardinal Outlier Blow-Ups)

Combines the best properties of value-averaging and rank-averaging:

1. **No Fake Rank Penalties for Noise ($\Delta \le q_j$):** If Curve A scores $\chi^2/\text{ndf} = 1.01$ and Curve B scores $1.03$ (difference $\Delta = 0.02 \le q_j$), $\Psi_j = 0$—neither gets a win over the other.
2. **Bounded Outlier Impact ($\Delta \ge p_j$):** Once Curve A beats Curve B by a decisive margin $p_j$, the preference score caps at $1.0$, so a single plot where a curve blows up to $10,000$ cannot distort the head-to-head scores between the other curves.

## Weakness

Because it is a pairwise tournament score, adding or removing curves can slightly shift net margins $\Phi_{\text{net}}$, and it caps the penalty of a $100\times$ blow-up at the same $1.0$ loss as a $5\times$ blow-up once $\Delta \ge p_j$.

---

# 7. Min-Max Range Normalization (TOPSIS / Empirical Range Scaling)

$$\tilde{m}_{s,j} = \frac{m_{s,j} - \min_k(m_{k,j})}{\max_k(m_{k,j}) - \min_k(m_{k,j})} \in [0, 1]$$

## Description

Linearly stretches each metric so the best candidate curve on that plot sits at $0.0$ and the worst candidate curve sits at $1.0$.

## Strength

Guarantees every metric spans the exact same $[0, 1]$ interval before combining.

## Weakness (Least Reliable When Outliers Exist)

Highly vulnerable to **Outlier Compression**: if 4 configurations score $\{1.0,\, 1.1,\, 1.2,\, 1.3\}$ and 1 broken configuration scores $50.0$, the denominator becomes $50.0 - 1.0 = 49.0$, squishing the 4 good configurations into $\{0.000,\, 0.002,\, 0.004,\, 0.006\}$—effectively erasing that metric's ability to distinguish the top contenders! (Always prefer **Robust Median–MAD (#2)** or **Hinged Thresholds (#3)** over Min-Max).

---

# Summary Comparison Table: Rating Fairness Methods (0–5 Scale)

Ratings range from **$0$ (Fails Completely)** to **$5$ (Optimal Fairness)**:

* **Scale Fairness:** Prevents high-number metrics ($\sim 10$) from drowning out small-number metrics ($\sim 0.02$).
* **Spread Fairness:** Prevents widely varying metrics from drowning out tightly clustered metrics.
* **Outlier Immunity:** One broken curve ($m = 1000$) does not distort the scaling of the remaining curves.
* **Overfitting Guard:** Does not falsely reward curves for fitting random noise below the $1\sigma$ floor.
* **Pool Independence:** A curve's normalized score does not shift if other curves are added or removed.
* **Anti-Redundancy:** Prevents correlated/overlapping metrics from double-counting the same feature.

| Normalization / Scoring Method | Scale Fairness | Spread Fairness | Outlier Immunity | Overfitting Guard | Pool Independence | Anti-Redundancy |
| --- | --- | --- | --- | --- | --- | --- |
| **Baseline: Floored Median Ratio** ($m / \max(\text{med}, \tau)$) | **5** | 2 | **5** | 4 | 3 | 0 |
| **1. Geometric Mean** ($\prod (m_j + \tau_j)^{w_j}$) | **5** | 2 | 4 | 4 | **5** | 0 |
| **2. Robust Median–MAD** ($(m - \text{med})/\text{MAD}$) | **5** | **5** | **5** | 3 | 2 | 0 |
| **3. Hinged Physics Thresholds** ($\max(0, \frac{m - \tau_{\text{good}}}{\tau_{\text{bad}} - \tau_{\text{good}}})$) | **5** | 4 | **5** | **5** | **5** | 0 |
| **4. Exact Surprisal / $p$-Value** ($-\ln p_j(m)$) | **5** | **5** | 4 | **5** | **5** | 0 |
| **5. Mahalanobis / CRITIC Decorrelation** | 3 | 4 | 3 | 2 | 2 | **5** |
| **6. PROMETHEE II Outranking** (Pairwise $\Psi_j$) | **5** | 4 | **5** | **5** | 2 | 0 |
| **7. Min-Max / TOPSIS Range** ($(m - \min)/(\max - \min)$) | **5** | 4 | **0** | 1 | 0 | 0 |

### Practical Recommendation

* If you want **zero pool dependence** and **zero overfitting rewards**: use **#3 (Hinged Physics Thresholds)**.
* If your candidate pool is fixed and you want **every metric to have equal discriminative spread**: use **#2 (Robust Median–MAD)** (or your **Floored Median Ratio**) paired with **#5 (CRITIC weights)** if any of your metrics overlap.