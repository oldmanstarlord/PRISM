# PRISM Viva Questions and Grounded Answers

1. **What is PRISM?**  
   A diagnostic portfolio-risk and market-intelligence system for NIFTY 200 securities. It
   measures historical risk, concentration, co-movement, stress scenarios, news context, and
   model-estimated risk; it does not give investment advice.

2. **Why is PRISM not Modern Portfolio Theory?**  
   It does not estimate expected returns, solve an efficient frontier, or recommend optimal
   weights. It evaluates the risk and structure of an allocation supplied by the user.

3. **Which return convention is used for statistical risk?**  
   Simple daily asset returns combined as $R_{p,t}=\sum_iw_iR_{i,t}$ under a constant-weight,
   daily-rebalanced convention.

4. **Why not linearly combine log returns across assets?**  
   Log returns are additive through time, not across simultaneously held assets. A weighted log
   sum introduces a Jensen gap and does not equal the return of the portfolio wealth process.

5. **How is actual portfolio performance represented?**  
   By the buy-and-hold wealth identity $W_t=Cash_t+\sum_iQ_{i,t}P_{i,t}$, separate from the
   constant-weight statistical-risk series.

6. **How are transactions accounted for?**  
   The ledger is replayed chronologically using weighted-average cost. Buys increase quantity and
   cost, sales realize proceeds less the proportional WAC basis and fees, and overselling fails.

7. **How is volatility calculated?**  
   Sample standard deviation of daily portfolio returns multiplied by $\sqrt{252}$. The 252 factor
   is an annualization convention, not a claim that future volatility is constant.

8. **What is downside semi-deviation?**  
   The square root of the mean squared negative return relative to a zero target, annualized by
   $\sqrt{252}$. It focuses on observations below the target.

9. **How is maximum drawdown different from volatility?**  
   Drawdown is the largest peak-to-trough loss in the discrete wealth path; volatility is dispersion
   of periodic returns. One is path-dependent and the other is not.

10. **Why regularize covariance?**  
    Collinear assets or too few observations can make the sample covariance matrix rank deficient.
    PRISM floors eigenvalues at $10^{-6}\lambda_{max}$ while preserving an exactly zero matrix.

11. **What is Euler risk decomposition?**  
    For $\sigma_p=\sqrt{w^T\Sigma w}$, component volatility is
    $C_i=w_i(\Sigma w)_i/\sigma_p$. Components reconcile to total volatility because volatility is
    homogeneous of degree one.

12. **Can an Euler contribution be negative?**  
    Yes. A negatively covarying holding can reduce portfolio variance. PRISM preserves and labels
    such contributions as hedging effects instead of forcing them to zero.

13. **What do VaR and Expected Shortfall mean here?**  
    They are historical one-day loss estimates at 95% and 99% confidence. Expected Shortfall is the
    average loss beyond VaR. Neither is a guaranteed loss bound.

14. **Why report a Gaussian VaR as well?**  
    It is a transparent parametric comparator. Historical VaR remains important because empirical
    returns can be skewed and heavy-tailed.

15. **What does a stress test prove?**  
    It estimates portfolio sensitivity under stated linear or correlation-shift assumptions. It is
    a scenario calculation, not a forecast and not causal evidence.

16. **What is HHI and effective holdings?**  
    $HHI=\sum_iw_i^2$ measures capital concentration and $N_{eff}=1/HHI$ expresses the equivalent
    number of equally weighted holdings.

17. **What is the diversification ratio?**  
    $DR=(\sum_iw_i\sigma_i)/\sigma_p$. A value above one shows variance reduction relative to the
    weighted standalone volatilities, subject to the estimation window.

18. **Why use a minimum spanning tree?**  
    It compresses a dense correlation graph into an interpretable $N-1$-edge backbone. PRISM uses
    Mantegna distance $d_{ij}=\sqrt{2(1-\rho_{ij})}$ and Kruskal's algorithm.

19. **What information does the MST discard?**  
    For $N$ nodes it discards $(N-1)(N-2)/2$ pairwise edges. A missing tree edge does not mean two
    assets are uncorrelated, and an included edge does not establish causation.

20. **How is sector divergence constructed?**  
    Each stock is regressed on a leave-one-out median return of eligible industry peers over 60
    sessions. Residual moves over 1, 5, and 20 sessions are standardized by residual volatility.

21. **Are the stock and portfolio risk scores machine learning?**  
    No. They are labelled heuristic weighted composites with fixed normalization bounds. Model D
    evaluates their historical ranking skill but does not turn them into advice.

22. **What does Model A predict?**  
    Forward 21-session realized volatility, not returns or price direction. Gradient boosting is
    compared with trailing volatility, EWMA, and HAR-RV baselines under walk-forward testing.

23. **What happens when ML does not beat the baseline?**  
    If improvement is below the 2% governance threshold, the simpler baseline is selected and the
    UI reports that result. The earlier recorded run selected EWMA because ML improvement was only
    1.14%.

24. **How does Model B avoid look-ahead bias?**  
    The Markov-switching regime model exposes filtered probabilities $P(S_t|\mathcal F_t)$, not
    smoothed probabilities that use future observations.

25. **What does Model C's anomaly flag mean?**  
    Isolation Forest and robust MAD scores identify unusual cross-sectional behaviour. The flag has
    no claimed directional or predictive meaning.

26. **How is ML validated chronologically?**  
    Expanding walk-forward splits preserve time order, purge overlapping 21-day targets, apply a
    21-day embargo, and compare out-of-sample losses with non-ML baselines.

27. **How is news prevented from contaminating quantitative risk?**  
    News sentiment is calculated in a separate service and response contract. It never changes
    returns, covariance, beta, volatility, VaR, or Expected Shortfall; its multiplier is explicitly
    heuristic.

28. **How are duplicate and ambiguous news items handled?**  
    SimHash/Hamming distance plus token Jaccard detect likely reprints. Common-word ticker matches
    require corroborating company context and otherwise remain ambiguous/needs-review.

29. **How is tenant isolation implemented?**  
    Supabase bearer tokens identify a UUID owner. Portfolio queries filter by owner, cross-user
    access returns 404, and PostgreSQL RLS policies provide database-level defense in depth.

30. **What prevents a production release today?**  
    The local static, unit, browser-mocked, and offline migration gates can pass, but a GO decision
    also requires live Supabase re-login E2E, clean and restored-copy PostgreSQL migration rehearsal,
    and server-side owner-scoped persistence for notes, journal, review inbox, and browser snapshots.
    These limitations are recorded rather than hidden.
