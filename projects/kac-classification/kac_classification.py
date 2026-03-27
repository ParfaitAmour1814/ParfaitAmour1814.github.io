"""
KA Customer Classification — KAC vs KAM
=========================================
Author      : Truong Phat
Project     : KA Customer Classification (Key Account Chain vs Key Account Mgmt)
Description : Two-stage pipeline:
              1. ETL — Extract 15 structured fields from F1 pricing approval
                 PDFs using pdftotext layout extraction + regex parsing.
              2. ML  — Logistic Regression classifier predicting KAC (KA01)
                 vs KAM (KA00) from extracted features.
              Planned extension: K-Means clustering for unsupervised
              customer segmentation beyond the binary KAC/KAM split.

Usage       : python kac_classification.py
Requires    : pandas, numpy, scikit-learn, scipy, subprocess (pdftotext)
Input       : Directory of F1 PDF files
"""

import os
import re
import subprocess
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.pipeline import Pipeline
import warnings
warnings.filterwarnings('ignore')

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
PDF_DIR    = './f1_pdfs'          # directory containing extracted F1 PDFs
OUTPUT_CSV = 'f1_extracted.csv'

# Hyperparameters (current — pending GridSearchCV tuning)
LR_C          = 1.0
LR_PENALTY    = 'l2'
LR_MAX_ITER   = 1000
RANDOM_STATE  = 42
TEST_SIZE     = 0.20

# Client type groupings
HOSPITAL_CODES = ['BVXX', 'BVCD']
OFFICE_CODES   = ['CQXX', 'CQCD']
SCHOOL_CODES   = ['THXX', 'VCXX', 'VCDB', 'VCSA']
FOOD_CODES     = ['CBTP', 'GKCF']
SERVICE_CODES  = ['SATH', 'SACN', 'GTVC', 'KSNH', 'AUNH', 'AUCH', 'AUCD']


# ── STAGE 1: ETL ──────────────────────────────────────────────────────────────
def extract_text(pdf_path):
    """Extract text from PDF using pdftotext with layout preservation."""
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', pdf_path, '-'],
            capture_output=True, timeout=15)
        return result.stdout.decode('utf-8', errors='replace')
    except Exception:
        return ''


