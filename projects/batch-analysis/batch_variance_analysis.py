"""
Material Batch Variance Analysis
==================================
Author      : Truong Phat
Project     : Material Batch Variance — 4 Factories, Full Year 2025
Description : Analyses actual vs standard material usage per production
              batch across 4 factories. Joins batch data with INV100
              inventory cost (PMAC) to compute value-weighted variance.
              Splits RM/SM from packaging material for separate analysis.

Usage       : python batch_variance_analysis.py
Requires    : pandas, numpy, subprocess (LibreOffice for xlsb conversion)
Input files : DNC.xlsb, SBC.xlsb, SGC.xlsb, TSC.xlsb (batch data)
              INV100 monthly CSV files (inventory cost data)
"""

import pandas as pd
import numpy as np
import subprocess
import os
import warnings
warnings.filterwarnings('ignore')

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
FACTORY_FILES = {
    'DNC': 'DNC.xlsb',   # Factory A — Liquid Dairy
    'SBC': 'SBC.xlsb',   # Factory B — Powder Products
    'SGC': 'SGC.xlsb',   # Factory C — Liquid Dairy
    'TSC': 'TSC.xlsb',   # Factory D — Multi-Category
}
FACTORY_NAMES = {
    'DNC': 'Factory A',
    'SBC': 'Factory B',
    'SGC': 'Factory C',
    'TSC': 'Factory D',
}
LOW_VALUE_THRESHOLD = 10000  # VND/unit — exclude below this (straws, small caps)

# ── 1. CONVERT XLSB TO CSV USING LIBREOFFICE ──────────────────────────────────
def convert_xlsb(xlsb_path, out_dir='.'):
    """Convert xlsb to CSV using LibreOffice headless."""
    result = subprocess.run(
        ['libreoffice', '--headless', '--convert-to', 'csv',
         '--outdir', out_dir, xlsb_path],
        capture_output=True, timeout=180)
    csv_path = os.path.join(out_dir,
                os.path.basename(xlsb_path).replace('.xlsb', '.csv'))
    return csv_path if os.path.exists(csv_path) else None


# ── 2. LOAD BATCH DATA ────────────────────────────────────────────────────────
def load_batch_data():
    all_dfs = []
    for code, fname in FACTORY_FILES.items():
        csv_path = fname.replace('.xlsb', '.csv')
        if not os.path.exists(csv_path):
            print(f"Converting {fname}...")
            csv_path = convert_xlsb(fname)
        if csv_path and os.path.exists(csv_path):
            df = pd.read_csv(csv_path, encoding='utf-8-sig', low_memory=False)
            df['FACTORY']      = code
            df['FACTORY_NAME'] = FACTORY_NAMES[code]
            all_dfs.append(df)
            print(f"  {code}: {len(df):,} rows loaded")
        else:
            print(f"  {code}: FAILED — {fname} not found")

    return pd.concat(all_dfs, ignore_index=True) if all_dfs else None


# ── 3. LOAD INVENTORY COSTS (INV100) ──────────────────────────────────────────
def load_inventory_costs(inv_dir='.'):
    """Load all INV100 CSV files and compute average PMAC per item."""
    keep_cols = ['ITEM_NO', 'DESCRIPTION', 'ITEM_TYPE', 'UOM',
                 'PERIOD_NAME', 'PMAC']
    dfs = []
    for f in os.listdir(inv_dir):
        if f.endswith('.csv') and f.startswith('2'):
            try:
                df = pd.read_csv(os.path.join(inv_dir, f),
                                 encoding='utf-8-sig',
                                 usecols=keep_cols,
                                 low_memory=False)
                dfs.append(df)
            except Exception:
                pass
    if not dfs:
        return None
    inv = pd.concat(dfs, ignore_index=True)
    inv['PMAC'] = pd.to_numeric(inv['PMAC'], errors='coerce').fillna(0)
    unit_cost = (inv.groupby(['ITEM_NO', 'DESCRIPTION', 'ITEM_TYPE'])
                    ['PMAC'].mean().reset_index()
                    .rename(columns={'PMAC': 'AVG_PMAC'}))
    return unit_cost


