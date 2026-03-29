/* ============================================================
   IFRS 9 PROVISION VARIANCE ANALYSIS — WRITE-DOWN PORTFOLIO
   ============================================================
   Author  : Truong Phat | Finance Executive, Home Credit Vietnam
   Purpose : Month-on-month provision movement analysis for the
             write-down (Stage 2/3) portfolio, broken down by
             product segment and acquisition channel.

   Design note:
   Each product segment (CDACQ, CDNONACQ, TW, CLXSACQ, etc.)
   is written as a standalone query block intentionally.
   This allows non-technical users and management to run,
   read, and maintain individual segments independently
   without risk of breaking other segments.

   How to use:
   1. Set the two month variables at the top:
        l_mo_p = prior month   (e.g. '2021.11')
        l_mo_c = current month (e.g. '2021.12')
   2. Run each segment block separately in SQL Developer
   3. Export results to Excel for P&L reporting

   Output columns:
   - Text_contract_number : Unique contract identifier
   - WDM                  : Write-down month
   - Code_cross_pre       : DPD bucket in prior month
                            ('New WD' = contract newly entered WD portfolio)
   - Balance_pre          : Outstanding balance prior month (Principal + Interest + Penalty)
   - Provision_pre        : Provision amount prior month
   - Code_cross_cur       : DPD bucket in current month
                            ('Finished' = contract exited WD portfolio)
   - Balance_cur          : Outstanding balance current month
   - Provision_cur        : Provision amount current month
   - Provision_Var        : Provision movement (Cur - Pre)
   - Act - Est            : Movement classification:
                            'New_WD'       = new contract entered write-down
                            'Recovery'     = provision decreased
                            'Additional WO'= provision increased
                            'No adj'       = no change

   Source tables:
   - AP_FIN.tfi_acc_overview_new  : Monthly accounting overview (main fact)
   - AP_FIN.tfi_contract          : Contract master data
   - AP_FIN.tfi_provisioning_rate : ECL provisioning rates by bucket/month
   - AP_FIN.tfi_writeoff          : Write-off/write-down event dates
   - owner_dwh.dc_application     : Application data (for acquisition flag)
   ============================================================ */

-- Set reporting period (update these two lines each month run)
def l_mo_p = "'2021.11'";   -- Prior month
def l_mo_c = "'2021.12'";   -- Current month


/* ============================================================
   SEGMENT 1: CD — ACQUISITION
   Cash Disbursement loans, Acquisition channel (skp_class_status_acquisition = 5)
   ============================================================ */

WITH taxonomy AS (
    -- Deduplicate to latest application record per contract
    SELECT *
    FROM (
        SELECT
            skp_credit_case,
            skp_class_status_acquisition,
            ROW_NUMBER() OVER (
                PARTITION BY skp_credit_case
                ORDER BY dtime_proposal DESC
            ) AS rnk
        FROM owner_dwh.dc_application
        WHERE flag_deleted = 'N'
    ) t
    WHERE rnk = 1
),

-- Prior month snapshot
P AS (
    SELECT
        t1.mo                                                               AS mo_pre,
        t4.mo                                                               AS wdm,
        t2.text_contract_number,
        t5.skp_class_status_acquisition,
        t2.code_accounting_method,
        t2.type_product,
        t1.code_cross                                                       AS code_cross_pre,
        -- Total exposure = Principal + Interest + Penalty
        t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty     AS balance_pre,
        -- Provision = ECL rate × Total exposure
        t3.rate_provisioning_stage_2_3
            * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_pre
    FROM AP_FIN.tfi_acc_overview_new    t1
    JOIN AP_FIN.tfi_contract            t2  ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy                  t5  ON t5.skp_credit_case = t1.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON  t3.code_cross = CASE
                -- REL products use a remapped code_cross for rate lookup
                WHEN t2.code_accounting_method = 'REL'
                THEN DECODE(t2.type_product, 'CC_CLX', 'CC_CLX', 'CC_CD')
                     || REPLACE(t1.code_cross, 'REL', '')
                ELSE t1.code_cross
            END
        AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff       t4  ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_p
      -- Exclude NI (non-insured) CLX variants — handled in separate segment
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      -- Only include write-downs from Jul 2019 onward (policy cutoff)
      AND t4.mo > '2019.06'
      AND t1.mo >= t4.mo
),