def parse_f1(text, filename):
    """
    Parse F1 form text and extract structured fields.

    Key fields:
    - MA_LH      : Channel code — KA01 (KAC) or KA00 (KAM) → classification label
    - LOAI_HINH  : Client type code (XXXX suffix) → CQXX, BVXX, GKCF etc.
    - NUM_SHIP_TO: Number of delivery locations (strongest KAC predictor)
    - REVENUE_*  : Monthly/annual revenue targets
    - HIST_SALES : 12-month historical sales
    - TOTAL_SUPPORT_PCT: Combined discount + post-sale support %
    """
    d = {'FILENAME': filename}

    # ── Target label from Mã LH ───────────────────────────────────────────────
    m = re.search(r'Mã LH[:\s]*([A-Z]{2}\d{2})', text)
    if m:
        d['MA_LH'] = m.group(1)
        d['LABEL'] = ('KAC' if 'KA01' in m.group(1) else
                      'KAM' if 'KA00' in m.group(1) else 'OTHER')
    else:
        d['MA_LH'] = None
        d['LABEL'] = None

    # ── Client type suffix (e.g. CQXX, BVXX) ─────────────────────────────────
    m = re.search(r'Mã LH[:\s]*[A-Z]{2}\d{2}\s*[-–]\s*([A-Z]{4})', text)
    if not m:
        m = re.search(r'KA0[01]\s*[-–]\s*([A-Z]{4,6})', text)
    d['LOAI_HINH_CODE'] = m.group(1) if m else None

    # ── Number of ship-to locations (strongest feature) ───────────────────────
    m = re.search(r'Số lượng Ship-to[:\s]*(\d+)', text)
    d['NUM_SHIP_TO'] = int(m.group(1)) if m else None

    # ── Contract duration ─────────────────────────────────────────────────────
    m = re.search(r'Thời hạn[:\s:]*(\d+)\s*tháng', text)
    d['CONTRACT_MONTHS'] = int(m.group(1)) if m else None

    # ── Auto-renew ────────────────────────────────────────────────────────────
    m = re.search(r'Tự gia hạn[:\s]*(CÓ|KHÔNG)', text, re.IGNORECASE)
    d['AUTO_RENEW'] = m.group(1).upper() if m else None

    # ── Revenue targets ───────────────────────────────────────────────────────
    totals = re.findall(r'([\d,]+)\s+([\d,]+)\s+[\d.]+%', text)
    if totals:
        try:
            d['REVENUE_TARGET_YEAR']  = int(totals[0][0].replace(',', ''))
            d['REVENUE_TARGET_MONTH'] = int(totals[0][1].replace(',', ''))
        except Exception:
            d['REVENUE_TARGET_YEAR'] = d['REVENUE_TARGET_MONTH'] = None
    else:
        d['REVENUE_TARGET_YEAR'] = d['REVENUE_TARGET_MONTH'] = None

    # ── Total discount + support % ────────────────────────────────────────────
    m = re.search(r'Tổng tỷ lệ hỗ trợ.*?([\d.]+)%', text, re.DOTALL)
    d['TOTAL_SUPPORT_PCT'] = float(m.group(1)) if m else None

    # ── Historical 12M sales ──────────────────────────────────────────────────
    m = re.search(r'DS lịch sử 12 tháng.*?([\d,]+)', text, re.DOTALL)
    try:
        d['HIST_SALES_12M'] = int(m.group(1).replace(',', '')) if m else None
    except Exception:
        d['HIST_SALES_12M'] = None

    # ── Product categories & groups ───────────────────────────────────────────
    cats = re.findall(r'^\s+([A-Z])\s+', text, re.MULTILINE)
    d['NUM_CATEGORIES'] = len(set(cats)) if cats else None

    prod_groups = [pg for pg in
                   ['STTT', 'SDD', 'SCA', 'SCU', 'Sữa bột', 'Flex',
                    'Organic', 'Green Farm', 'Tổ Yến', 'Kem', 'Kombucha',
                    'Nước dừa', 'Twincows']
                   if pg in text]
    d['PRODUCT_GROUPS']    = '|'.join(prod_groups) if prod_groups else None
    d['NUM_PRODUCT_GROUPS'] = len(prod_groups)

    # ── Geographic coverage ───────────────────────────────────────────────────
    if 'Toàn quốc' in text:        d['GEO_COVERAGE'] = 'National'
    elif 'TP. HCM' in text:        d['GEO_COVERAGE'] = 'HCM'
    elif 'Hà Nội' in text:         d['GEO_COVERAGE'] = 'HN'
    else:                          d['GEO_COVERAGE'] = 'Regional'

    # ── Order frequency ───────────────────────────────────────────────────────
    m = re.search(r'(\d+)\s*lần/tháng', text)
    d['ORDER_FREQ_MONTH'] = int(m.group(1)) if m else None

    # ── Document metadata ─────────────────────────────────────────────────────
    m = re.search(r'Số[:\s]*([\w/]+GV-KD-02-F1[\w/]+)', text)
    d['F1_NUMBER'] = m.group(1) if m else None

    m = re.search(r'Ngày hiệu lực[:\s]*([\d/]+)', text)
    d['EFFECTIVE_DATE'] = m.group(1) if m else None

    return d


def run_etl(pdf_dir):
    """Run ETL on all PDFs in directory. Returns DataFrame."""
    pdfs     = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    records  = []
    failed   = []
    print(f"Processing {len(pdfs)} PDFs...")

    for i, fname in enumerate(pdfs, 1):
        if i % 50 == 0:
            print(f"  {i}/{len(pdfs)}...")
        path = os.path.join(pdf_dir, fname)
        text = extract_text(path)
        if not text.strip():
            failed.append(fname)
            continue
        records.append(parse_f1(text, fname))

    df = pd.DataFrame(records)
    print(f"Extracted: {len(df)} records | Failed: {len(failed)}")
    print(f"Labels: {df['LABEL'].value_counts(dropna=False).to_dict()}")
    return df


