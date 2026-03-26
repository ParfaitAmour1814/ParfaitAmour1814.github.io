"""
Sales Channel Forecasting Model
================================
Author      : Truong Phat
Project     : Sales Channel Forecasting — FMCG Manufacturer
Description : Linear regression model predicting monthly sales volume
              across 5 distribution channels. Features: trend, seasonality
              (sin/cos), lag variables, rolling mean, COVID dummy.
              Macro variables (CPI, GDP, Interest Rate) and marketing spend
              (Account 641) tested as external regressors.

Usage       : python sales_forecasting_model.py
Requires    : pandas, numpy, scikit-learn, scipy
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
TRAIN_END   = '2025-12'    # last month of training data
SALES_FILE  = 'SalesForecasting_DummyData.xlsx'
MACRO_FILE  = 'Vietnam_Macro_Data.csv'

# ── 1. LOAD & AGGREGATE SALES ─────────────────────────────────────────────────
print("Loading sales data...")
df = pd.read_excel(SALES_FILE)
df['TRX_DATE']   = pd.to_datetime(df['TRX_DATE'])
df['YEAR_MONTH'] = df['TRX_DATE'].dt.to_period('M').astype(str)

monthly = (df.groupby('YEAR_MONTH')['Sale']
             .sum()
             .reset_index()
             .rename(columns={'Sale': 'TOTAL_SALE'})
             .sort_values('YEAR_MONTH')
             .reset_index(drop=True))

# ── 2. TRAIN / VALIDATION SPLIT ───────────────────────────────────────────────
train = monthly[monthly['YEAR_MONTH'] <= TRAIN_END].copy().reset_index(drop=True)
val   = monthly[monthly['YEAR_MONTH'] >  TRAIN_END].copy().reset_index(drop=True)

print(f"Training  : {len(train)} months | {train.YEAR_MONTH.min()} → {train.YEAR_MONTH.max()}")
print(f"Validation: {len(val)}  months | {val.YEAR_MONTH.min()} → {val.YEAR_MONTH.max()}")

# ── 3. FEATURE ENGINEERING ────────────────────────────────────────────────────
def add_features(df, trend_start=1):
    """Add time-series features to a monthly sales DataFrame."""
    d = df.copy()
    d['TREND']     = range(trend_start, trend_start + len(d))
    d['MONTH_NUM'] = pd.to_datetime(d['YEAR_MONTH']).dt.month
    d['SIN_12']    = np.sin(2 * np.pi * d['MONTH_NUM'] / 12)
    d['COS_12']    = np.cos(2 * np.pi * d['MONTH_NUM'] / 12)
    d['SIN_6']     = np.sin(2 * np.pi * d['MONTH_NUM'] / 6)
    d['SALE_LAG1'] = d['TOTAL_SALE'].shift(1)
    d['ROLL_MA3']  = d['TOTAL_SALE'].rolling(3).mean()
    d['COVID_DIP'] = ((pd.to_datetime(d['YEAR_MONTH']).dt.year == 2021) &
                      (pd.to_datetime(d['YEAR_MONTH']).dt.month.isin([7, 8, 9]))).astype(int)
    d['YEAREND']   = pd.to_datetime(d['YEAR_MONTH']).dt.month.isin([11, 12]).astype(int)
    return d

train = add_features(train, trend_start=1)
train = train.dropna().reset_index(drop=True)

FEATURES = ['TREND', 'SIN_12', 'COS_12', 'SIN_6',
            'SALE_LAG1', 'ROLL_MA3', 'COVID_DIP', 'YEAREND']

# ── 4. TRAIN MODEL ────────────────────────────────────────────────────────────
model = LinearRegression()
model.fit(train[FEATURES], train['TOTAL_SALE'])

y_pred_train = model.predict(train[FEATURES])
r2   = r2_score(train['TOTAL_SALE'], y_pred_train)
mae  = mean_absolute_error(train['TOTAL_SALE'], y_pred_train)
mape = np.mean(np.abs((train['TOTAL_SALE'] - y_pred_train) / train['TOTAL_SALE'])) * 100

print(f"\n── In-Sample Performance ──────────────────────")
print(f"  R²    : {r2:.4f}")
print(f"  MAE   : {mae/1e6:.1f}M VND")
print(f"  MAPE  : {mape:.2f}%")

# ── 5. OUT-OF-SAMPLE VALIDATION ───────────────────────────────────────────────
all_sales = list(train['TOTAL_SALE'])
results   = []

for i, row in val.iterrows():
    trend_val = len(train) + i + 1
    month_num = pd.to_datetime(row['YEAR_MONTH']).month

    X_pred = pd.DataFrame({
        'TREND':     [trend_val],
        'SIN_12':    [np.sin(2 * np.pi * month_num / 12)],
        'COS_12':    [np.cos(2 * np.pi * month_num / 12)],
        'SIN_6':     [np.sin(2 * np.pi * month_num / 6)],
        'SALE_LAG1': [all_sales[-1]],
        'ROLL_MA3':  [np.mean(all_sales[-3:])],
        'COVID_DIP': [0],
        'YEAREND':   [1 if month_num in [11, 12] else 0],
    })

    predicted = model.predict(X_pred)[0]
    actual    = row['TOTAL_SALE']
    pct_error = abs(actual - predicted) / actual * 100

    results.append({
        'YEAR_MONTH': row['YEAR_MONTH'],
        'ACTUAL':     round(actual, 0),
        'PREDICTED':  round(predicted, 0),
        'ERROR':      round(actual - predicted, 0),
        'MAPE_PCT':   round(pct_error, 2),
    })
    all_sales.append(actual)

val_df = pd.DataFrame(results)
print(f"\n── Out-of-Sample Validation ───────────────────")
print(val_df.to_string(index=False))
print(f"\n  Overall MAPE : {val_df['MAPE_PCT'].mean():.2f}%")

val_df.to_csv('validation_results.csv', index=False, encoding='utf-8-sig')
print("\nSaved: validation_results.csv")

# ── 6. MACRO VARIABLE REGRESSION TEST ─────────────────────────────────────────
print(f"\n── Macro Variable Regression Test ─────────────")
try:
    macro = pd.read_csv(MACRO_FILE)
    merged = monthly.merge(macro[['YEAR_MONTH', 'CPI_YOY_PCT',
                                   'INTEREST_RATE_PCT', 'GDP_GROWTH_PCT']],
                           on='YEAR_MONTH', how='inner')
    merged = merged[merged['YEAR_MONTH'] <= TRAIN_END].dropna()

    macro_vars = ['CPI_YOY_PCT', 'INTEREST_RATE_PCT', 'GDP_GROWTH_PCT']
    for var in macro_vars:
        slope, intercept, r, p, se = stats.linregress(
            merged[var], merged['TOTAL_SALE'])
        print(f"  {var:<25}: R²={r**2:.4f}  p={p:.4f}  "
              f"{'✅ Significant' if p < 0.05 else '❌ Not significant'}")
except FileNotFoundError:
    print("  Vietnam_Macro_Data.csv not found — skipping macro test")