-- Current month snapshot (same logic as P, different month filter)
C AS (
    SELECT
        t1.mo                                                               AS mo_cur,
        t4.mo                                                               AS wdm,
        t2.text_contract_number,
        t5.skp_class_status_acquisition,
        t2.code_accounting_method,
        t2.type_product,
        t1.code_cross                                                       AS code_cross_cur,
        t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty     AS balance_cur,
        t3.rate_provisioning_stage_2_3
            * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_cur
    FROM AP_FIN.tfi_acc_overview_new    t1
    JOIN AP_FIN.tfi_contract            t2  ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy                  t5  ON t5.skp_credit_case = t1.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON  t3.code_cross = CASE
                WHEN t2.code_accounting_method = 'REL'
                THEN DECODE(t2.type_product, 'CC_CLX', 'CC_CLX', 'CC_CD')
                     || REPLACE(t1.code_cross, 'REL', '')
                ELSE t1.code_cross
            END
        AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff       t4  ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_c
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06'
      AND t1.mo >= t4.mo
)

-- Final output: full outer join to capture all movements including new entries and exits
SELECT
    NVL(P.text_contract_number, C.text_contract_number)    AS text_contract_number,
    NVL(P.wdm,              C.wdm)                         AS wdm,
    NVL(code_cross_pre,     'New WD')                      AS code_cross_pre,  -- 'New WD' = newly entered WD portfolio this month
    NVL(balance_pre,        0)                             AS balance_pre,
    NVL(provision_pre,      0)                             AS provision_pre,
    NVL(code_cross_cur,     'Finished')                    AS code_cross_cur,  -- 'Finished' = exited WD portfolio this month
    NVL(balance_cur,        0)                             AS balance_cur,
    NVL(provision_cur,      0)                             AS provision_cur,
    NVL(provision_cur,      0) - NVL(provision_pre, 0)     AS provision_var,
    -- Movement classification for P&L reporting
    CASE
        WHEN code_cross_pre IS NULL
            THEN 'New_WD'           -- Contract newly appeared in write-down this month
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) < 0
            THEN 'Recovery'         -- Provision decreased (positive for P&L)
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) > 0
            THEN 'Additional WO'    -- Provision increased (negative for P&L)
        ELSE
            'No adj'                -- No change
    END AS "Act - Est"
FROM P
FULL JOIN C ON P.text_contract_number = C.text_contract_number
-- Filter: CD product, Acquisition channel only
WHERE NVL(P.code_accounting_method, C.code_accounting_method) = 'CD'
  AND NVL(C.skp_class_status_acquisition, P.skp_class_status_acquisition) = 5  -- 5 = Acquisition
  AND NVL(balance_pre, 0) + NVL(balance_cur, 0) <> 0;  -- Exclude zero-balance rows


/* ============================================================
   SEGMENT 2: CD — NON-ACQUISITION
   Cash Disbursement loans, Non-Acquisition channel (skp_class_status_acquisition = 2)
   Only difference from Segment 1: final WHERE clause filter = 2
   ============================================================ */

WITH taxonomy AS (
    SELECT *
    FROM (
        SELECT
            skp_credit_case,
            skp_class_status_acquisition,
            ROW_NUMBER() OVER (
                PARTITION BY skp_credit_case
                ORDER BY dtime_proposal DESC
            ) AS rnk
        FROM owner_dwh.dc_application
        WHERE flag_deleted = 'N'
    ) t
    WHERE rnk = 1
),
P AS (
    SELECT
        t1.mo AS mo_pre, t4.mo AS wdm,
        t2.text_contract_number, t5.skp_class_status_acquisition,
        t2.code_accounting_method, t2.type_product,
        t1.code_cross AS code_cross_pre,
        t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_pre,
        t3.rate_provisioning_stage_2_3
            * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_pre
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t5.skp_credit_case = t1.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON  t3.code_cross = CASE
                WHEN t2.code_accounting_method = 'REL'
                THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
                ELSE t1.code_cross END
        AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_p
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
),
C AS (
    SELECT
        t1.mo AS mo_cur, t4.mo AS wdm,
        t2.text_contract_number, t5.skp_class_status_acquisition,
        t2.code_accounting_method, t2.type_product,
        t1.code_cross AS code_cross_cur,
        t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_cur,
        t3.rate_provisioning_stage_2_3
            * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_cur
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t5.skp_credit_case = t1.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON  t3.code_cross = CASE
                WHEN t2.code_accounting_method = 'REL'
                THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
                ELSE t1.code_cross END
        AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_c
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
)
SELECT
    NVL(P.text_contract_number, C.text_contract_number)    AS text_contract_number,
    NVL(P.wdm, C.wdm)                                      AS wdm,
    NVL(code_cross_pre,  'New WD')                         AS code_cross_pre,
    NVL(balance_pre,     0)                                AS balance_pre,
    NVL(provision_pre,   0)                                AS provision_pre,
    NVL(code_cross_cur,  'Finished')                       AS code_cross_cur,
    NVL(balance_cur,     0)                                AS balance_cur,
    NVL(provision_cur,   0)                                AS provision_cur,
    NVL(provision_cur,   0) - NVL(provision_pre, 0)        AS provision_var,
    CASE
        WHEN code_cross_pre IS NULL                                         THEN 'New_WD'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) < 0               THEN 'Recovery'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) > 0               THEN 'Additional WO'
        ELSE 'No adj'
    END AS "Act - Est"
