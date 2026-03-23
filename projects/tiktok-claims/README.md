# TikTok Claims vs Opinions — Full Analytics Pipeline
**Author:** Truong Phat | Google Advanced Data Analytics Certificate · Courses 3–6  
**Language:** Python 3 | scikit-learn, XGBoost, scipy, pandas, seaborn, matplotlib  
**Dataset:** ~19,000 TikTok videos · 12 features · Binary classification (claim vs opinion)

---

## What This Project Does

End-to-end data analytics pipeline across 4 courses using TikTok video data. The goal: build a model that classifies whether a TikTok video makes a **claim** or expresses an **opinion** — helping TikTok's moderation team prioritise user reports more efficiently.

---

## Pipeline Overview

| Course | Stage | Focus |
|---|---|---|
| **Course 3** | EDA & Visualisation | Data distribution, engagement metrics, outliers |
| **Course 4** | Hypothesis Testing | Two-sample t-test — verified vs unverified accounts |
| **Course 5** | Logistic Regression | Predict verified status as intermediate model |
| **Course 6** | ML Classification | Random Forest & XGBoost — claim vs opinion |

---

## Dataset

| Column | Description |
|---|---|
| `claim_status` | **Final target** — claim or opinion |
| `verified_status` | Whether account is verified |
| `video_view_count` | Total views |
| `video_like_count` | Total likes |
| `video_share_count` | Total shares |
| `video_download_count` | Total downloads |
| `video_comment_count` | Total comments |
| `video_duration_sec` | Video length in seconds |
| `author_ban_status` | Whether author is banned/under review |
| `video_transcription_text` | Text transcription of video |

---

## Results by Course

### Course 3 — EDA
- Claim videos have dramatically higher engagement than opinion videos
- View counts: claims avg ~501K vs opinions avg ~5K
- Similar duration distributions between claims and opinions
- Missing values and outliers identified and handled

### Course 4 — Hypothesis Testing
- **H₀:** No difference in view counts between verified and unverified accounts
- **H₁:** Significant difference exists
- **Result:** t-statistic = 25.50, **p-value = 2.6 × 10⁻¹²⁰** → Reject H₀
- Unverified accounts have significantly higher view counts — possible clickbait or bot activity

### Course 5 — Logistic Regression (Verified Status)
| Metric | Verified | Not Verified | Overall |
|---|---|---|---|
| Precision | 74% | 61% | 67% |
| Recall | 46% | 84% | 65% |
| F1 | 57% | 71% | 64% |
| Accuracy | | | **65%** |

Key finding: `video_like_count` dropped due to multicollinearity (r=0.86 with view count)

### Course 6 — ML Classification (Claim vs Opinion)
| Model | Precision | Recall | F1 | Accuracy | Result |
|---|---|---|---|---|---|
| Logistic Regression | 67% | 65% | 64% | 65% | Baseline |
| XGBoost | 99% | 99% | 99% | 99% | Runner-up |
| **Random Forest** ★ | **~100%** | **~100%** | **~100%** | **~100%** | **Champion** |

---

## Key Findings

- **Engagement metrics are perfect predictors** of claim vs opinion — view count, share count, and download count dominate feature importance
- Claims generate ~100x more engagement than opinions — the pattern is so consistent the model achieves near-perfect classification
- **Verified accounts behave differently** — statistically significant difference in view counts vs unverified accounts (p = 2.6e-120)
- **Unverified accounts post more claim-style content** — higher engagement possibly linked to clickbait or coordinated activity

---

## Skills Demonstrated

- **EDA** — distribution analysis, outlier detection, correlation heatmaps, Matplotlib/Seaborn visualisation
- **Statistical testing** — two-sample t-test, p-value interpretation, hypothesis framing
- **Logistic Regression** — class imbalance handling (upsampling), multicollinearity detection, coefficient interpretation
- **ML Classification** — Random Forest, XGBoost, GridSearchCV hyperparameter tuning, feature importance
- **Business communication** — PACE framework, executive summaries, stakeholder recommendations
