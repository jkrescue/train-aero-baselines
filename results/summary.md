# PhysicsNeMo-CFD benchmark summary

Engine: `physicsnemo.cfd.evaluation.benchmarks.engine.run_benchmark`; metrics `l2_pressure`, `l2_pressure_area_weighted`, `l2_shear_stress`, `drag`, `lift` (built-in) + `side_force`, `roll_moment_lee` (registered). Seed 0, default settings, unless stated.

## noses: per fold

| fold | model | Cp L2 | Cp L2 (area-wt) | τx L2 | τy L2 | τz L2 | Cd rel err | Cs err/span | Cl err/span | C_Mx,lee err/span |
|---|---|---|---|---|---|---|---|---|---|---|
| n1 | GeoTransolver | 0.1684 | 0.1549 | 0.0923 | 0.2890 | 0.2409 | 5.0% | 3.9% | 2.0% | 7.2% |
| n1 | SMART | 0.1933 | 0.1710 | 0.0947 | 0.3061 | 0.2484 | 8.7% | 1.7% | 3.7% | 2.8% |
| n1 | AB-UPT | 0.2054 | 0.1994 | 0.0988 | 0.3035 | 0.2765 | 8.1% | 6.8% | 6.9% | 9.9% |
| n2 | GeoTransolver | 0.1409 | 0.1322 | 0.0791 | 0.2314 | 0.2074 | 4.5% | 2.4% | 4.1% | 3.6% |
| n2 | SMART | 0.1297 | 0.1168 | 0.0755 | 0.2253 | 0.2055 | 3.5% | 1.2% | 4.9% | 2.0% |
| n2 | AB-UPT | 0.1808 | 0.1724 | 0.0970 | 0.2619 | 0.2602 | 1.8% | 3.4% | 5.8% | 3.9% |
| n3 | GeoTransolver | 0.1512 | 0.1342 | 0.0862 | 0.2514 | 0.2205 | 3.8% | 1.3% | 1.5% | 2.1% |
| n3 | SMART | 0.1470 | 0.1336 | 0.0886 | 0.2545 | 0.2177 | 4.3% | 0.6% | 2.4% | 1.9% |
| n3 | AB-UPT | 0.2030 | 0.2013 | 0.0920 | 0.2535 | 0.2568 | 1.9% | 2.2% | 6.5% | 1.5% |
| n4 | GeoTransolver | 0.2080 | 0.1925 | 0.0980 | 0.2513 | 0.2495 | 3.4% | 3.6% | 6.0% | 6.8% |
| n4 | SMART | 0.1856 | 0.1681 | 0.0937 | 0.2527 | 0.2437 | 2.3% | 0.5% | 5.2% | 2.9% |
| n4 | AB-UPT | 0.2261 | 0.2197 | 0.0994 | 0.2656 | 0.2642 | 4.5% | 4.3% | 6.1% | 9.8% |

## noses: mean over folds (n = folds available)

| model | n | Cp L2 | Cp L2 (area-wt) | τx L2 | τy L2 | τz L2 | Cd rel err | Cs err/span | Cl err/span | C_Mx,lee err/span | Cs sign ok | C_Mx,lee sign ok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GeoTransolver | 4 | 0.1671 | 0.1535 | 0.0889 | 0.2558 | 0.2296 | 4.2% | 2.8% | 3.4% | 4.9% | 100.0% | 100.0% |
| SMART | 4 | 0.1639 | 0.1474 | 0.0881 | 0.2596 | 0.2288 | 4.7% | 1.0% | 4.1% | 2.4% | 100.0% | 100.0% |
| AB-UPT | 4 | 0.2038 | 0.1982 | 0.0968 | 0.2711 | 0.2644 | 4.1% | 4.2% | 6.3% | 6.3% | 100.0% | 100.0% |

## noses: paired differences over common folds (positive = first model worse)

| pair | metric | folds | mean diff | sd | t = mean/SE | folds where first is worse |
|---|---|---|---|---|---|---|
| SMART − GeoTransolver | Cp L2 | 4 | -0.0032 | 0.0202 | -0.32 | 1/4 |
| SMART − GeoTransolver | C_Mx,lee err/span | 4 | -0.0250 | 0.0199 | -2.52 | 0/4 |
| AB-UPT − GeoTransolver | Cp L2 | 4 | +0.0367 | 0.0140 | +5.25 | 4/4 |
| AB-UPT − GeoTransolver | C_Mx,lee err/span | 4 | +0.0137 | 0.0174 | +1.57 | 3/4 |
| AB-UPT − SMART | Cp L2 | 4 | +0.0399 | 0.0197 | +4.06 | 4/4 |
| AB-UPT − SMART | C_Mx,lee err/span | 4 | +0.0387 | 0.0372 | +2.08 | 3/4 |

## lengths: per fold

| fold | model | Cp L2 | Cp L2 (area-wt) | τx L2 | τy L2 | τz L2 | Cd rel err | Cs err/span | Cl err/span | C_Mx,lee err/span |
|---|---|---|---|---|---|---|---|---|---|---|
| l1 | GeoTransolver | 0.1366 | 0.1209 | 0.0716 | 0.1817 | 0.1915 | 4.6% | 1.8% | 6.3% | 3.9% |
| l1 | SMART | 0.1329 | 0.1216 | 0.0697 | 0.1765 | 0.1970 | 2.1% | 4.6% | 3.4% | 10.6% |
| l1 | AB-UPT | 0.7288 | 0.7536 | 0.1940 | 0.6629 | 0.7376 | 54.8% | 48.2% | 27.7% | 83.3% |
| l2 | GeoTransolver | 0.1765 | 0.1229 | 0.0529 | 0.1663 | 0.1707 | 1.3% | 1.3% | 4.1% | 1.1% |
| l2 | SMART | 0.1723 | 0.1255 | 0.0548 | 0.1717 | 0.1624 | 1.1% | 2.8% | 5.0% | 3.0% |
| l2 | AB-UPT | 0.5701 | 0.5686 | 0.1376 | 0.4939 | 0.5855 | 4.5% | 8.8% | 68.0% | 55.7% |
| l3 | GeoTransolver | 0.1695 | 0.1515 | 0.0731 | 0.2337 | 0.2132 | 0.6% | 5.9% | 15.1% | 6.2% |
| l3 | SMART | 0.1737 | 0.1557 | 0.0767 | 0.2488 | 0.2224 | 2.0% | 5.3% | 5.9% | 10.2% |
| l3 | AB-UPT | 0.6926 | 0.7057 | 0.1564 | 0.5909 | 0.7382 | 12.2% | 32.6% | 70.9% | 84.7% |

