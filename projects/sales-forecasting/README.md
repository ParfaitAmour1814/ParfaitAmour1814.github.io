# Sales Channel Forecasting Model
**Author:** Truong Phat | Pricing & Costing Specialist, Vinamilk  
**Language:** Python 3 | scikit-learn, scipy, pandas, numpy  
**Data:** Anonymised FMCG sales volume (2020–2025) + Vietnam macro indicators

---

## What This Project Does

Linear regression forecasting model for monthly FMCG sales volume across 5 sales channels. Includes rigorous macro variable testing (CPI, interest rate, GDP) with full statistical output — all excluded based on R² and p-value evidence — confirming that average selling price, trend, and seasonality are the dominant predictors of FMCG sales.

---

## Files

| File | Description |
|---|---|
| `sales_forecasting_model.py` | Main Python script — full regression model with feature engineering, train/test split, and channel-level evaluation |
| `SalesForecasting_DummyData.xlsx` | Anonymised input dataset (4 sheets: Monthly Sales, Dim_Product, Dim_Channel, Dim_Date) |
| `SalesForecasting_Results.xlsx` | Model output (3 sheets: Forecast vs Actual, Model Performance, Trend Chart Data) |
| `Vietnam_Macro_Data.csv` | Monthly macro dataset (Jan 2019 – Dec 2025): CPI YoY%, Interest Rate%, GDP Growth% |
| `sales_macro_final.csv` | Combined dataset: monthly sales volume + all 3 macro variables (72 months) |
| `macro_regression_full_results.csv` | Full statistical regression results for all macro variable tests |
| `macro_executive_summary.html` | Executive summary report of macro variable regression analysis |

---

## Methodology

### Primary Model — Linear Regression
```
Sale Volume = β₀ + β₁(Avg Price) + β₂(Trend) + β₃(Seasonality)
             + β₄(Lag_1) + β₅(Lag_12) + β₆(Rolling_MA3)
             + β₇(Covid_Dummy) + β₈(Yearend_Dummy)
```
- **Tool:** `sklearn.linear_model.LinearRegression` (OLS)
- **Evaluation:** R², MAE, MAPE per channel and product group
- **Split:** Train 2020–2024 | Test 2025

### Secondary Reference — Rolling MA Baseline
12-month rolling average used as a naive time-series benchmark to validate whether regression adds value over a simple baseline.

### Macro Variable Testing
Three macro variables were tested individually and in combination using `scipy.stats.linregress` (OLS with full statistical output):

| Variable | R² | p-value | Verdict |
|---|---|---|---|
| CPI YoY % | 1.7% | 0.2745 | ❌ Exclude — not significant |
| Interest Rate % | 5.2% | 0.0532 | ❌ Exclude — borderline, too weak |
| GDP Growth % | 8.9% | 0.0110 | ❌ Exclude — significant but R² too low |
| All 3 Combined | 16.1% (Adj. 12.4%) | 0.0074 | ❌ Exclude — multicollinearity, insufficient fit |

**Conclusion:** Macro variables excluded. FMCG dairy sales exhibit inelastic demand — consumers buy milk regardless of interest rates or GDP fluctuations. Internal pricing is the stronger driver.

---

## Model Results (Primary Model)

| Channel | R² | MAPE | LR vs MA Baseline |
|---|---|---|---|
| Modern Trade | 0.936 | 1.6% | +84.9% better |
| Traditional Trade | 0.932 | 1.8% | +78.2% better |
| HoReCa | 0.927 | 1.7% | +84.6% better |
| Export | 0.945 | 1.5% | +82.0% better |
| E-Commerce | 0.928 | 1.8% | +79.3% better |
| **Overall** | **0.933** | **1.7%** | **+81.8% better** |

---

## Statistical Parameters Used

| Metric | Description |
|---|---|
| **R²** | % of sales variance explained by the model |
| **Adjusted R²** | R² penalised for number of variables (multiple regression) |
| **p-value** | Probability the coefficient is zero — significance test |
| **F-statistic** | Overall model significance |
| **95% Confidence Interval** | Range of the true coefficient value |
| **MAE** | Mean Absolute Error — average prediction error in VND |
| **MAPE** | Mean Absolute Percentage Error — relative prediction accuracy |

---

## Data Sources

- **Sales volume:** Anonymised FMCG transaction data aggregated to monthly level (product × channel × month)
- **CPI:** GSO Vietnam — monthly Consumer Price Index YoY%
- **Interest Rate:** State Bank of Vietnam — refinancing rate (key changes: cuts 2020, hikes Sep-Oct 2022, cuts 2023)
- **GDP:** World Bank / GSO Vietnam — quarterly GDP growth interpolated to monthly

---

## Skills Demonstrated

- **Python ML** — sklearn pipeline, feature engineering, lag variables, seasonal dummies
- **Statistical testing** — OLS regression, p-values, F-statistics, confidence intervals, multicollinearity detection
- **Finance domain** — connecting macro economics to FMCG demand analysis
- **Research rigour** — testing and formally excluding variables with evidence, not assumption
- **Data storytelling** — executive summary communicating statistical findings in business language
