# PRISM Specification: Portfolio Diversification & Shock Simulation (FR-I1, FR-I2)

## 1. Executive Summary

This specification formalizes the quantitative formulations, regulatory constraints, and execution requirements for:
1. **Portfolio Diversification Engine (FR-I1)**: Dual Effective Number of Bets (ENB) metrics, MST-cluster concentration analysis, and candidate diversification suggestions.
2. **Stress Shock Simulator (FR-I2)**: Pairwise regression beta sensitivity modeling and Minimum Spanning Tree (MST) path decay propagation.

Strict adherence to PRISM Authority principles:
- **Descriptive Risk Only**: No price forecasts or investment recommendations. Suggestions are strictly framed as `"would reduce concentration"` and never use `"buy"` or `"invest"`.
- **Mandatory Disclaimers**: All shock simulations display the prominent banner:
  > *"Scenario estimate, not a prediction. Hypothetical stress scenarios model historical co-movement and statistical sensitivities. They do not constitute forward price forecasts, guarantees, or investment advice."*
- **Traceability & Result Envelope (D3)**: Every run records configuration fingerprint, input data cutoff, methodology version, and explicit limitations.

---

## 2. Effective Number of Bets (ENB) Formulations (SRS OQ-5)

### 2.1 Risk-Contribution Entropy ENB (Primary Default)

Measures effective bets based on how evenly risk contributions are distributed across assets:

$$\text{ENB}_{\text{entropy}} = \exp\left(-\sum_{i=1}^N p_i \ln p_i\right)$$

Where:
- $p_i = \max(0, \text{PRC}_i)$ is the non-negative portfolio percentage risk contribution of asset $i$, normalized such that $\sum_{i=1}^N p_i = 1$.
- If $\sum p_i \le 0$ (e.g., non-positive total portfolio risk), $\text{ENB}_{\text{entropy}} = 1.0$.

#### Worked Example:
- **Scenario A (Equal Risk)**: 4 assets with equal risk contribution $p = [0.25, 0.25, 0.25, 0.25]$.
  $$H = -\sum_{i=1}^4 0.25 \ln(0.25) = -4 \times (0.25 \times -1.3863) = 1.3863$$
  $$\text{ENB}_{\text{entropy}} = \exp(1.3863) = 4.0$$
- **Scenario B (Concentrated Risk)**: 4 assets where 1 asset accounts for 97% of risk: $p = [0.97, 0.01, 0.01, 0.01]$.
  $$H \approx 0.169 \implies \text{ENB}_{\text{entropy}} = \exp(0.169) \approx 1.18$$

### 2.2 Eigenvalue Decomposition ENB (Secondary Reference)

Measures effective dimensions from the spectral decomposition of the shrunk correlation matrix $C$:

$$\text{ENB}_{\text{eigen}} = \frac{\left(\sum_{i=1}^N \lambda_i\right)^2}{\sum_{i=1}^N \lambda_i^2} = \frac{N^2}{\sum_{i=1}^N \lambda_i^2}$$

Where $\lambda_i \ge 0$ are the eigenvalues of $C$ (with $\sum \lambda_i = \text{Tr}(C) = N$).

#### Worked Example:
- **Uncorrelated Assets ($C = I_N$, $N=4$)**:
  All $\lambda_i = 1.0 \implies \left(\sum \lambda_i\right)^2 = 16$, $\sum \lambda_i^2 = 4 \implies \text{ENB}_{\text{eigen}} = 16 / 4 = 4.0$.
- **Perfect Collinearity ($C = \mathbf{1}\mathbf{1}^T$, $N=4$)**:
  $\lambda_1 = 4.0, \lambda_{2,3,4} = 0 \implies \left(\sum \lambda_i\right)^2 = 16$, $\sum \lambda_i^2 = 16 \implies \text{ENB}_{\text{eigen}} = 16 / 16 = 1.0$.

---

## 3. MST Cluster Concentration & Candidate Suggestions

### 3.1 Cluster Concentration Analysis
Holdings are mapped to their respective clusters from the latest approved Layer 2 Minimum Spanning Tree run (`correlation-mst-v1`).
- Cluster weights $W_c = \sum_{i \in c} w_i$ are computed.
- If $W_c \ge 0.40$ (configurable via `high_concentration_threshold`), an alert finding is generated:
  > *"Cluster concentration: K of N holdings sit in MST cluster 'C', representing X% of total portfolio weight."*

### 3.2 Candidate Suggestions
To reduce concentration in dominant clusters without making investment recommendations:
1. Universe filter: `confidence >= 60.0`, `adv_20 >= 10,000,000 INR`.
2. Compute average pairwise correlation between universe candidates and current portfolio holdings.
3. Select candidates with lowest correlation, outputting:
   > *"Adding {SYMBOL} would reduce concentration in cluster {C} due to low correlation ({R}) with portfolio holdings."*

---

## 4. Shock Simulator Formulations (SRS OQ-6)

### 4.1 Pairwise Regression Beta Propagation (Default)
Given a shocked asset $s$ subject to hypothetical return $\Delta r_s \in [-50\%, +50\%]$:

$$\beta_{j,s} = \frac{\text{Cov}(r_j, r_s)}{\text{Var}(r_s)}$$

$$\text{impact}_j = \begin{cases} \Delta r_s & \text{if } j = s \\ \beta_{j,s} \times \Delta r_s & \text{if } j \ne s \end{cases}$$

$$\text{Portfolio Impact} = \sum_{j \in \text{holdings}} w_j \times \text{impact}_j$$

### 4.2 MST-Path Decay Mode (Alternative Scenario)
Given the unique tree path $P(s, j) = \{(u_1, u_2), \dots, (u_{k-1}, u_k)\}$ connecting asset $s$ to asset $j$ in the Minimum Spanning Tree:

$$D_{s,j} = \prod_{(u,v) \in P(s,j)} \max(0, \rho_{u,v})$$

$$\text{impact}_j = \begin{cases} \Delta r_s & \text{if } j = s \\ D_{s,j} \times \Delta r_s & \text{if } j \ne s \end{cases}$$