FROM P
FULL JOIN C ON P.text_contract_number = C.text_contract_number
WHERE NVL(P.code_accounting_method, C.code_accounting_method) = 'CD'
  AND NVL(C.skp_class_status_acquisition, P.skp_class_status_acquisition) = 2  -- 2 = Non-Acquisition
  AND NVL(balance_pre,0) + NVL(balance_cur,0) <> 0;


/* ============================================================
   SEGMENT 3: TW — TWO-WHEELER
   No acquisition split for TW (single portfolio)
   ============================================================ */

WITH taxonomy AS (
    SELECT *
    FROM (
        SELECT skp_credit_case, skp_class_status_acquisition,
               ROW_NUMBER() OVER (PARTITION BY skp_credit_case ORDER BY dtime_proposal DESC) AS rnk
        FROM owner_dwh.dc_application WHERE flag_deleted = 'N'
    ) t WHERE rnk = 1
),
P AS (
    SELECT t1.mo AS mo_pre, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_pre,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_pre,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_pre
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_p AND t4.mo > '2019.06' AND t1.mo >= t4.mo
),
C AS (
    SELECT t1.mo AS mo_cur, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_cur,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_cur,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_cur
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_c AND t4.mo > '2019.06' AND t1.mo >= t4.mo
)
SELECT
    NVL(P.text_contract_number, C.text_contract_number) AS text_contract_number,
    NVL(P.wdm, C.wdm) AS wdm,
    NVL(code_cross_pre, 'New WD')    AS code_cross_pre,
    NVL(balance_pre,    0)           AS balance_pre,
    NVL(provision_pre,  0)           AS provision_pre,
    NVL(code_cross_cur, 'Finished')  AS code_cross_cur,
    NVL(balance_cur,    0)           AS balance_cur,
    NVL(provision_cur,  0)           AS provision_cur,
    NVL(provision_cur,  0) - NVL(provision_pre, 0) AS provision_var,
    CASE
        WHEN code_cross_pre IS NULL                                   THEN 'New_WD'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) < 0         THEN 'Recovery'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) > 0         THEN 'Additional WO'
        ELSE 'No adj'
    END AS "Act - Est"
FROM P
FULL JOIN C ON P.text_contract_number = C.text_contract_number
WHERE NVL(P.code_accounting_method, C.code_accounting_method) = 'TW'
  AND NVL(balance_pre,0) + NVL(balance_cur,0) <> 0;


/* ============================================================
   SEGMENT 4: CLXS — ACQUISITION
   Consumer Electronics (Standard), Acquisition channel
   ============================================================ */