## lengths: mean over folds (n = folds available)

| model | n | Cp L2 | Cp L2 (area-wt) | τx L2 | τy L2 | τz L2 | Cd rel err | Cs err/span | Cl err/span | C_Mx,lee err/span | Cs sign ok | C_Mx,lee sign ok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GeoTransolver | 3 | 0.1609 | 0.1318 | 0.0659 | 0.1939 | 0.1918 | 2.2% | 3.0% | 8.5% | 3.8% | 100.0% | 100.0% |
| SMART | 3 | 0.1596 | 0.1342 | 0.0671 | 0.1990 | 0.1939 | 1.7% | 4.3% | 4.8% | 7.9% | 100.0% | 100.0% |
| AB-UPT | 3 | 0.6638 | 0.6760 | 0.1627 | 0.5826 | 0.6871 | 23.8% | 29.9% | 55.5% | 74.6% | 83.3% | 83.3% |

## lengths: paired differences over common folds (positive = first model worse)

| pair | metric | folds | mean diff | sd | t = mean/SE | folds where first is worse |
|---|---|---|---|---|---|---|
| SMART − GeoTransolver | Cp L2 | 3 | -0.0012 | 0.0047 | -0.45 | 1/3 |
| SMART − GeoTransolver | C_Mx,lee err/span | 3 | +0.0416 | 0.0243 | +2.96 | 3/3 |
| AB-UPT − GeoTransolver | Cp L2 | 3 | +0.5030 | 0.1008 | +8.64 | 3/3 |
| AB-UPT − GeoTransolver | C_Mx,lee err/span | 3 | +0.7078 | 0.1409 | +8.70 | 3/3 |
| AB-UPT − SMART | Cp L2 | 3 | +0.5042 | 0.0998 | +8.75 | 3/3 |
| AB-UPT − SMART | C_Mx,lee err/span | 3 | +0.6662 | 0.1212 | +9.52 | 3/3 |

## Seed noise (default settings, seeds 0/1/2)

| fold | model | n | Cp L2 mean | Cp L2 sd | C_Mx,lee err/span mean | values (Cp L2) |
|---|---|---|---|---|---|---|

## Variants (tagged runs: learning rate, points, area-weighted loss, centred AB-UPT, extra seeds)

| fold | run | Cp L2 | Cp L2 (area-wt) | τx L2 | τy L2 | τz L2 | Cd rel err | Cs err/span | Cl err/span | C_Mx,lee err/span |
|---|---|---|---|---|---|---|---|---|---|---|
| n2 | AB-UPT/seed0__lr3e-4 | 0.1715 | 0.1611 | 0.0918 | 0.2471 | 0.2524 | 0.9% | 1.4% | 3.5% | 3.0% |
| n2 | AB-UPT/seed0__lr3e-5 | 0.1946 | 0.1983 | 0.0875 | 0.2492 | 0.2459 | 1.1% | 3.9% | 3.6% | 7.1% |
| n2 | GeoTransolver/seed0__lr1e-2 | 0.1832 | 0.1643 | 0.0768 | 0.2289 | 0.2168 | 2.2% | 2.6% | 3.2% | 7.6% |
| n2 | GeoTransolver/seed0__lr1e-3 | 0.1379 | 0.1213 | 0.0771 | 0.2326 | 0.2094 | 9.1% | 0.7% | 1.9% | 1.0% |
| n2 | SMART/seed0__lr3e-3 | 0.1403 | 0.1283 | 0.0792 | 0.2325 | 0.2072 | 2.6% | 2.2% | 1.9% | 4.3% |
| n2 | SMART/seed0__lr3e-4 | 0.1515 | 0.1413 | 0.0791 | 0.2422 | 0.2081 | 6.4% | 2.8% | 4.2% | 4.9% |
| l1 | AB-UPT/seed0__centered | 0.5623 | 0.5550 | 0.1534 | 0.6155 | 0.6690 | 11.8% | 24.3% | 10.1% | 45.2% |
| l2 | AB-UPT/seed0__centered | 0.4197 | 0.3993 | 0.1173 | 0.3574 | 0.4726 | 9.7% | 12.5% | 14.5% | 44.8% |

## Cost (seed 0, default settings, 300 epochs)

| family | model | runs | parameters | train time / run | peak train memory |
|---|---|---|---|---|---|
| noses | GeoTransolver | 5 | 9.05 M | 31 min | 17.3 GB |
| noses | SMART | 5 | 29.45 M | 44 min | 10.5 GB |
| noses | AB-UPT | 4 | 6.01 M | 142 min | 18.1–18.4 GB |
| lengths | GeoTransolver | 3 | 9.05 M | 20 min | 17.3 GB |
| lengths | SMART | 3 | 29.45 M | 28 min | 10.5 GB |
| lengths | AB-UPT | 3 | 6.01 M | 93 min | 17.2–20.1 GB |
