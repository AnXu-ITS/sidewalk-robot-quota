# E2 Margin quantile sweep

Status: COMPLETE

Five prespecified settings, seven outer city folds, 400 predictions per setting; each yields the same 164 evaluated scenarios. Positive uncensored training references fit the frozen log-width-demand estimator; all resolved six-city training rows calibrate positive residuals, including zero/censored references. Archived rounded x is used for fitting/residuals, actual qp/W for inference. NumPy linear quantiles, explicit zero margin at tau=0.

Independent reproduction confirms tau=0 equals frozen M1 and tau=0.80 equals frozen M0, including every abstention and zero. Every positive flow has an exact configuration-matched original 30-seed test; new selective flows do not modify q*. No monotonic service assumption, held-out tuning, or selection of an optimal tau.

```text
 tau city  evaluable  abstain  positive_recommendations  zero_recommendations  PASS  FAIL  missing_or_technical  pass_fraction_among_positives  failure_fraction_among_positives  mean_positive_candidate_flow  median_reference_utilization  utilization_n  reference_exceedance_count  mae_to_reference  withheld_relative_to_tau0  withheld_tau0_flow_PASS  withheld_tau0_flow_FAIL  withheld_tau0_flow_missing
0.00  ALL        164      236                       136                    28   118    18                     0                       0.867647                          0.132353                      6.316176                      0.750000            139                          16          2.426829                          0                        0                        0                           0
0.50  ALL        164      236                       129                    35   119    10                     0                       0.922481                          0.077519                      5.240310                      0.428571            139                           9          3.408537                          7                        4                        3                           0
0.65  ALL        164      236                       122                    42   117     5                     0                       0.959016                          0.040984                      4.836066                      0.300000            139                           4          3.859756                         14                        8                        6                           0
0.80  ALL        164      236                        98                    66    98     0                     0                       1.000000                          0.000000                      4.806122                      0.166667            139                           0          4.536585                         38                       32                        6                           0
0.90  ALL        164      236                        58                   106    58     0                     0                       1.000000                          0.000000                      4.810345                      0.000000            139                           0          5.707317                         78                       71                        7                           0
```

Reference utilization is calculated over all 139 positive-reference scenarios, including zero recommendations and censored q*=20. MAE/exceedance use all 164 evaluable scenarios. Withheld opportunity means tau0 positive and current tau zero; its counterfactual service outcome comes only from the directly tested tau0 flow. This does not assert the untested zero/lower flow is safe.

E2_MARGIN_SWEEP_BY_CITY.csv gives the full fold breakdown. Finite-sample trade-off is descriptive: a stronger margin can lower access and observed failure, but service at individual integer rates is not assumed monotone. Plots are internal analysis assets; no manuscript figures changed.