WITH taxonomy AS (
    SELECT * FROM (
        SELECT skp_credit_case, skp_class_status_acquisition,
               ROW_NUMBER() OVER (PARTITION BY skp_credit_case ORDER BY dtime_proposal DESC) AS rnk
        FROM owner_dwh.dc_application WHERE flag_deleted = 'N'
    ) t WHERE rnk = 1
),
P AS (
    SELECT t1.mo AS mo_pre, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_pre,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_pre,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_pre
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_p
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
),
C AS (
    SELECT t1.mo AS mo_cur, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_cur,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_cur,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_cur
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_c
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
)
SELECT
    NVL(P.text_contract_number, C.text_contract_number) AS text_contract_number,
    NVL(P.wdm, C.wdm) AS wdm,
    NVL(code_cross_pre, 'New WD')    AS code_cross_pre,
    NVL(balance_pre,    0)           AS balance_pre,
    NVL(provision_pre,  0)           AS provision_pre,
    NVL(code_cross_cur, 'Finished')  AS code_cross_cur,
    NVL(balance_cur,    0)           AS balance_cur,
    NVL(provision_cur,  0)           AS provision_cur,
    NVL(provision_cur,  0) - NVL(provision_pre, 0) AS provision_var,
    CASE
        WHEN code_cross_pre IS NULL                                   THEN 'New_WD'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) < 0         THEN 'Recovery'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) > 0         THEN 'Additional WO'
        ELSE 'No adj'
    END AS "Act - Est"
FROM P
FULL JOIN C ON P.text_contract_number = C.text_contract_number
WHERE NVL(P.code_accounting_method, C.code_accounting_method) = 'CL'
  AND NVL(C.skp_class_status_acquisition, P.skp_class_status_acquisition) = 5  -- 5 = Acquisition
  AND NVL(balance_pre,0) + NVL(balance_cur,0) <> 0;


/* ============================================================
   SEGMENT 5: CLXS — NON-ACQUISITION
   Consumer Electronics (Standard), Non-Acquisition channel
   ============================================================ */

WITH taxonomy AS (
    SELECT * FROM (
        SELECT skp_credit_case, skp_class_status_acquisition,
               ROW_NUMBER() OVER (PARTITION BY skp_credit_case ORDER BY dtime_proposal DESC) AS rnk
        FROM owner_dwh.dc_application WHERE flag_deleted = 'N'
    ) t WHERE rnk = 1
),
P AS (
    SELECT t1.mo AS mo_pre, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_pre,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_pre,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_pre
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_p
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
),
C AS (
    SELECT t1.mo AS mo_cur, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_cur,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_cur,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_cur
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_c
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
)
SELECT
    NVL(P.text_contract_number, C.text_contract_number) AS text_contract_number,
    NVL(P.wdm, C.wdm) AS wdm,
    NVL(code_cross_pre, 'New WD')    AS code_cross_pre,
    NVL(balance_pre,    0)           AS balance_pre,
    NVL(provision_pre,  0)           AS provision_pre,
    NVL(code_cross_cur, 'Finished')  AS code_cross_cur,
    NVL(balance_cur,    0)           AS balance_cur,
    NVL(provision_cur,  0)           AS provision_cur,
    NVL(provision_cur,  0) - NVL(provision_pre, 0) AS provision_var,
    CASE
        WHEN code_cross_pre IS NULL                                   THEN 'New_WD'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) < 0         THEN 'Recovery'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) > 0         THEN 'Additional WO'
        ELSE 'No adj'
    END AS "Act - Est"
FROM P
FULL JOIN C ON P.text_contract_number = C.text_contract_number
WHERE NVL(P.code_accounting_method, C.code_accounting_method) = 'CL'
  AND NVL(C.skp_class_status_acquisition, P.skp_class_status_acquisition) = 2  -- 2 = Non-Acquisition
  AND NVL(balance_pre,0) + NVL(balance_cur,0) <> 0;


/* ============================================================
   SEGMENT 6: CLWI — ACQUISITION
   Consumer Electronics (With Insurance), Acquisition channel
   ============================================================ */

WITH taxonomy AS (
    SELECT * FROM (
        SELECT skp_credit_case, skp_class_status_acquisition,
               ROW_NUMBER() OVER (PARTITION BY skp_credit_case ORDER BY dtime_proposal DESC) AS rnk
        FROM owner_dwh.dc_application WHERE flag_deleted = 'N'
    ) t WHERE rnk = 1
),
P AS (
    SELECT t1.mo AS mo_pre, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_pre,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_pre,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_pre
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_p
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
),
C AS (
    SELECT t1.mo AS mo_cur, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_cur,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_cur,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_cur
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_c
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
)
SELECT
    NVL(P.text_contract_number, C.text_contract_number) AS text_contract_number,
    NVL(P.wdm, C.wdm) AS wdm,
    NVL(code_cross_pre, 'New WD')    AS code_cross_pre,
    NVL(balance_pre,    0)           AS balance_pre,
    NVL(provision_pre,  0)           AS provision_pre,
    NVL(code_cross_cur, 'Finished')  AS code_cross_cur,
    NVL(balance_cur,    0)           AS balance_cur,
    NVL(provision_cur,  0)           AS provision_cur,
    NVL(provision_cur,  0) - NVL(provision_pre, 0) AS provision_var,
    CASE
        WHEN code_cross_pre IS NULL                                   THEN 'New_WD'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) < 0         THEN 'Recovery'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) > 0         THEN 'Additional WO'
        ELSE 'No adj'
    END AS "Act - Est"