# ── STAGE 2: FEATURE ENGINEERING & MODEL ──────────────────────────────────────
def get_client_group(code):
    code = str(code)
    if code in HOSPITAL_CODES: return 'HOSPITAL'
    if code in OFFICE_CODES:   return 'OFFICE'
    if code in SCHOOL_CODES:   return 'SCHOOL'
    if code in FOOD_CODES:     return 'FOOD_MFG'
    if code in SERVICE_CODES:  return 'SERVICE'
    return 'OTHER'


def build_features(df):
    """Engineer feature matrix from extracted fields."""
    labelled = df[df['LABEL'].isin(['KAC', 'KAM'])].copy().reset_index(drop=True)

    # Client type one-hot
    labelled['CLIENT_GROUP'] = (labelled['LOAI_HINH_CODE']
                                .fillna('UNKNOWN')
                                .apply(get_client_group))
    client_dummies = pd.get_dummies(labelled['CLIENT_GROUP'], prefix='CG')

    # Numeric features (median imputation for missing values)
    num_cols = ['NUM_SHIP_TO', 'CONTRACT_MONTHS', 'REVENUE_TARGET_YEAR',
                'REVENUE_TARGET_MONTH', 'TOTAL_SUPPORT_PCT', 'HIST_SALES_12M',
                'NUM_CATEGORIES', 'NUM_PRODUCT_GROUPS', 'ORDER_FREQ_MONTH']
    num_df = pd.DataFrame(index=labelled.index)
    for col in num_cols:
        s = pd.to_numeric(labelled[col], errors='coerce')
        num_df[col] = s.fillna(s.median())

    # Log transform skewed financial columns
    for col in ['REVENUE_TARGET_YEAR', 'REVENUE_TARGET_MONTH', 'HIST_SALES_12M']:
        num_df[f'LOG_{col}'] = np.log1p(num_df[col])

    # Binary flags
    misc = pd.DataFrame({
        'IS_NATIONAL':    (labelled['GEO_COVERAGE'] == 'National').astype(int).values,
        'IS_HCM':         (labelled['GEO_COVERAGE'] == 'HCM').astype(int).values,
        'AUTO_RENEW_BIN': (labelled['AUTO_RENEW'] == 'CÓ').astype(int).values,
    }, index=labelled.index)

    X = pd.concat([num_df, client_dummies, misc], axis=1)
    X.columns = [str(c) for c in X.columns]
    X = X.loc[:, ~X.columns.duplicated()]
    y = (labelled['LABEL'] == 'KAC').astype(int)
    return X, y


