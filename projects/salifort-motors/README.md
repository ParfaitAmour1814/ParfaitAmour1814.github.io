# Employee Turnover Prediction — Salifort Motors
**Author:** Truong Phat | Google Advanced Data Analytics Certificate · Course 7 Capstone  
**Language:** Python 3 | scikit-learn, XGBoost, pandas, matplotlib, seaborn  
**Dataset:** 14,999 employee records · 10 features · Binary classification (left = 1/0)

---

## What This Project Does

Built and compared 4 classification models to predict whether an employee will leave Salifort Motors, using self-reported HR survey data. The goal was to identify the key drivers of turnover and provide actionable recommendations to the leadership team to improve employee retention.

---

## Files

| File | Description |
|---|---|
| `index.html` | Interactive project presentation with charts and findings |
| `Salifort_Motors_notebook.html` | Full Jupyter notebook — EDA, model building, evaluation |
| `README.md` | This file |

---

## Dataset

| Column | Type | Description |
|---|---|---|
| `satisfaction_level` | float | Employee self-reported satisfaction (0–1) |
| `last_evaluation` | float | Last performance review score (0–1) |
| `number_project` | int | Number of projects assigned |
| `average_monthly_hours` | int | Avg hours worked per month |
| `time_spend_company` | int | Tenure in years |
| `work_accident` | int | Whether employee had a work accident |
| `left` | int | **Target** — whether employee left (1) or stayed (0) |
| `promotion_last_5years` | int | Whether promoted in last 5 years |
| `department` | str | Employee's department |
| `salary` | str | Salary level (low / medium / high) |

---

## Methodology

**Framework:** Google PACE (Plan → Analyze → Construct → Execute)

**Feature Engineering:**
- Created `overworked` binary flag: avg monthly hours > 175
- Tenure buckets for grouping analysis
- Removed potential data leakage features before final model training

**Train/Test Split:** 80/20 stratified split

---

## Model Results

| Model | Accuracy | Precision | Recall | F1 | AUC |
|---|---|---|---|---|---|
| Logistic Regression | 83% | 80% | 83% | 80% | — |
| Decision Tree | 96.2% | 87.0% | 90.4% | 88.7% | 93.8% |
| **Random Forest** ★ | **96.2%+** | **87%+** | **90%+** | **88.7%+** | **93.8%+** |
| XGBoost | ~96% | ~87% | ~90% | ~88% | ~93% |

**Best model:** Random Forest — modestly outperformed Decision Tree across all metrics.  
**Most interpretable:** Logistic Regression — useful for stakeholder communication despite lower accuracy.

---

## Key Findings

**Top 4 features by importance (Random Forest):**
1. `last_evaluation` — performance score is the strongest predictor
2. `number_project` — U-shaped risk (too few = disengaged, too many = burned out)
3. `tenure` — 4-year mark is a critical inflection point
4. `overworked` — working 200+ hours/month strongly predicts departure

**Core insight:** Employees are systematically overworked. The company's evaluation system rewards overwork, creating a perverse incentive that drives high performers out.

---

## Business Recommendations

- Cap projects per employee at 5 — the 6–7 project range has a 48–61% turnover rate
- Investigate why 4-year tenured employees are disproportionately dissatisfied
- Rebalance evaluation criteria — high scores should not require 200+ hours/month
- Conduct regular pulse surveys and act on results
- Clarify overtime pay policies company-wide

---

## Skills Demonstrated

- **Python ML** — sklearn pipeline, model selection, hyperparameter tuning
- **Classification metrics** — Accuracy, Precision, Recall, F1, AUC-ROC, confusion matrix
- **Feature engineering** — binary flags, bucketing, leakage detection
- **EDA** — distribution analysis, correlation heatmaps, group comparisons
- **Business communication** — translating model results into executive recommendations
