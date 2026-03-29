# IFRS 9 Loan Provision Variance Analysis
**Author:** Truong Phat | Finance Executive, Home Credit Vietnam (Nov 2021 – Oct 2022)  
**Platform:** Oracle Database 19c | SQL Developer / SQLcl  
**Data:** Anonymised consumer finance portfolio — principal, interest, penalty balances across 30M-row enterprise data warehouse

---

## What This Project Does

Month-on-month provision movement analysis across 8 product segments for IFRS 9 Stage 2/3 (write-down) portfolio. Output feeds directly into P&L reporting for Vietnamese C-suite and European parent company consolidation.

Each run produces a contract-level reconciliation showing exactly **why** the provision balance moved from one month to the next — broken into New Write-Downs, Recoveries, and Additional Write-Offs.

---

## Files

| File | Description |
|---|---|
| `Provision_WD_Contract-Segment_CLEAN.sql` | Main provision variance query — 9 product segments |
| `GROSS_RECEIVABLE_NEW_METHOD_-segment.sql` | ETL pipeline — builds monthly accounting overview with IFRS 9 stage classification and Covid-flag adjustments |
| `2022_07_Gross_receivables_WD_Stage_-_New_Segment.xlsx` | Sample output — July 2022 gross receivables by stage, DPD bucket, segment, and Covid flag |

---

## How to Run

1. Open `Provision_WD_Contract-Segment_CLEAN.sql` in SQL Developer
2. Update the two month variables at the top of the file:
   ```sql
   def l_mo_p = "'2021.11'";   -- Prior month
   def l_mo_c = "'2021.12'";   -- Current month
   ```
3. Run each segment block individually (highlight → F9)
4. Export results to Excel for P&L reporting

> **Note:** The `&&` variable syntax is SQL Developer / SQLcl specific. On other Oracle clients, replace `&&l_mo_p` with a direct bind variable or hardcoded value.

---

## Query Design

### Why each segment is a separate block
Each product segment (CD-ACQ, CD-NONACQ, TW, CLXS-ACQ, etc.) is written as a fully standalone query rather than a single unified query. This is a deliberate design choice for **operational maintainability** — non-technical finance users can run, read, and troubleshoot individual segments without risk of affecting others. Each block is self-contained and readable without SQL expertise.

### Core logic — Full Outer Join MoM comparison
```
Prior month CTE (P)  ──┐
                        ├── FULL OUTER JOIN on contract_number ──► variance + classification
Current month CTE (C) ──┘
```
The full outer join captures three scenarios in one pass:
- Contract in P only → exited portfolio (`code_cross_cur = 'Finished'`)
- Contract in C only → newly entered portfolio (`code_cross_pre = 'New WD'`)
- Contract in both → movement within portfolio (Recovery / Additional WO / No change)

### IFRS 9 Stage classification (in `GROSS_RECEIVABLE_NEW_METHOD`)
```
DPD > 90               → Stage 3
DPD > 30               → Stage 2
Covid flag = Y         → Stage 2 (regulatory override)
Deterioration flag = 1 → Stage 2 (SICR — Significant Increase in Credit Risk)
Otherwise              → Stage 1
```

### REL product special handling
REL (Revolving) loans use a remapped `code_cross` for provisioning rate lookup:
```sql
CASE WHEN code_accounting_method = 'REL'
THEN DECODE(type_product, 'CC_CLX', 'CC_CLX', 'CC_CD') || REPLACE(code_cross, 'REL', '')
ELSE code_cross END
```
This maps REL DPD buckets to the equivalent CD or CLX rate table depending on product sub-type.

### Movement classification
| Label | Condition | P&L Impact |
|---|---|---|
| `New_WD` | Prior month balance = null (new entry) | Negative |
| `Additional WO` | Provision increased vs prior month | Negative |
| `Recovery` | Provision decreased vs prior month | Positive |
| `No adj` | No change | Neutral |

---

## Product Segments Covered

| Segment | Code | Description | ACQ Split |
|---|---|---|---|
| CD-ACQ | `CD` + status=5 | Cash Disbursement, Acquisition | Yes |
| CD-NONACQ | `CD` + status=2 | Cash Disbursement, Non-Acquisition | Yes |
| TW | `TW` | Two-Wheeler Loan | No |
| CLXS-ACQ | `CL` + status=5 | Consumer Electronics Standard, Acquisition | Yes |
| CLXS-NONACQ | `CL` + status=2 | Consumer Electronics Standard, Non-Acquisition | Yes |
| CLWI-ACQ | `CLW` + status=5 | Consumer Electronics With Insurance, Acquisition | Yes |
| CLWI-NONACQ | `CLW` + status=2 | Consumer Electronics With Insurance, Non-Acquisition | Yes |
| REL | `REL` | Revolving Loan (CC_CLX / CC_CD sub-split) | No |
| RM | `RM` | Revolving Mortgage | No |

---

## Key Technical Skills Demonstrated

- **Production Oracle SQL** — CTEs, window functions (`ROW_NUMBER OVER PARTITION`), `FULL OUTER JOIN`, `MERGE`, `UNPIVOT/PIVOT`, `DECODE`, `NVL`
- **IFRS 9 domain knowledge** — Stage 1/2/3 classification, ECL rate application, Covid-flag portfolio adjustments, write-down vs write-off distinction
- **ETL pipeline design** — multi-step `INSERT` with statistics gathering, staged commits, adjustment table reconciliation
- **Stakeholder-oriented design** — segment-by-segment structure for non-technical maintainability
