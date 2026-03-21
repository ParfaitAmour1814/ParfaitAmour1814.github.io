# Cost Variance Dashboard (627 Manufacturing Overhead)
**Author:** Truong Phat | Pricing & Costing Specialist, Vinamilk  
**Tool:** Power BI Desktop  
**Data:** Anonymised manufacturing cost data — GL accounts 627, 641, 642 (2023–2025)

---

## What This Project Does

A multi-page Power BI dashboard analysing manufacturing overhead costs (Account 627) across 13 factory units, broken down by cost category, product group, and production volume. Covers 3 fiscal years (2023–2025) with year-on-year variance analysis, cost-per-kg efficiency metrics, and revenue-to-cost ratio tracking.

---

## Dashboard Pages

| Page | Description |
|---|---|
| **Thống kê 1** | Monthly cost trend overview — YoY comparison across all factories with treemap breakdown by unit |
| **Check Lũy Kế 627** | Cumulative cost detail by category (Labor, Depreciation, Variable, Fixed) with waterfall variance by factory |
| **Horizontal** | Cost per kg vs production volume scatter — factory efficiency comparison with donut breakdown |
| **627/Dls** | Batch material cost analysis — cost % vs production volume by factory and product group |
| **DTND** | Overall cost vs revenue analysis — cost structure as % of revenue by product group and factory |

---

## Data Sources (Anonymised)

All data has been anonymised — factory names replaced with Factory A through Factory M, fiscal years replaced with Year 1/2/3, and financial figures scaled.

| File | Description | Key Columns |
|---|---|---|
| `627-2023/24/25.csv` | GL manufacturing overhead entries | `EFFECTIVE_DATE`, `TAIKHOAN`, `REASON`, `NHÓM SP`, `GT23/24/25`, `Ten` |
| `641-2024/25.csv` | Selling expense GL entries | `EFFECTIVE_DATE`, `ACCOUNTED_DR`, `ACCOUNTED_CR` |
| `642-2024/25.csv` | Advertising expense GL entries | `EFFECTIVE_DATE`, `642Amount24/25` |
| `SanLuong-2023/24/25.csv` | Production volume by factory & product | `PERIOD`, `CodeNM`, `ITEM`, `NHÓM`, `Sản Lượng` |
| `SanLuongCST004.csv` | Production volume from cost system | `PERIOD`, `OPERATING_UNIT`, `QTY_KG` |
| `DIS01-2024/25.csv` | Batch material cost transactions | `TRANS_DATE`, `SOURCE_DESC`, `ORGANIZATION_CODE`, `AMOUNT` |
| `INV021-2024/25.csv` | Inventory transactions by area | `TRX_DATE`, `KHUVUC`, `TEN_DV`, `AMOUNT` |
| `ITEM_MASTER.csv` | Product master with net weight | `ITEM_NO`, `DESCRIPTION`, `NET_KG` |
| `MaSP.csv` | Product group mapping | `ITEM`, `NHÓM`, `NET_KG` |
| `DoanhThu_BI.xlsx` | Revenue and sales volume | `ITEM`, `THÁNG`, `Doanh thu 24/25`, `Doanh Số 24/25` |

---

## Data Model

```
627-2023 ─┐
627-2024 ─┼──► Combined GL fact table
627-2025 ─┘         │
                     ├── JOIN → Org (factory master)
                     ├── JOIN → Phân loại báo cáo (cost category mapping)
                     └── JOIN → Mã SP (product group)

SanLuong ──────────► Production volume fact
DIS01 ─────────────► Batch material cost fact
INV021 ─────────────► Inventory movement fact
Doanh thu ─────────► Revenue fact

Reference tables (from Master627):
- Org: factory codes and names
- Phân loại báo cáo: cost reason → category hierarchy
- Kho: warehouse to factory mapping
- Mã SP: item to product group mapping
```

---

## Key Metrics & DAX

- **GT (Gross Total):** Sum of actual manufacturing costs from GL
- **GT/kg:** Cost per kilogram of production output
- **%GT by Don Vi:** Factory's share of total cost
- **+/- GT:** YoY cost variance (Current Year - Prior Year)
- **%+/- GT:** YoY variance as percentage
- **%627/DT:** Manufacturing cost as % of revenue
- **%Mater/DT:** Material cost as % of revenue

---

## Key Insights (Anonymised)

- Total manufacturing overhead ~3.7T VND in Year 3, up ~4.7% vs Year 2
- Labor & Depreciation accounts for ~59% of total cost
- Variable factory costs (energy, chemicals, maintenance by output) ~27%
- Fixed factory costs (transport, maintenance, services) ~14%
- Cost per kg ranges significantly across factories — scatter analysis identifies efficiency outliers
- Factory B has the highest production volume (~34% of total) but mid-range cost efficiency

---

## Skills Demonstrated

- **Power BI Desktop** — multi-page dashboard, complex DAX measures, drill-through, slicers
- **Power Query (M language)** — multi-source ETL, folder-based file loading, custom column logic, pivot/unpivot
- **Oracle EBS** — data extraction from enterprise ERP (GL, inventory, cost modules)
- **Cost accounting domain** — VAS-compliant manufacturing overhead analysis, cost-per-unit calculation, P&L integration
- **Data storytelling** — translating complex cost structures into executive-readable visuals