FROM P
FULL JOIN C ON P.text_contract_number = C.text_contract_number
WHERE NVL(P.code_accounting_method, C.code_accounting_method) = 'CLW'
  AND NVL(C.skp_class_status_acquisition, P.skp_class_status_acquisition) = 5
  AND NVL(balance_pre,0) + NVL(balance_cur,0) <> 0;


/* ============================================================
   SEGMENT 7: CLWI — NON-ACQUISITION
   Consumer Electronics (With Insurance), Non-Acquisition channel
   ============================================================ */

WITH taxonomy AS (
    SELECT * FROM (
        SELECT skp_credit_case, skp_class_status_acquisition,
               ROW_NUMBER() OVER (PARTITION BY skp_credit_case ORDER BY dtime_proposal DESC) AS rnk
        FROM owner_dwh.dc_application WHERE flag_deleted = 'N'
    ) t WHERE rnk = 1
),
P AS (
    SELECT t1.mo AS mo_pre, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_pre,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_pre,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_pre
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_p
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
),
C AS (
    SELECT t1.mo AS mo_cur, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_cur,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_cur,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_cur
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_c
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
)
SELECT
    NVL(P.text_contract_number, C.text_contract_number) AS text_contract_number,
    NVL(P.wdm, C.wdm) AS wdm,
    NVL(code_cross_pre, 'New WD')    AS code_cross_pre,
    NVL(balance_pre,    0)           AS balance_pre,
    NVL(provision_pre,  0)           AS provision_pre,
    NVL(code_cross_cur, 'Finished')  AS code_cross_cur,
    NVL(balance_cur,    0)           AS balance_cur,
    NVL(provision_cur,  0)           AS provision_cur,
    NVL(provision_cur,  0) - NVL(provision_pre, 0) AS provision_var,
    CASE
        WHEN code_cross_pre IS NULL                                   THEN 'New_WD'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) < 0         THEN 'Recovery'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) > 0         THEN 'Additional WO'
        ELSE 'No adj'
    END AS "Act - Est"
FROM P
FULL JOIN C ON P.text_contract_number = C.text_contract_number
WHERE NVL(P.code_accounting_method, C.code_accounting_method) = 'CLW'
  AND NVL(C.skp_class_status_acquisition, P.skp_class_status_acquisition) = 2
  AND NVL(balance_pre,0) + NVL(balance_cur,0) <> 0;


/* ============================================================
   SEGMENT 8: REL — REVOLVING LOAN
   Special handling: REL uses type_product sub-split (CC_CLX vs CC_CD)
   No acquisition split for REL
   ============================================================ */

WITH taxonomy AS (
    SELECT * FROM (
        SELECT skp_credit_case, skp_class_status_acquisition,
               ROW_NUMBER() OVER (PARTITION BY skp_credit_case ORDER BY dtime_proposal DESC) AS rnk
        FROM owner_dwh.dc_application WHERE flag_deleted = 'N'
    ) t WHERE rnk = 1
),
P AS (
    SELECT t1.mo AS mo_pre, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_pre,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_pre,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_pre
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_p
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
),
C AS (
    SELECT t1.mo AS mo_cur, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_cur,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_cur,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_cur
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_c
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
)
SELECT
    -- REL-specific: split output by type_product sub-category
    DECODE(NVL(P.type_product, C.type_product), 'CC_CLX', 'CC_CLX', 'CC_CD') AS type_product,
    NVL(P.text_contract_number, C.text_contract_number) AS text_contract_number,
    NVL(P.wdm, C.wdm) AS wdm,
    NVL(code_cross_pre, 'New WD')    AS code_cross_pre,
    NVL(balance_pre,    0)           AS balance_pre,
    NVL(provision_pre,  0)           AS provision_pre,
    NVL(code_cross_cur, 'Finished')  AS code_cross_cur,
    NVL(balance_cur,    0)           AS balance_cur,
    NVL(provision_cur,  0)           AS provision_cur,
    NVL(provision_cur,  0) - NVL(provision_pre, 0) AS provision_var,
    CASE
        WHEN code_cross_pre IS NULL                                   THEN 'New_WD'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) < 0         THEN 'Recovery'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) > 0         THEN 'Additional WO'
        ELSE 'No adj'
    END AS "Act - Est"
