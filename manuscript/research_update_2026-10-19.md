# Manuscript update: 19 October 2026

The current presentation artifact is the [four-page interview brief, revision 2](interview_brief_v2/brief.pdf)
with [LaTeX source](interview_brief_v2/brief.tex) and an evidence ledger. It describes
CancerOmicsLake as an implemented data-engineering platform and an exploratory
study of candidate-ranking sensitivity. It is suitable for discussion of the
project's research process, technical contribution and limitations.

The repository's older `manuscript.md` describes a historical snapshot. The
four-page brief is an outreach summary, not an accepted paper or evidence that a
superior ranking algorithm was established. Its ledger records the hashes of
the frozen aggregate sources; those research inputs are not included in this
public-facing brief package.

## Main evidence retained

- Frozen expression inventory: 36,456,660 TCGA and 11,240,000 GTEx measurement
  rows. Individual counts cannot be inferred from measurement counts.
- Matched processing: 617 specimens, including 417 tumors and 200 GTEx normals.
  The three primary comparisons use 150 normals; sigmoid colon remains separate.
  Signed-effect Kendall tau-b is 0.556--0.571 across 55,660 shared genes per
  cancer, while mean tie-aware top-50 Jaccard is 0.0026--0.0058.
- Corrected ranking studies showed no top-50 advantage over maximin. Official
  RRA remains a ranking comparator; the shared tumor population prevents an
  independent-list significance interpretation.
- Candidate lists and heldout metrics reproduced in container replay, but 63
  native and 60 paired sensitivity cells failed the original numerical tolerance.
- The limited external preparation comparison matched outputs across 21
  workloads and seven native-script integrations. It did not establish
  end-to-end workflow speed superiority.
- Arora et al. remains literature-level related work. Direct reproduction was
  not executed after access errors at the checked matrix locations on
  16 October 2026; that audit is not evidence of universal data unavailability.

## Later work now included in the brief

| Direction | Executed result | Interpretation |
| --- | --- | --- |
| Evidence contracts | Existing SQL/SHACL/workflow tools matched the prototype over 32 constructed cases, replayed as 192 tool/case/pass decisions. | No unique tested validation capability; false original assertions remained undetectable. |
| Decision-aware recomputation | 233 of 400 distinct events were certified unchanged, but lifecycle cost beat the exact incremental baseline in 0/40 workloads. | A correct bounded certificate did not provide a practical advantage under the declared budget. |
| Exact arithmetic | Existing exact methods agreed on 46 comparisons; 36 of 6,624 process attempts failed, confined to binary64 extreme-value execution. | A useful baseline evaluation, without a new arithmetic algorithm or repair of archived sensitivity failures. |
| Rank abstention | The top-k label screen passed in 3,600 synthetic datasets; one moderate-signal cell had invalid pair directions in 47/200 joint-bootstrap versus 5/200 Holm datasets. | Pairwise calibration was unsupported; the narrow positive gate cannot justify a confidence-method claim. |
| Claim fragility | Ordinary SQL and Python matched all 112 synthetic alternatives and minimum-change results. | The prepared-catalog test did not establish a unique capability or actual quantification-workflow replay. |

These are exploratory results conditional on their declared fixtures and
workloads. Repeated timing and tool passes are not independent datasets. The
four-page brief keeps these distinctions explicit.

## Remaining scientific and author requirements

The next milestones are independent investigator reproduction, comparable
external endpoint evaluation and fresh evidence chosen before method tuning.
Biological claims require separate validation. Affiliation, correspondence,
funding, interests, precise AI disclosure and responsibility confirmation remain
author-dependent. Public publication and DOI deposit are not enabled by this
interview summary.