# ── 4. MAIN ANALYSIS ──────────────────────────────────────────────────────────
def run_analysis():
    print("Loading batch data...")
    batch = load_batch_data()
    if batch is None:
        print("ERROR: No batch data loaded.")
        return

    for col in ['PLAN_QTY', 'ACTUAL_QTY', 'DIFF_QTY', 'DIFF_PERCENT']:
        batch[col] = pd.to_numeric(batch[col], errors='coerce')
    batch['START_DATE'] = pd.to_datetime(batch['START_DATE'], errors='coerce')
    batch['MONTH']      = batch['START_DATE'].dt.strftime('%m-%y')

    print("\nLoading inventory costs...")
    unit_cost = load_inventory_costs()
    if unit_cost is not None:
        cost_map = unit_cost.groupby('ITEM_NO')['AVG_PMAC'].mean().to_dict()
        type_map = unit_cost.groupby('ITEM_NO')['ITEM_TYPE'].first().to_dict()
        batch['UNIT_COST']       = batch['INGREDIENT'].map(cost_map)
        batch['INGREDIENT_TYPE'] = batch['INGREDIENT'].map(type_map)

        # Exclude low-value items
        excl = {k for k, v in cost_map.items() if v < LOW_VALUE_THRESHOLD}
        batch_val = batch[
            ~batch['INGREDIENT'].isin(excl) &
            batch['UNIT_COST'].notna()
        ].copy()

        batch_val['PLAN_VALUE']   = batch_val['PLAN_QTY']   * batch_val['UNIT_COST']
        batch_val['ACTUAL_VALUE'] = batch_val['ACTUAL_QTY'] * batch_val['UNIT_COST']
        batch_val['DIFF_VALUE']   = batch_val['DIFF_QTY']   * batch_val['UNIT_COST']
    else:
        print("WARNING: No INV100 files found. Running quantity-only analysis.")
        batch_val = batch.copy()

    # ── FACTORY SUMMARY ───────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("FACTORY SUMMARY")
    print("="*60)
    for factory in ['DNC', 'SBC', 'SGC', 'TSC']:
        f = batch[batch['FACTORY'] == factory]
        print(f"\n{FACTORY_NAMES[factory]} ({factory})")
        print(f"  Batches  : {f['BATCH'].nunique():,}")
        print(f"  Products : {f['PRODUCT_1'].nunique():,}")
        print(f"  Net DIFF : {f['DIFF_QTY'].sum():+,.0f} units")
        print(f"  Avg DIFF%: {f['DIFF_PERCENT'].mean()*100:.4f}%")

    # ── RM/SM PRODUCT RANKING ─────────────────────────────────────────────────
    if 'INGREDIENT_TYPE' in batch_val.columns:
        df_rmsm = batch_val[
            batch_val['INGREDIENT_TYPE'].isin(['RM', 'SM']) &
            ~batch_val['PRODUCT_1'].str.startswith('99', na=False)
        ].copy()

        prod = (df_rmsm.groupby(['FACTORY', 'PRODUCT_1', 'PRODUCT_1_DESCRIPTION'])
                .agg(PLAN_VAL   =('PLAN_VALUE', 'sum'),
                     ACTUAL_VAL =('ACTUAL_VALUE', 'sum'),
                     DIFF_VAL   =('DIFF_VALUE', 'sum'),
                     BATCHES    =('BATCH', 'nunique'))
                .reset_index())
        prod['VARIANCE_PCT'] = prod['DIFF_VAL'] / prod['PLAN_VAL'] * 100
        prod['ABS_VAR_PCT']  = prod['VARIANCE_PCT'].abs()
        prod_sig = prod[(prod['PLAN_VAL'] > 1e9) & (prod['BATCHES'] >= 3)]

        print(f"\n{'='*60}")
        print("TOP 3 BEST / WORST PRODUCTS — RM/SM VALUE VARIANCE")
        print("="*60)
        for factory in ['DNC', 'SBC', 'SGC', 'TSC']:
            f = prod_sig[prod_sig['FACTORY'] == factory]
            best  = f.nsmallest(3, 'ABS_VAR_PCT')
            worst = f.nlargest(3,  'ABS_VAR_PCT')
            print(f"\n{FACTORY_NAMES[factory]}:")
            print("  BEST 3:")
            for _, r in best.iterrows():
                print(f"    {r['PRODUCT_1']}: {r['VARIANCE_PCT']:+.4f}% "
                      f"({r['BATCHES']} batches)")
            print("  WORST 3:")
            for _, r in worst.iterrows():
                print(f"    {r['PRODUCT_1']}: {r['VARIANCE_PCT']:+.4f}% "
                      f"({r['BATCHES']} batches)")

        prod_sig.to_csv('batch_rmsm_product_variance.csv',
                        index=False, encoding='utf-8-sig')
        print("\nSaved: batch_rmsm_product_variance.csv")

    # ── PM CROSS-FACTORY ──────────────────────────────────────────────────────
    if 'INGREDIENT_TYPE' in batch_val.columns:
        df_pm = batch_val[batch_val['INGREDIENT_TYPE'] == 'PM'].copy()
        pm_summary = (df_pm.groupby('FACTORY')
                      .agg(PLAN_VAL=('PLAN_VALUE', 'sum'),
                           DIFF_VAL=('DIFF_VALUE', 'sum'))
                      .reset_index())
        pm_summary['VAR_PCT'] = pm_summary['DIFF_VAL'] / pm_summary['PLAN_VAL'] * 100
        pm_summary['NAME']    = pm_summary['FACTORY'].map(FACTORY_NAMES)
        print(f"\n{'='*60}")
        print("PACKAGING MATERIAL — CROSS-FACTORY VARIANCE RATE")
        print("="*60)
        for _, r in pm_summary.sort_values('VAR_PCT').iterrows():
            print(f"  {r['NAME']}: {r['VAR_PCT']:+.3f}% "
                  f"({r['DIFF_VAL']/1e9:.2f}B VND)")

        pm_summary.to_csv('batch_pm_factory_summary.csv',
                          index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    run_analysis()