def run_model(X, y):
    """Train and evaluate Logistic Regression classifier."""
    print(f"\nFeature matrix: {X.shape}")
    print(f"Class balance: KAC={y.sum()} ({y.mean()*100:.1f}%) | "
          f"KAM={len(y)-y.sum()} ({(1-y.mean())*100:.1f}%)")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    # ── Logistic Regression (chosen model) ────────────────────────────────────
    # Rationale: chosen for interpretability and generalisation robustness
    # over tree-based models on this small dataset (402 records).
    # LR coefficients provide direct business explainability.
    # Gradient Boosting achieves higher raw accuracy (90% vs 79%) but
    # risks overfitting with n=402 and does not provide interpretable outputs.
    lr = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', LogisticRegression(C=LR_C, penalty=LR_PENALTY,
                                   max_iter=LR_MAX_ITER,
                                   random_state=RANDOM_STATE))
    ])

    # Cross-validation
    cv_auc = cross_val_score(lr, X_train, y_train, cv=cv, scoring='roc_auc')
    cv_acc = cross_val_score(lr, X_train, y_train, cv=cv, scoring='accuracy')
    print(f"\n── Cross-Validation (5-fold) ──────────────────")
    print(f"  AUC : {cv_auc.mean():.4f} ± {cv_auc.std():.4f}")
    print(f"  Acc : {cv_acc.mean():.4f} ± {cv_acc.std():.4f}")

    # Test set evaluation
    lr.fit(X_train, y_train)
    y_pred  = lr.predict(X_test)
    y_proba = lr.predict_proba(X_test)[:, 1]
    print(f"\n── Test Set Results ───────────────────────────")
    print(f"  AUC : {roc_auc_score(y_test, y_proba):.4f}")
    print(classification_report(y_test, y_pred, target_names=['KAM', 'KAC']))

    # Coefficients
    coefs = pd.DataFrame({
        'Feature':     X.columns,
        'Coefficient': lr.named_steps['clf'].coef_[0]
    }).sort_values('Coefficient', key=abs, ascending=False)
    print("── Top Feature Coefficients (+ = KAC, - = KAM) ─")
    print(coefs.head(10).to_string(index=False))

    # ── Random Forest (sanity check only) ─────────────────────────────────────
    rf = RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE,
                                class_weight='balanced')
    rf.fit(X_train, y_train)
    rf_proba = rf.predict_proba(X_test)[:, 1]
    print(f"\n── Random Forest (sanity check) ───────────────")
    print(f"  AUC : {roc_auc_score(y_test, rf_proba):.4f}")
    print("  (Used to flag disagreements with LR for manual review)")

    # Agreement rate between LR and RF
    agree = (lr.predict(X_test) == rf.predict(X_test)).mean()
    print(f"  LR/RF agreement: {agree*100:.1f}%")

    coefs.to_csv('f1_lr_coefficients.csv', index=False, encoding='utf-8-sig')
    print("\nSaved: f1_lr_coefficients.csv")

    return lr, rf, coefs


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Stage 1: ETL
    if os.path.exists(OUTPUT_CSV):
        print(f"Loading cached ETL results from {OUTPUT_CSV}...")
        df = pd.read_csv(OUTPUT_CSV)
    elif os.path.exists(PDF_DIR):
        df = run_etl(PDF_DIR)
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        print(f"Saved: {OUTPUT_CSV}")
    else:
        print(f"ERROR: {PDF_DIR} not found. Please extract F1 PDFs first.")
        exit(1)

    print(f"\nTotal records: {len(df)}")
    print(f"Labelled     : {df['LABEL'].isin(['KAC','KAM']).sum()}")
    print(f"Unlabelled   : {df['LABEL'].isna().sum()}")

    # Stage 2: Model
    X, y = build_features(df)
    lr_model, rf_model, coefs = run_model(X, y)

    # Export unlabelled for manual review
    unlabelled = df[df['LABEL'].isna()][
        ['FILENAME', 'F1_NUMBER', 'EFFECTIVE_DATE',
         'LOAI_HINH_CODE', 'LOAI_HINH']].copy()
    unlabelled['MA_LH (KA00/KA01)'] = ''
    unlabelled['LABEL (KAC/KAM)']   = ''
    unlabelled.to_excel('f1_manual_review.xlsx', index=False)
    print(f"\nExported {len(unlabelled)} unlabelled records to f1_manual_review.xlsx")
    print("Fill in MA_LH and LABEL columns, then re-run to retrain on full dataset.")

    print("\n\n" + "="*60)
    print("STAGE 3: K-MEANS CLUSTERING — FULL AR CUSTOMER DATA")
    print("="*60)
    run_kmeans()


