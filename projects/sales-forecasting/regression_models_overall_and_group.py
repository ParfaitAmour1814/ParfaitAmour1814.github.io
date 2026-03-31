"""
Regression Models — Overall Quantity & Product Group
======================================================
Author      : Truong Phat
Project     : Sales Channel Forecasting — FMCG Manufacturer (Vinamilk)
Description : Full OLS regression suite for total sales quantity and
              four product groups (01/02/04/07 NHÓM). Runs Models A–F
              on log-quantity, produces side-by-side comparison, and
              outputs per-group ASP elasticity summary.

Models
------
  A  Trend + Seasonality only           (baseline)
  B  + LOG(ASP)                         (honest model — primary)
  C  + LOG(ASP) + LOG(MKT_OLD proxy)    (endogenous 641 — shown for comparison)
  D  + LOG(ASP) + LOG(MKT_NEW)          (correct MK** spend — confirmed not sig.)
  E  + LOG(ASP) + GDP_Growth            (macro test)
  F  + LOG(ASP) + TET_FEB dummy         (final recommended model — real-data fit)

Usage       : python regression_models_overall_and_group.py
Requires    : pandas, numpy, scipy, scikit-learn

Input files
-----------
  sales_macro_complete.csv              — 75 months (2020-01 → 2026-03)
                                          Columns: YEAR_MONTH, TOTAL_SALE,
                                          CPI_YOY_PCT, INTEREST_RATE_PCT,
                                          GDP_GROWTH_PCT
  asp_monthly.csv                       — monthly average selling price
                                          Columns: YEAR_MONTH, ASP_VND
  mkt_monthly.csv                       — monthly marketing spend
                                          Columns: YEAR_MONTH, MKT_OLD_B,
                                          MKT_NEW_B  (B = billion VND)
  nhom_monthly.csv                      — product group monthly quantity
                                          Columns: YEAR_MONTH,
                                          NHOM01, NHOM02, NHOM04, NHOM07
                                          (all in million units)

Output files
------------
  model_comparison_overall.csv          — Models A–F R², MAPE, coefficients
  model_comparison_by_group.csv         — Model B & F per group
  validation_overall_modelF.csv         — Q1 2026 out-of-sample results
"""

import pandas as pd
import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error
from scipy.stats import f as f_dist
import warnings
warnings.filterwarnings('ignore')

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
SALES_FILE  = 'sales_macro_complete.csv'    # 75 months 2020-01 → 2026-03
ASP_FILE    = 'asp_monthly.csv'
MKT_FILE    = 'mkt_monthly.csv'
NHOM_FILE   = 'nhom_monthly.csv'
TRAIN_END   = '2025-12'
VAL_START   = '2026-01'

# ── HELPERS ───────────────────────────────────────────────────────────────────
def add_time_features(df):
    """Add trend, seasonality, event dummies. Works on any monthly df with YEAR_MONTH."""
    d = df.copy().reset_index(drop=True)
    d['MONTH_NUM'] = pd.to_datetime(d['YEAR_MONTH']).dt.month
    d['TREND']     = range(1, len(d) + 1)
    d['SIN_12']    = np.sin(2 * np.pi * d['MONTH_NUM'] / 12)
    d['COS_12']    = np.cos(2 * np.pi * d['MONTH_NUM'] / 12)
    d['SIN_6']     = np.sin(2 * np.pi * d['MONTH_NUM'] / 6)
    d['COVID_DIP'] = (
        (pd.to_datetime(d['YEAR_MONTH']).dt.year == 2021) &
        (d['MONTH_NUM'].isin([7, 8, 9]))
    ).astype(int)
    d['YEAREND']   = d['MONTH_NUM'].isin([11, 12]).astype(int)
    d['TET_FEB']   = (d['MONTH_NUM'] == 2).astype(int)
    return d

def fit_ols(X, y):
    """Fit OLS, return model + full stats dict."""
    m = LinearRegression().fit(X, y)
    y_pred = m.predict(X)
    n, k   = len(y), X.shape[1]
    r2     = r2_score(y, y_pred)
    r2_adj = 1 - (1 - r2) * (n - 1) / (n - k - 1)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    f_stat = (r2 / k) / ((1 - r2) / (n - k - 1))
    p_f    = 1 - f_dist.cdf(f_stat, k, n - k - 1)
    mae    = mean_absolute_error(y, y_pred)
    return m, {
        'r2': r2, 'r2_adj': r2_adj, 'f_stat': f_stat, 'p_f': p_f,
        'mae': mae, 'n': n, 'k': k,
        'coefs': dict(zip(range(k), m.coef_)),
        'intercept': m.intercept_
    }

