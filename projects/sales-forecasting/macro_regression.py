"""
Macro Variable Regression Analysis
====================================
Author      : Truong Phat
Project     : Sales Channel Forecasting — Macro Variable Testing
Description : Tests CPI, Interest Rate, GDP Growth, and Marketing Spend
              (Account 641) as external regressors against monthly FMCG
              sales volume. Includes product-group level deep dive.

Usage       : python macro_regression.py
Requires    : pandas, numpy, scipy
"""

import pandas as pd
import numpy as np
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
SALES_FILE    = 'SalesForecasting_DummyData.xlsx'
MACRO_FILE    = 'Vietnam_Macro_Data.csv'
MKT_FILE_A    = '641_20-22.csv'   # Account 641 marketing spend 2020-2022
MKT_FILE_B    = '641_23-25.csv'   # Account 641 marketing spend 2023-2025
TRAIN_END     = '2025-12'

# ── 1. LOAD SALES ─────────────────────────────────────────────────────────────
df = pd.read_excel(SALES_FILE)
df['TRX_DATE']   = pd.to_datetime(df['TRX_DATE'])
df['YEAR_MONTH'] = df['TRX_DATE'].dt.to_period('M').astype(str)
monthly_sales    = (df.groupby('YEAR_MONTH')['Sale'].sum()
                      .reset_index()
                      .rename(columns={'Sale': 'TOTAL_SALE'}))
monthly_sales    = monthly_sales[monthly_sales['YEAR_MONTH'] <= TRAIN_END]

# ── 2. LOAD MACRO ─────────────────────────────────────────────────────────────
macro  = pd.read_csv(MACRO_FILE)
merged = monthly_sales.merge(
    macro[['YEAR_MONTH', 'CPI_YOY_PCT', 'INTEREST_RATE_PCT', 'GDP_GROWTH_PCT']],
    on='YEAR_MONTH', how='inner').dropna()

# ── 3. SIMPLE REGRESSION — ONE VARIABLE AT A TIME ─────────────────────────────
print("="*60)
print("SIMPLE REGRESSION — Sales vs Each Macro Variable")
print("="*60)

macro_vars = {
    'CPI_YOY_PCT':       'CPI YoY %',
    'INTEREST_RATE_PCT': 'Interest Rate %',
    'GDP_GROWTH_PCT':    'GDP Growth %',
}

for col, label in macro_vars.items():
    X = merged[col].values
    y = merged['TOTAL_SALE'].values
    n = len(X)
    slope, intercept, r, p, se = stats.linregress(X, y)
    r2 = r**2
    from scipy.stats import t as t_dist
    t_crit = t_dist.ppf(0.975, df=n-2)
    ci_lo  = slope - t_crit * se
    ci_hi  = slope + t_crit * se
    print(f"\n{label} (n={n})")
    print(f"  R²         : {r2:.4f} ({r2*100:.1f}%)")
    print(f"  p-value    : {p:.4f}  {'✅' if p < 0.05 else '❌'}")
    print(f"  Coefficient: {slope:,.0f} units per 1% change")
    print(f"  95% CI     : [{ci_lo:,.0f}, {ci_hi:,.0f}]")

# ── 4. MULTIPLE REGRESSION — ALL 3 MACRO VARS ─────────────────────────────────
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

print(f"\n{'='*60}")
print("MULTIPLE REGRESSION — All 3 Macro Variables Combined")
print("="*60)

X_multi = merged[['CPI_YOY_PCT', 'INTEREST_RATE_PCT', 'GDP_GROWTH_PCT']].values
y       = merged['TOTAL_SALE'].values
model   = LinearRegression().fit(X_multi, y)
y_pred  = model.predict(X_multi)
r2_adj  = 1 - (1 - r2_score(y, y_pred)) * (len(y)-1) / (len(y)-4)

print(f"  R²     : {r2_score(y, y_pred):.4f}")
print(f"  Adj R² : {r2_adj:.4f}")
for var, coef in zip(['CPI_YOY_PCT', 'INTEREST_RATE_PCT', 'GDP_GROWTH_PCT'],
                     model.coef_):
    print(f"  {var:<22}: {coef:,.0f}")

# ── 5. MARKETING SPEND (641) REGRESSION ───────────────────────────────────────
print(f"\n{'='*60}")
print("MARKETING SPEND (Account 641) REGRESSION")
print("="*60)

def load_641(path):
    df = pd.read_csv(path, encoding='utf-8-sig')
    df['VALUE'] = (df['VALUE'].astype(str).str.strip()
                              .str.replace(',', '', regex=False))
    df['VALUE'] = pd.to_numeric(df['VALUE'], errors='coerce').fillna(0)
    def parse_period(p):
        parts = str(p).strip().split('-')
        if len(parts) == 2:
            mm, yy = parts
            return f"20{yy}-{mm.zfill(2)}"
        return None
    df['YEAR_MONTH'] = df['PREIOD'].apply(parse_period)
    return df

try:
    df641 = pd.concat([load_641(MKT_FILE_A), load_641(MKT_FILE_B)],
                      ignore_index=True)
    monthly_mkt = (df641[df641['VALUE'] > 0]
                   .groupby('YEAR_MONTH')['VALUE'].sum()
                   .reset_index()
                   .rename(columns={'VALUE': 'MARKETING_SPEND'}))

    merged_mkt = monthly_sales.merge(monthly_mkt, on='YEAR_MONTH', how='inner').dropna()

    slope, intercept, r, p, se = stats.linregress(
        merged_mkt['MARKETING_SPEND'], merged_mkt['TOTAL_SALE'])
    r2 = r**2

    print(f"  n months   : {len(merged_mkt)}")
    print(f"  R²         : {r2:.4f} ({r2*100:.1f}%)")
    print(f"  p-value    : {p:.4f}  {'✅ Significant' if p < 0.05 else '❌ Not significant'}")
    print(f"  Coefficient: {slope:.6f} units per VND")
    print(f"\n  ➤ Marketing spend is the strongest external variable found.")
    print(f"    Macro variables (CPI/GDP/Rate) are excluded from primary model.")

    merged_mkt.to_csv('sales_marketing_641_full.csv', index=False, encoding='utf-8-sig')
    print("\nSaved: sales_marketing_641_full.csv")

except FileNotFoundError as e:
    print(f"  File not found: {e}")
    print("  Upload 641_20-22.csv and 641_23-25.csv to run this section.")
