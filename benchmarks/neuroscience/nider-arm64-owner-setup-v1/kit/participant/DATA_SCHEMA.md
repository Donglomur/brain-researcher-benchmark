# Scientific input

The workbook is a scientific-only projection of the admitted study summary. It retains all 40 original data rows, eight original scientific columns and original missingness. It contains no contact fields or unrelated sheets. The 39 source identifiers are not a certification of independent cohorts.

| Column | Meaning |
|---|---|
| `image name stem` | Source study identifier used by the supplied procedure. |
| `sample size quest` | Questionnaire-related sample-size field. |
| `sample size rating` | Rating-related sample-size field. |
| `sample size amygdala` | Amygdala-related sample-size field. |
| `amyQuestCorr` | Study-level amygdala/questionnaire correlation input. |
| `questSelfRating` | Study-level questionnaire/self-rating correlation input. |
| `amySelfRating` | Study-level amygdala/self-rating correlation input. |
| `questionnaire name` | Questionnaire metadata used by the selected procedure. |

Do not replace missing cells with zero, drop additional rows or infer independence from distinct identifiers. Apply the supplied task’s explicit contrast, inclusion and duplicate-handling conventions. The correlation output is Pearson r; it is distinct from the native Fisher-z random-effects mean. The requested N is the source sample-size sum for the fitted contrast, not a deduplicated count of people. The three hypothetical workbooks preserve the same schema and are procedure checks, not new empirical studies.