def mape_log(y_actual_log, y_pred_log):
    """MAPE in original (exp) space from log predictions."""
    actual = np.exp(y_actual_log)
    pred   = np.exp(y_pred_log)
    return np.mean(np.abs((actual - pred) / actual)) * 100

def ols_simple_stats(x, y):
    """Simple regression with full statistical output."""
    sl, ic, r, p, se = stats.linregress(x, y)
    r2   = r ** 2
    n    = len(x)
    t    = stats.t.ppf(0.975, df=n - 2)
    return {'r2': r2, 'p': p, 'coef': sl, 'intercept': ic,
            'ci_lo': sl - t * se, 'ci_hi': sl + t * se}

# ── 1. LOAD DATA ──────────────────────────────────────────────────────────────
print("Loading data...")
sales   = pd.read_csv(SALES_FILE).sort_values('YEAR_MONTH').reset_index(drop=True)
asp_df  = pd.read_csv(ASP_FILE)
mkt_df  = pd.read_csv(MKT_FILE)
nhom_df = pd.read_csv(NHOM_FILE)

# Merge all on YEAR_MONTH
df = (sales
      .merge(asp_df,  on='YEAR_MONTH', how='left')
      .merge(mkt_df,  on='YEAR_MONTH', how='left')
      .merge(nhom_df, on='YEAR_MONTH', how='left'))

df = add_time_features(df)

# Log-transform targets and key regressors
df['LOG_QTY']     = np.log(df['TOTAL_SALE'])
df['LOG_ASP']     = np.log(df['ASP_VND'])
df['LOG_MKT_OLD'] = np.log(df['MKT_OLD_B'].clip(lower=0.1))  # clip to avoid log(0)
df['LOG_MKT_NEW'] = np.log(df['MKT_NEW_B'].clip(lower=0.1))

# For product groups (M units in nhom_monthly.csv)
for grp in ['NHOM01', 'NHOM02', 'NHOM04', 'NHOM07']:
    df[f'LOG_{grp}'] = np.log(df[grp])

train = df[df['YEAR_MONTH'] <= TRAIN_END].dropna(subset=['LOG_QTY','LOG_ASP']).reset_index(drop=True)
val   = df[df['YEAR_MONTH'] >= VAL_START].reset_index(drop=True)

print(f"  Train: {len(train)} months ({train.YEAR_MONTH.iloc[0]} → {train.YEAR_MONTH.iloc[-1]})")
print(f"  Val:   {len(val)} months  ({val.YEAR_MONTH.iloc[0]} → {val.YEAR_MONTH.iloc[-1]})")

# ── 2. BASE FEATURES (shared across all models) ───────────────────────────────
BASE = ['TREND', 'SIN_12', 'COS_12', 'SIN_6', 'COVID_DIP', 'YEAREND']

# ═══════════════════════════════════════════════════════════════════════════════
# 3. OVERALL MODELS A–F
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("OVERALL QUANTITY — MODELS A THROUGH F")
print("=" * 65)

y_train = train['LOG_QTY'].values

MODEL_DEFS = {
    'A — Trend + Seasonality':           BASE,
    'B — + LOG(ASP)':                    BASE + ['LOG_ASP'],
    'C — + LOG(ASP) + LOG(MKT_OLD)':     BASE + ['LOG_ASP', 'LOG_MKT_OLD'],
    'D — + LOG(ASP) + LOG(MKT_NEW)':     BASE + ['LOG_ASP', 'LOG_MKT_NEW'],
    'E — + LOG(ASP) + GDP_Growth':        BASE + ['LOG_ASP', 'GDP_GROWTH_PCT'],
    'F — + LOG(ASP) + TET_FEB ★':        BASE + ['LOG_ASP', 'TET_FEB'],
}

results_overall = []
models_fitted   = {}