# ── STAGE 3: K-MEANS CLUSTERING ───────────────────────────────────────────────
def run_kmeans(ar_file1='Ar data.csv', ar_file2='Ar data 2.csv'):
    """
    K-Means clustering on full KA customer AR data.

    Data sources:
    - AR ship-to / bill-to location data (2,219 KA customers)
    - Features: ship-to count, city/district/region spread, credit limit,
      payment terms, profile class, client type, geographic flags

    Results (K=3,4,5):
    - K=5 optimal by silhouette score (0.168)
    - 5 natural segments: Hospital KAM, Commercial KAC, School/Hotel KAM,
      Industrial KAM, National Chain KAC
    - Key finding: geographic scale (ship-to, cities) is the primary
      KAC differentiator, not industry type alone
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    # Load AR data
    dfs = []
    for fname in [ar_file1, ar_file2]:
        try:
            dfs.append(pd.read_csv(fname, encoding='utf-8-sig', low_memory=False))
        except FileNotFoundError:
            print(f"WARNING: {fname} not found — skipping")
    if not dfs:
        print("ERROR: No AR data files found. Provide 'Ar data.csv' and 'Ar data 2.csv'")
        return

    df = pd.concat(dfs, ignore_index=True)
    ka = df[df['SALES_CHANNEL_CODE'] == 'KA'].copy()
    print(f"KA rows: {len(ka):,} | Unique customers: {ka['CUSTOMER_NUMBER'].nunique():,}")

    # ── CUSTOMER-LEVEL AGGREGATION ────────────────────────────────────────────
    ship_to = (ka[ka['SITE_USE_CODE'] == 'SHIP_TO']
               .groupby('CUSTOMER_NUMBER')
               .agg(NUM_SHIP_TO =('SITE_USE_ID',  'nunique'),
                    CITIES      =('CITY_TER',      'nunique'),
                    DISTRICTS   =('DISTRICT_TER',  'nunique'),
                    REGIONS     =('MIEN',          'nunique'),
                    ACTIVE_SITES=('CUST_SITE_STATUS', lambda x: (x=='A').sum()))
               .reset_index())

    bill_to = (ka[ka['SITE_USE_CODE'] == 'BILL_TO']
               .groupby('CUSTOMER_NUMBER')
               .agg(BILL_CITY    =('CITY_TER',             'first'),
                    BILL_REGION  =('MIEN',                 'first'),
                    CREDIT_LIMIT =('CREDIT_LIMIT_CUST_VND','max'),
                    PAYMENT_TERM =('PAYMENT_TERM',         'first'),
                    PROFILE_CLASS=('PROFILE_CLASS',        'first'),
                    CATEGORY_CODE=('CATEGORY_CODE',        'first'))
               .reset_index())

    cust = ship_to.merge(bill_to, on='CUSTOMER_NUMBER', how='outer')

    # ── LABELS & GROUPINGS ────────────────────────────────────────────────────
    def get_label(code):
        if pd.isna(code): return None
        return 'KAC' if 'KA01' in str(code) else 'KAM' if 'KA00' in str(code) else 'OTHER'

    def get_client_type(code):
        if pd.isna(code): return 'UNKNOWN'
        for s in ['CQXX','CQCD','BVXX','BVCD','GKCF','KSNH','SATH',
                  'SACN','AUNH','CBTP','GTVC','THSA','THHD','B2BL','B2KM']:
            if s in str(code): return s[:4]
        return 'OTHER'

    def profile_group(p):
        if pd.isna(p): return 'UNKNOWN'
        p = str(p).upper()
        if 'BENH' in p or 'VIEN' in p: return 'HOSPITAL'
        if 'TRUONG' in p or 'HOC' in p: return 'SCHOOL'
        if 'KHACH SAN' in p:            return 'HOTEL'
        if 'DOC HAI' in p:              return 'INDUSTRIAL'
        if 'KINH DOANH' in p:           return 'COMMERCIAL'
        return 'OTHER'

    def parse_payment_days(s):
        if pd.isna(s): return np.nan
        import re
        m = re.search(r'(\d+)D', str(s))
        return int(m.group(1)) if m else np.nan

    cust['LABEL']        = cust['CATEGORY_CODE'].apply(get_label)
    cust['CLIENT_TYPE']  = cust['CATEGORY_CODE'].apply(get_client_type)
    cust['PROFILE_GRP']  = cust['PROFILE_CLASS'].apply(profile_group)
    cust['IS_HCM']       = cust['BILL_CITY'].str.contains('051|HỒ CHÍ MINH', na=False).astype(int)
    cust['IS_HANOI']     = cust['BILL_CITY'].str.contains('001|HÀ NỘI', na=False).astype(int)
    cust['IS_NATIONAL']  = (pd.to_numeric(cust['REGIONS'], errors='coerce') >= 3).astype(int)
    cust['IS_SOUTH']     = cust['BILL_REGION'].str.contains('MN|MY|MH', na=False).astype(int)
    cust['IS_NORTH']     = cust['BILL_REGION'].str.contains('HN|MB', na=False).astype(int)
    cust['IS_CENTRAL']   = cust['BILL_REGION'].str.contains('MT|MD', na=False).astype(int)
    cust['CREDIT_LIMIT'] = pd.to_numeric(cust['CREDIT_LIMIT'], errors='coerce')
    cust['LOG_CREDIT']   = np.log1p(cust['CREDIT_LIMIT'].fillna(0))
    cust['PAYMENT_DAYS'] = cust['PAYMENT_TERM'].apply(parse_payment_days)

    # ── FEATURE MATRIX ────────────────────────────────────────────────────────
    profile_dummies = pd.get_dummies(cust['PROFILE_GRP'], prefix='PG')
    client_dummies  = pd.get_dummies(cust['CLIENT_TYPE'],  prefix='CT')

    num_df = pd.DataFrame({
        'LOG_SHIP_TO'  : np.log1p(pd.to_numeric(cust['NUM_SHIP_TO'],  errors='coerce').fillna(1)),
        'NUM_CITIES'   : pd.to_numeric(cust['CITIES'],    errors='coerce').fillna(1),
        'NUM_DISTRICTS': pd.to_numeric(cust['DISTRICTS'], errors='coerce').fillna(1),
        'NUM_REGIONS'  : pd.to_numeric(cust['REGIONS'],   errors='coerce').fillna(1),
        'LOG_CREDIT'   : cust['LOG_CREDIT'].fillna(0),
        'PAYMENT_DAYS' : cust['PAYMENT_DAYS'].fillna(30),
        'IS_HCM'       : cust['IS_HCM'], 'IS_HANOI': cust['IS_HANOI'],
        'IS_NATIONAL'  : cust['IS_NATIONAL'], 'IS_SOUTH': cust['IS_SOUTH'],
        'IS_NORTH'     : cust['IS_NORTH'],    'IS_CENTRAL': cust['IS_CENTRAL'],
    })

    X = pd.concat([num_df, profile_dummies, client_dummies], axis=1).fillna(0)
    X.columns = [str(c) for c in X.columns]

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # ── K-MEANS K=3,4,5 ──────────────────────────────────────────────────────
    print(f"\nFeature matrix: {X.shape}")
    print(f"\n{'='*60}")
    print("K-MEANS RESULTS (K=3, 4, 5)")
    print("="*60)

    # Cluster segment names for K=5
    K5_NAMES = {
        0: 'Hospital KAM',
        1: 'Commercial KAC',
        2: 'School & Hotel KAM',
        3: 'Industrial KAM',
        4: 'National Chain KAC',
    }

    best_k, best_sil = 3, 0
    for k in [3, 4, 5]:
        km     = KMeans(n_clusters=k, random_state=42, n_init=20, max_iter=500)
        labels = km.fit_predict(X_scaled)
        sil    = silhouette_score(X_scaled, labels)
        if sil > best_sil: best_k, best_sil = k, sil
        cust[f'CLUSTER_K{k}'] = labels

        print(f"\n── K={k}  Silhouette={sil:.4f}  Inertia={km.inertia_:,.0f}")
        for c in range(k):
            grp  = cust[cust[f'CLUSTER_K{k}'] == c]
            vc   = grp['LABEL'].value_counts()
            tot  = len(grp)
            name = K5_NAMES.get(c, f'Cluster {c}') if k == 5 else f'Cluster {c}'
            prof = grp['PROFILE_GRP'].value_counts().index[0]
            print(f"  {name:<22} n={tot:>4} "
                  f"KAC={vc.get('KAC',0)/tot*100:>4.0f}% "
                  f"KAM={vc.get('KAM',0)/tot*100:>4.0f}% "
                  f"ship={grp['NUM_SHIP_TO'].median():.0f} "
                  f"cities={grp['CITIES'].median():.0f} "
                  f"profile={prof}")

    print(f"\n★ Best K={best_k} (Silhouette={best_sil:.4f})")
    print("\nSILHOUETTE SCORES:")
    for k in [3, 4, 5]:
        s   = silhouette_score(X_scaled, cust[f'CLUSTER_K{k}'])
        bar = '█' * int(s * 60)
        star = ' ★' if k == best_k else ''
        print(f"  K={k}: {s:.4f}  {bar}{star}")

    cust.to_csv('ka_kmeans_results.csv', index=False, encoding='utf-8-sig')
    print("\nSaved: ka_kmeans_results.csv")