FROM P
FULL JOIN C ON P.text_contract_number = C.text_contract_number
WHERE NVL(P.code_accounting_method, C.code_accounting_method) = 'REL'
  AND NVL(balance_pre,0) + NVL(balance_cur,0) <> 0
ORDER BY DECODE(NVL(P.type_product, C.type_product), 'CC_CLX', 'CC_CLX', 'CC_CD');


/* ============================================================
   SEGMENT 9: RM — REVOLVING MORTGAGE
   No acquisition split for RM
   ============================================================ */

WITH taxonomy AS (
    SELECT * FROM (
        SELECT skp_credit_case, skp_class_status_acquisition,
               ROW_NUMBER() OVER (PARTITION BY skp_credit_case ORDER BY dtime_proposal DESC) AS rnk
        FROM owner_dwh.dc_application WHERE flag_deleted = 'N'
    ) t WHERE rnk = 1
),
P AS (
    SELECT t1.mo AS mo_pre, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_pre,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_pre,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_pre
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_p
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
),
C AS (
    SELECT t1.mo AS mo_cur, t4.mo AS wdm, t2.text_contract_number,
           t5.skp_class_status_acquisition, t2.code_accounting_method, t2.type_product,
           t1.code_cross AS code_cross_cur,
           t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty AS balance_cur,
           t3.rate_provisioning_stage_2_3
               * (t1.amt_principal_outstanding + t1.amt_interest + t1.amt_penalty) AS provision_cur
    FROM AP_FIN.tfi_acc_overview_new t1
    JOIN AP_FIN.tfi_contract t2 ON t2.skp_credit_case = t1.skp_credit_case
    LEFT JOIN taxonomy t5 ON t2.skp_credit_case = t5.skp_credit_case
    LEFT JOIN AP_FIN.tfi_provisioning_rate t3
        ON t3.code_cross = CASE WHEN t2.code_accounting_method = 'REL'
            THEN DECODE(t2.type_product,'CC_CLX','CC_CLX','CC_CD') || REPLACE(t1.code_cross,'REL','')
            ELSE t1.code_cross END AND t3.mo = t1.mo
    LEFT JOIN AP_FIN.tfi_writeoff t4 ON t4.skp_credit_case = t1.skp_credit_case
    WHERE t1.mo = &&l_mo_c
      AND t2.code_product NOT IN ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
      AND t4.mo > '2019.06' AND t1.mo >= t4.mo
)
SELECT
    NVL(P.text_contract_number, C.text_contract_number) AS text_contract_number,
    NVL(P.wdm, C.wdm) AS wdm,
    NVL(code_cross_pre, 'New WD')    AS code_cross_pre,
    NVL(balance_pre,    0)           AS balance_pre,
    NVL(provision_pre,  0)           AS provision_pre,
    NVL(code_cross_cur, 'Finished')  AS code_cross_cur,
    NVL(balance_cur,    0)           AS balance_cur,
    NVL(provision_cur,  0)           AS provision_cur,
    NVL(provision_cur,  0) - NVL(provision_pre, 0) AS provision_var,
    CASE
        WHEN code_cross_pre IS NULL                                   THEN 'New_WD'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) < 0         THEN 'Recovery'
        WHEN NVL(provision_cur,0) - NVL(provision_pre,0) > 0         THEN 'Additional WO'
        ELSE 'No adj'
    END AS "Act - Est"
FROM P
FULL JOIN C ON P.text_contract_number = C.text_contract_number
WHERE NVL(P.code_accounting_method, C.code_accounting_method) = 'RM'
  AND NVL(balance_pre,0) + NVL(balance_cur,0) <> 0;