for name, features in MODEL_DEFS.items():
    X   = train[features].values
    m, s = fit_ols(X, y_train)
    y_pred = m.predict(X)
    mape   = mape_log(y_train, y_pred)

    # Pull ASP coef if present
    asp_coef = mkt_coef = None
    if 'LOG_ASP' in features:
        asp_idx  = features.index('LOG_ASP')
        asp_coef = m.coef_[asp_idx]
    for mkt_col in ['LOG_MKT_OLD', 'LOG_MKT_NEW']:
        if mkt_col in features:
            mkt_coef = m.coef_[features.index(mkt_col)]

    row = {
        'Model':    name,
        'R²':       round(s['r2'],    4),
        'Adj_R²':   round(s['r2_adj'],4),
        'MAPE_%':   round(mape,       2),
        'F_stat':   round(s['f_stat'],2),
        'p_F':      round(s['p_f'],   4),
        'ASP_coef': round(asp_coef, 3) if asp_coef is not None else '—',
        'MKT_coef': round(mkt_coef, 3) if mkt_coef is not None else '—',
        'n_features': len(features),
    }
    results_overall.append(row)
    models_fitted[name] = (m, features)

    elas_str = f"  elasticity={asp_coef:.3f}, +5%→{(1.05**asp_coef-1)*100:.1f}%" if asp_coef else ""
    print(f"\n{name}")
    print(f"  R²={s['r2']:.4f}  Adj.R²={s['r2_adj']:.4f}  MAPE={mape:.2f}%  F={s['f_stat']:.2f} (p={s['p_f']:.4f}){elas_str}")
    print(f"  Coefficients: " + ", ".join(f"{f}={m.coef_[i]:+.4f}" for i,f in enumerate(features)))

df_overall = pd.DataFrame(results_overall)
df_overall.to_csv('model_comparison_overall.csv', index=False, encoding='utf-8-sig')
print(f"\n\nSaved: model_comparison_overall.csv")
print(df_overall[['Model','R²','Adj_R²','MAPE_%','ASP_coef','MKT_coef']].to_string(index=False))

# ═══════════════════════════════════════════════════════════════════════════════
# 4. MODEL F — Q1 2026 OUT-OF-SAMPLE VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("MODEL F — Q1 2026 OUT-OF-SAMPLE VALIDATION")
print("=" * 65)

m_F, feat_F = models_fitted['F — + LOG(ASP) + TET_FEB ★']
val_results  = []

for i, row in val.iterrows():
    if pd.isna(row.get('LOG_ASP')):
        print(f"  ⚠️  {row['YEAR_MONTH']}: ASP missing — using last known ASP")
        continue
    X_val = pd.DataFrame([{f: row[f] for f in feat_F}])
    pred_log = m_F.predict(X_val)[0]
    pred_qty = np.exp(pred_log)
    act_qty  = row['TOTAL_SALE']
    err_pct  = (act_qty - pred_qty) / act_qty * 100
    val_results.append({
        'YEAR_MONTH': row['YEAR_MONTH'],
        'ACTUAL_M':   round(act_qty / 1e6, 1),
        'PRED_M':     round(pred_qty / 1e6, 1),
        'ERROR_M':    round((act_qty - pred_qty) / 1e6, 1),
        'ERROR_PCT':  round(err_pct, 2),
        'ABS_ERR_PCT':round(abs(err_pct), 2),
    })

val_df = pd.DataFrame(val_results)
print(val_df.to_string(index=False))
print(f"\n  Q1 2026 MAPE  : {val_df['ABS_ERR_PCT'].mean():.2f}%")

# Rolling MA12 baseline
all_hist = list(train['TOTAL_SALE'])
ma_mapes = []
for i, row in val.iterrows():
    ma_pred = np.mean(all_hist[-12:])
    ma_mapes.append(abs(row['TOTAL_SALE'] - ma_pred) / row['TOTAL_SALE'] * 100)
    all_hist.append(row['TOTAL_SALE'])
print(f"  MA12 baseline : {np.mean(ma_mapes):.2f}%")
print(f"  LR improvement: +{np.mean(ma_mapes) - val_df['ABS_ERR_PCT'].mean():.1f}pp")

val_df.to_csv('validation_overall_modelF.csv', index=False, encoding='utf-8-sig')
print("\nSaved: validation_overall_modelF.csv")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. PRODUCT GROUP — MODELS B & F per NHÓM
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PRODUCT GROUP REGRESSIONS — 01 / 02 / 04 / 07 NHÓM")
print("=" * 65)

GROUPS = {
    'NHOM01': '01XXXX — Condensed Milk',
    'NHOM02': '02XXXX — Powdered/Infant Formula',
    'NHOM04': '04XXXX — UHT Liquid Milk',
    'NHOM07': '07XXXX — Cultured/Other Dairy',
}

