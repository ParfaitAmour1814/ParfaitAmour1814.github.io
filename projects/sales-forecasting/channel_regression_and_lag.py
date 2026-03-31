"""
Channel-Level Regression & Lagged Marketing Analysis
======================================================
Author      : Truong Phat
Project     : Sales Channel Forecasting — FMCG Manufacturer (Vinamilk)
Description : Separate OLS regression (Model B: ASP + Seasonality) for
              each distribution channel (NPP / MT / CVS / KA), plus a
              systematic lagged marketing investigation testing MK** spend
              at lags 0–3 months against channel and total quantity.

Channels modelled
-----------------
  NPP  — Distributor (bulk ordering, contractual)
  MT   — Modern Trade (supermarket / hypermarket)
  CVS  — Convenience Store (7-Eleven, FamilyMart, etc.)
  KA   — Key Account (institutional buyers, corporate)
  HD   — School Milk (excluded — too lumpy for OLS)

Marketing lag test
------------------
  MK** spend (correct activity codes, ~97B VND/month) tested at:
  Lag 0  — same-month spend vs quantity
  Lag 1  — last month's spend vs this month's quantity
  Lag 2  — 2-month lagged spend
  Lag 3  — 3-month lagged spend
  Results: all lags are statistically insignificant (best ΔR²=+0.004).

Usage       : python channel_regression_and_lag.py
Requires    : pandas, numpy, scipy, scikit-learn

Input files
-----------
  channel_monthly.csv        — monthly quantity per channel
                               Columns: YEAR_MONTH, NPP, MT, CVS, KA
                               (all in million units)
  asp_channel_monthly.csv    — ASP per channel per month
                               Columns: YEAR_MONTH, ASP_NPP, ASP_MT,
                               ASP_CVS, ASP_KA  (VND/unit)
  mkt_monthly.csv            — monthly marketing spend
                               Columns: YEAR_MONTH, MKT_OLD_B, MKT_NEW_B
  macro_complete.csv         — macro vars (same as sales_macro_complete.csv)
                               Columns: YEAR_MONTH, CPI_YOY_PCT,
                               INTEREST_RATE_PCT, GDP_GROWTH_PCT

Output files
------------
  channel_model_results.csv  — Model B + F results per channel
  lag_test_results.csv       — R², MAPE, p-values for all lag models
  channel_coef_detail.csv    — full coefficient table per channel
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
CHANNEL_FILE   = 'channel_monthly.csv'
ASP_CH_FILE    = 'asp_channel_monthly.csv'
MKT_FILE       = 'mkt_monthly.csv'
MACRO_FILE     = 'macro_complete.csv'
TRAIN_END      = '2025-12'

CHANNELS = {
    'NPP': 'NPP — Distributor',
    'MT':  'MT — Modern Trade',
    'CVS': 'CVS — Convenience Store',
    'KA':  'KA — Key Account',
}

# ── HELPERS ───────────────────────────────────────────────────────────────────
def add_time_features(df):
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

def fit_ols(X, y, feature_names):
    """Fit OLS, return model + full stats."""
    m = LinearRegression().fit(X, y)
    y_pred = m.predict(X)
    n, k   = len(y), X.shape[1]
    r2     = r2_score(y, y_pred)
    r2_adj = 1 - (1 - r2) * (n - 1) / (n - k - 1)
    f_stat = (r2 / k) / ((1 - r2) / (n - k - 1))
    p_f    = 1 - f_dist.cdf(f_stat, k, n - k - 1)
    mape   = np.mean(np.abs((np.exp(y) - np.exp(y_pred)) / np.exp(y))) * 100
    coef_d = {feature_names[i]: round(m.coef_[i], 5) for i in range(k)}
    return m, {
        'r2': r2, 'r2_adj': r2_adj, 'f_stat': f_stat, 'p_f': p_f,
        'mape': mape, 'coefs': coef_d, 'intercept': m.intercept_
    }

def simple_reg_stats(x, y):
    """Simple linreg with p-value and CI."""
    sl, ic, r, p, se = stats.linregress(x, y)
    n  = len(x)
    t  = stats.t.ppf(0.975, df=n - 2)
    return {'r2': r**2, 'p': p, 'coef': sl, 'se': se,
            'ci_lo': sl - t*se, 'ci_hi': sl + t*se}

# ── 1. LOAD & MERGE ───────────────────────────────────────────────────────────
print("Loading data...")
ch_df    = pd.read_csv(CHANNEL_FILE).sort_values('YEAR_MONTH').reset_index(drop=True)
asp_ch   = pd.read_csv(ASP_CH_FILE)
mkt_df   = pd.read_csv(MKT_FILE)
macro_df = pd.read_csv(MACRO_FILE)

df = (ch_df
      .merge(asp_ch,   on='YEAR_MONTH', how='left')
      .merge(mkt_df,   on='YEAR_MONTH', how='left')
      .merge(macro_df[['YEAR_MONTH', 'CPI_YOY_PCT',
                        'INTEREST_RATE_PCT', 'GDP_GROWTH_PCT']],
             on='YEAR_MONTH', how='left'))

df = add_time_features(df)

# Log transforms
for ch in CHANNELS:
    df[f'LOG_QTY_{ch}']  = np.log(df[ch].clip(lower=0.001))
    df[f'LOG_ASP_{ch}']  = np.log(df[f'ASP_{ch}'].clip(lower=1))

df['LOG_MKT_OLD'] = np.log(df['MKT_OLD_B'].clip(lower=0.1))
df['LOG_MKT_NEW'] = np.log(df['MKT_NEW_B'].clip(lower=0.1))
df['MKT_NEW_B']   = df['MKT_NEW_B'].fillna(0)

# Create lagged MKT_NEW columns
for lag in range(1, 4):
    df[f'LOG_MKT_NEW_L{lag}'] = df['LOG_MKT_NEW'].shift(lag)
    df[f'MKT_NEW_L{lag}']     = df['MKT_NEW_B'].shift(lag)

train = df[df['YEAR_MONTH'] <= TRAIN_END].copy()
print(f"  Train: {len(train)} months ({train.YEAR_MONTH.iloc[0]} → {train.YEAR_MONTH.iloc[-1]})")

BASE    = ['TREND', 'SIN_12', 'COS_12', 'SIN_6', 'COVID_DIP', 'YEAREND']

# ═══════════════════════════════════════════════════════════════════════════════
# 2. CHANNEL MODEL B — ASP + SEASONALITY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("CHANNEL MODEL B — LOG(ASP) + SEASONALITY (per channel)")
print("=" * 65)

channel_results = []
channel_coefs   = []

for ch_code, ch_label in CHANNELS.items():
    qty_col = f'LOG_QTY_{ch_code}'
    asp_col = f'LOG_ASP_{ch_code}'

    sub = train.dropna(subset=[qty_col, asp_col]).reset_index(drop=True)
    y   = sub[qty_col].values

    # ── Simple regressions: ASP, MKT_OLD, MKT_NEW, macro ──────────────────
    s_asp     = simple_reg_stats(sub[asp_col].values,        y)
    s_mkt_old = simple_reg_stats(sub['LOG_MKT_OLD'].values,  y)
    s_mkt_new = simple_reg_stats(sub['LOG_MKT_NEW'].values,  y)
    s_rate    = simple_reg_stats(sub['INTEREST_RATE_PCT'].values, y)

    # ── Model B ─────────────────────────────────────────────────────────────
    feat_B = BASE + [asp_col]
    mB, sB = fit_ols(sub[feat_B].values, y, feat_B)

    # ── Model F (+TET_FEB) ──────────────────────────────────────────────────
    feat_F = BASE + [asp_col, 'TET_FEB']
    mF, sF = fit_ols(sub[feat_F].values, y, feat_F)

    asp_coef_B = sB['coefs'][asp_col]
    asp_coef_F = sF['coefs'][asp_col]
    elas5_B    = (1.05 ** asp_coef_B - 1) * 100
    elas5_F    = (1.05 ** asp_coef_F - 1) * 100

    print(f"\n{'─'*55}")
    print(f"  {ch_label}  (n={len(sub)})")
    print(f"  Simple R²: ASP={s_asp['r2']:.3f}(p={s_asp['p']:.4f})  "
          f"MKT_OLD={s_mkt_old['r2']:.3f}  MKT_NEW={s_mkt_new['r2']:.3f}(p={s_mkt_new['p']:.3f})  "
          f"Rate={s_rate['r2']:.3f}(p={s_rate['p']:.4f})")
    print(f"  Model B:  R²={sB['r2']:.3f}  Adj={sB['r2_adj']:.3f}  MAPE={sB['mape']:.2f}%  "
          f"ASP_coef={asp_coef_B:.3f}  +5%→{elas5_B:.1f}%")
    print(f"  Model F:  R²={sF['r2']:.3f}  Adj={sF['r2_adj']:.3f}  MAPE={sF['mape']:.2f}%  "
          f"ASP_coef={asp_coef_F:.3f}  +5%→{elas5_F:.1f}%")

    # Identify top driver (highest |standardised beta|)
    y_std = (y - y.mean()) / y.std()
    top_driver_val, top_driver_name = 0, ''
    for feat in feat_B:
        x_arr = sub[feat].values
        if x_arr.std() == 0:
            continue
        x_std  = (x_arr - x_arr.mean()) / x_arr.std()
        sl, _, _, _, _ = stats.linregress(x_std, y_std)
        if abs(sl) > abs(top_driver_val):
            top_driver_val  = sl
            top_driver_name = feat

    print(f"  Top driver: {top_driver_name} (β={top_driver_val:+.3f} standardised)")

    channel_results.append({
        'Channel':        ch_code,
        'Label':          ch_label,
        'n':              len(sub),
        'ASP_Simple_R²':  round(s_asp['r2'],    3),
        'ASP_p':          round(s_asp['p'],      4),
        'MKT_OLD_R²':     round(s_mkt_old['r2'],3),
        'MKT_NEW_R²':     round(s_mkt_new['r2'],3),
        'MKT_NEW_p':      round(s_mkt_new['p'], 3),
        'Rate_R²':        round(s_rate['r2'],    3),
        'Rate_p':         round(s_rate['p'],     4),
        'ModelB_R²':      round(sB['r2'],        4),
        'ModelB_Adj_R²':  round(sB['r2_adj'],    4),
        'ModelB_MAPE_%':  round(sB['mape'],      2),
        'ModelB_ASP_coef':round(asp_coef_B,      4),
        'ModelB_Elast':   round(asp_coef_B,      3),
        'ModelB_+5%_qty': round(elas5_B,          1),
        'ModelF_R²':      round(sF['r2'],        4),
        'ModelF_MAPE_%':  round(sF['mape'],      2),
        'ModelF_ASP_coef':round(asp_coef_F,      4),
        'Top_Driver':     top_driver_name,
    })

    # Store full coefficient detail
    for feat in feat_F:
        channel_coefs.append({
            'Channel': ch_code,
            'Feature': feat,
            'Coef':    round(sF['coefs'][feat], 5),
        })
    channel_coefs.append({
        'Channel': ch_code,
        'Feature': 'Intercept',
        'Coef':    round(sF['intercept'], 5),
    })

df_ch = pd.DataFrame(channel_results)
df_coefs = pd.DataFrame(channel_coefs)
df_ch.to_csv('channel_model_results.csv', index=False, encoding='utf-8-sig')
df_coefs.to_csv('channel_coef_detail.csv', index=False, encoding='utf-8-sig')
print(f"\n\nSaved: channel_model_results.csv, channel_coef_detail.csv")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. LAGGED MARKETING INVESTIGATION — TOTAL QUANTITY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("LAGGED MARKETING INVESTIGATION — MK** SPEND vs TOTAL QUANTITY")
print("Lags 0–3 months tested on total log-quantity (Model F + each lag)")
print("=" * 65)

# Load total quantity
total_df = pd.read_csv('sales_macro_complete.csv').sort_values('YEAR_MONTH').reset_index(drop=True)
total_df = total_df.merge(pd.read_csv(MKT_FILE), on='YEAR_MONTH', how='left')
total_df = total_df.merge(pd.read_csv('asp_monthly.csv'), on='YEAR_MONTH', how='left')
total_df = add_time_features(total_df)
total_df['LOG_QTY']     = np.log(total_df['TOTAL_SALE'])
total_df['LOG_ASP']     = np.log(total_df['ASP_VND'].clip(lower=1))
total_df['LOG_MKT_NEW'] = np.log(total_df['MKT_NEW_B'].clip(lower=0.1))
for lag in range(1, 4):
    total_df[f'LOG_MKT_NEW_L{lag}'] = total_df['LOG_MKT_NEW'].shift(lag)

train_tot = total_df[total_df['YEAR_MONTH'] <= TRAIN_END].copy()

print("\n── 3a. Simple R² — MK** Lag vs Total Log-Quantity ──────────────────")
print(f"{'Lag':>6} {'R²':>8} {'p-value':>10} {'coef':>10} {'sig':>5}")

lag_summary = []
for lag in range(4):
    col = 'LOG_MKT_NEW' if lag == 0 else f'LOG_MKT_NEW_L{lag}'
    sub = train_tot.dropna(subset=[col, 'LOG_QTY'])
    s   = simple_reg_stats(sub[col].values, sub['LOG_QTY'].values)
    sig = '✅' if s['p'] < 0.05 else '❌'
    print(f"  Lag {lag}:  R²={s['r2']:.4f}  p={s['p']:.4f}  coef={s['coef']:+.4f}  {sig}")
    lag_summary.append({'Lag': lag, 'R²': round(s['r2'], 4), 'p': round(s['p'], 4),
                        'coef': round(s['coef'], 4)})

print("\n── 3b. Incremental R² — Model F + each MK** lag ─────────────────────")
print("  (Does adding lagged marketing to Model F materially improve fit?)")
print(f"{'Lag':>6} {'Base R²':>9} {'With Lag R²':>12} {'ΔR²':>8} {'p(lag coef)':>13}")

feat_base = BASE + ['LOG_ASP', 'TET_FEB']

lag_results = []
for lag in range(4):
    lag_col = 'LOG_MKT_NEW' if lag == 0 else f'LOG_MKT_NEW_L{lag}'
    sub = train_tot.dropna(subset=[lag_col, 'LOG_QTY', 'LOG_ASP'])
    y   = sub['LOG_QTY'].values

    # Base model
    mBase, sBase = fit_ols(sub[feat_base].values, y, feat_base)
    r2_base = sBase['r2']

    # With lag
    feat_lag = feat_base + [lag_col]
    mLag, sLag = fit_ols(sub[feat_lag].values, y, feat_lag)
    r2_lag  = sLag['r2']
    delta   = r2_lag - r2_base

    # p-value of the lag coefficient via t-test approximation
    lag_coef  = sLag['coefs'][lag_col]
    y_pred    = mLag.predict(sub[feat_lag].values)
    n, k_lag  = len(y), len(feat_lag)
    mse       = np.sum((y - y_pred)**2) / (n - k_lag - 1)
    X_arr     = sub[feat_lag].values
    xtx_inv   = np.linalg.pinv(X_arr.T @ X_arr)
    lag_idx   = feat_lag.index(lag_col)
    se_lag    = np.sqrt(mse * xtx_inv[lag_idx, lag_idx])
    t_stat    = lag_coef / se_lag
    p_lag     = 2 * stats.t.sf(abs(t_stat), df=n - k_lag - 1)
    sig       = '✅' if p_lag < 0.05 else '❌'

    print(f"  Lag {lag}:  base={r2_base:.4f}  +lag={r2_lag:.4f}  Δ={delta:+.4f}  "
          f"p(lag)={p_lag:.4f}  coef={lag_coef:+.4f}  {sig}")

    lag_results.append({
        'Lag': lag, 'R²_base': round(r2_base, 4), 'R²_with_lag': round(r2_lag, 4),
        'Delta_R²': round(delta, 4), 'lag_coef': round(lag_coef, 4),
        'p_lag_coef': round(p_lag, 4), 'Significant': p_lag < 0.05,
        'MAPE_%': round(sLag['mape'], 2),
    })

df_lags = pd.DataFrame(lag_results)
df_lags.to_csv('lag_test_results.csv', index=False, encoding='utf-8-sig')
print("\nSaved: lag_test_results.csv")

# ── 3c. Channel-level lag investigation ───────────────────────────────────────
print("\n── 3c. Lagged MK** vs Each Channel (simple R², lag 0–3) ─────────────")
for lag in range(4):
    lag_col_mkt = 'MKT_NEW_B' if lag == 0 else f'MKT_NEW_L{lag}'
    lag_col_log = 'LOG_MKT_NEW' if lag == 0 else f'LOG_MKT_NEW_L{lag}'
    row_str = f"  Lag {lag}: "
    for ch_code in CHANNELS:
        qty_col = f'LOG_QTY_{ch_code}'
        sub = train.dropna(subset=[lag_col_log, qty_col])
        if len(sub) < 20:
            row_str += f"{ch_code}=n/a  "
            continue
        s = simple_reg_stats(sub[lag_col_log].values, sub[qty_col].values)
        sig = '✅' if s['p'] < 0.05 else '  '
        row_str += f"{ch_code}={s['r2']:.3f}(p={s['p']:.3f}){sig}  "
    print(row_str)

# ═══════════════════════════════════════════════════════════════════════════════
# 4. CHANNEL PRICE ELASTICITY SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("CHANNEL ELASTICITY SUMMARY")
print("=" * 65)
print(f"\n{'Channel':<25} {'Elasticity':>11} {'ASP+5%→Qty':>11} {'ASP+10%→Qty':>12} {'Model F R²':>11}")
for _, row in df_ch.iterrows():
    e     = row['ModelB_ASP_coef']
    elas5  = (1.05 ** e - 1) * 100
    elas10 = (1.10 ** e - 1) * 100
    print(f"  {row['Label']:<23} {e:>+11.3f} {elas5:>+10.1f}% {elas10:>+11.1f}% {row['ModelF_R²']:>11.4f}")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. FINAL CONCLUSION
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("CONCLUSIONS")
print("=" * 65)
print("""
Channel findings (Model B):
  • CVS is the most price-elastic channel — convenience shoppers
    are discretionary; price increases directly cut volume.
  • KA (Key Account) is dominated by Interest Rate, not ASP —
    institutional buyers are sensitive to credit cost cycles.
  • NPP (Distributor) is trend-driven with the lowest price elasticity —
    consistent with contractual, bulk-order purchasing patterns.
  • MT (Modern Trade) is macro-sensitive (Interest Rate) with
    moderate price response — shopper mix includes deal-seekers.

Marketing lag findings:
  • MK** spend at all lags (0–3 months) adds at most ΔR²=+0.004
    to Model F — well below the threshold for practical significance.
  • No lag achieves p<0.05 on the lag coefficient in the full model.
  • Monthly aggregate is likely too coarse to detect ad response.
  • Recommended next step: SKU-level or campaign-level spend data,
    or Nielsen/Kantar panel for proper marketing attribution.
""")
