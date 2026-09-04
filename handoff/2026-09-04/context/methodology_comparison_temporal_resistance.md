# Methodology comparison: temporal cheetah resistance

Updated 2026-09-02 after the first 2012–2024 effective-cost comparison.

## Diagnostic result

The existing temporal resistance builder produced less than 1% effective-cost change for every robust link. Inspection showed that the builder varied only built-up fraction and nighttime lights. It omitted the three MODIS VCF fields even though the locked protocol identifies tree, non-tree vegetation, and bare ground as dynamic and states that VCF carries the temporal vegetation signal.

This means the first temporal output is a valid **anthropogenic-change-only sensitivity result**, but it is not a complete implementation of the protocol's dynamic covariate set and must not be treated as the final temporal result.

## Comparison with published methods

| Study | Relevant method | Agreement with this project | Required response |
|---|---|---|---|
| Moqanaki & Cushman (2017; online 2016), DOI 10.1111/acv.12281 | Factorial least-cost paths and resistant kernels; resistance from topographic complexity, roads, surface water, protection and linearly scaled nighttime lights; each resistance parameter tested at half and twice its original value | Supports fixed cores/sources, least-cost analysis, human-development and terrain variables, linear lights scaling, and explicit sensitivity analysis | Retain the existing anthropogenic model as a scenario; test vegetation contribution at half/base/double strength rather than selecting one post hoc |
| Klaassen & Broekhuis (2018), DOI 10.1002/ece3.4269 | GPS-collar habitat selection across multiple scales; cheetahs avoided people and steep slopes and selected semiclosed habitat and open/semiclosed edge | Supports human pressure and terrain while showing that vegetation structure cannot simply be omitted | Include continuous vegetation in a separate, transparent scenario; acknowledge that 1-km VCF composition is not true fine-scale edge density |
| Weise et al. (2017), DOI 10.7717/peerj.4096 | Regional southern African cheetah distribution constrained using human and cattle/sheep/goat density thresholds and ecoregion context | Supports inclusion of livestock/human pressure and regional-scale caution | Retain livestock as a static exposure layer; do not interpret it as observed movement resistance or temporal change |
| Zeller et al. (2012), DOI 10.1007/s10980-012-9737-0 | Review found no universal resistance parameterization and emphasized uncertainty in variables, scales and transformations | Supports an ensemble rather than a single claimed-correct surface | Report scenario agreement and uncertainty; do not choose the vegetation-inclusive result merely because it produces more change |

## Predeclared correction

Create three additional temporal sensitivity scenarios without replacing or deleting the existing anthropogenic-only surfaces:

- vegetation-low: anthropogenic 70%, vegetation 10%, terrain 20%;
- vegetation-balanced: anthropogenic 60%, vegetation 20%, terrain 20%;
- vegetation-high: anthropogenic 40%, vegetation 40%, terrain 20%.

The 10/20/40% sequence implements the half/base/double sensitivity logic used by Moqanaki & Cushman. The anthropogenic component retains its already documented internal weights: built 30%, roads 30%, livestock 30%, and lights 10%.

Vegetation resistance is a conservative regional proxy for sparse/bare cover: continuous tree and non-tree cover jointly represent vegetated cover, while the VCF bare field and the residual vegetation deficit represent increasing resistance. This does **not** claim to measure fine-scale habitat edge, hunting habitat, or empirical movement selection. Dense woody vegetation is not independently penalized because the available literature supports semiclosed cover and does not justify a universal regional tree-cover cutoff.

The original anthropogenic-only scenario remains in the ensemble. If conclusions change across vegetation weights, that instability is reported as model uncertainty rather than resolved by choosing the preferred-looking output.