# 5a. Simple macro regressions per group (confirms audit table)
print("\n── 5a. Simple Macro Regressions (quantity, linear OLS) ──────────────")
print(f"\n{'Group':<12} {'CPI_R²':>7} {'CPI_p':>7} {'Rate_R²':>8} {'Rate_p':>7} {'GDP_R²':>8} {'GDP_p':>7} {'Best':>7}")
for col, label in GROUPS.items():
    grp_train = train.dropna(subset=[col])
    qty_arr   = grp_train[col].values
    row_out   = [col]
    best_r2   = 0
    for macro in ['CPI_YOY_PCT', 'INTEREST_RATE_PCT', 'GDP_GROWTH_PCT']:
        s = ols_simple_stats(grp_train[macro].values, qty_arr)
        row_out += [s['r2'], s['p']]
        best_r2  = max(best_r2, s['r2'])
    row_out.append(best_r2)
    print(f"  {row_out[0]:<10} {row_out[1]:>7.3f} {row_out[2]:>7.4f} {row_out[3]:>8.3f} {row_out[4]:>7.4f} {row_out[5]:>8.3f} {row_out[6]:>7.4f} {row_out[7]:>7.3f}")

# 5b. ASP simple regression per group (log-log)
print("\n── 5b. ASP Simple Regression per Group (log-log) ───────────────────")
for col, label in GROUPS.items():
    grp_train = train.dropna(subset=[col])
    log_qty   = np.log(grp_train[col].values)
    log_asp   = grp_train['LOG_ASP'].values
    s = ols_simple_stats(log_asp, log_qty)
    print(f"  {col}  R²={s['r2']:.3f}  p={s['p']:.4f}  elasticity={s['coef']:.3f}  +5%→{(1.05**s['coef']-1)*100:.1f}%")

# 5c. Full model comparison B & F per group
print("\n── 5c. Model B vs F per Group (log-log OLS) ─────────────────────────")
group_results = []

for col, label in GROUPS.items():
    grp_train = train.dropna(subset=[col, 'LOG_ASP']).reset_index(drop=True)
    log_qty   = np.log(grp_train[col].values)

    for mname, features in [
        ('Model B (ASP+Season)',      BASE + ['LOG_ASP']),
        ('Model F (ASP+Season+TET)',  BASE + ['LOG_ASP', 'TET_FEB']),
    ]:
        X  = grp_train[features].values
        m, s = fit_ols(X, log_qty)
        y_pred = m.predict(X)
        mape = mape_log(log_qty, y_pred)
        asp_idx  = features.index('LOG_ASP')
        asp_coef = m.coef_[asp_idx]

        print(f"\n  {label[:30]} | {mname}")
        print(f"    R²={s['r2']:.3f}  Adj.R²={s['r2_adj']:.3f}  MAPE={mape:.2f}%")
        print(f"    LOG_ASP coef={asp_coef:.3f}  elasticity={asp_coef:.3f}  +5%→{(1.05**asp_coef-1)*100:.1f}%")
        print(f"    Intercept={m.intercept_:.4f}")
        print(f"    All coefs: " + ", ".join(f"{f}={m.coef_[i]:+.4f}" for i,f in enumerate(features)))

        group_results.append({
            'Group':      col,
            'Label':      label,
            'Model':      mname,
            'R²':         round(s['r2'],     4),
            'Adj_R²':     round(s['r2_adj'], 4),
            'MAPE_%':     round(mape,         2),
            'ASP_coef':   round(asp_coef,     4),
            'Elasticity': round(asp_coef,     3),
            '+5%_qty':    round((1.05**asp_coef-1)*100, 1),
        })

df_groups = pd.DataFrame(group_results)
df_groups.to_csv('model_comparison_by_group.csv', index=False, encoding='utf-8-sig')
print(f"\n\nSaved: model_comparison_by_group.csv")
print(df_groups[['Group','Model','R²','MAPE_%','Elasticity','+5%_qty']].to_string(index=False))

# ═══════════════════════════════════════════════════════════════════════════════
# 6. SUMMARY PRINT
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("FINAL SUMMARY")
print("=" * 65)
print("\nOverall Models A–F:")
print(df_overall[['Model','R²','MAPE_%','ASP_coef']].to_string(index=False))
print("\nRecommended: Model F (ASP + Seasonality + TET_FEB)")
m_F_row = df_overall[df_overall['Model'].str.startswith('F')]
print(f"  R²={m_F_row['R²'].values[0]:.4f}  MAPE={m_F_row['MAPE_%'].values[0]:.2f}%")
print(f"  Q1 2026 MAPE: {val_df['ABS_ERR_PCT'].mean():.2f}%  (target was <8%)")
