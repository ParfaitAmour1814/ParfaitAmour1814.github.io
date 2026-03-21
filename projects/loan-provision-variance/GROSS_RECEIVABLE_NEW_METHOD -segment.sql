def l_mo = "'2021.12'";

-- step 01: process stage -----------------------------------------------------
insert into AP_FIN.tfi_contract_stage
select  skp_credit_case
        , skp_credit_type
        , trunc(date_balance) as date_balance
        , case
            when flag_deterioration = 1 then 'stage 2'
            when flag_deterioration = 0 then 'stage 1'
          end as stage_split
from  AP_RISK.ft_ifrs9_contract_deter
where trunc(date_balance) = to_date(&l_mo, 'yyyy.mm') - 1
--where trunc(date_balance) = last_day(to_date(&l_mo, 'yyyy.mm'))
;
commit;

-- step 02: process accounting overview -----------------------------------------------------
exec dbms_stats.gather_table_stats(ownname => 'ap_fin', tabname => 'tfi_acc_overview', estimate_percent => 0.01);
exec dbms_stats.gather_table_stats(ownname => 'ap_fin', tabname => 'tfi_acc_overview_new', estimate_percent => 0.01);

delete AP_FIN.tfi_acc_overview_new t1
where t1.mo = &l_mo
;
commit;

insert /*+append*/ into AP_FIN.tfi_acc_overview_new
with tmp_writeoff_acc_dd as
(
  select  --+materialize
          t1.text_contract_number
--          , sum(t1.sum_176) as sum_176
--          , sum(t1.sum_177) as sum_177
--          , sum(t1.sum_178) as sum_178
          , 0 as sum_176
          , 0 as sum_177
          , 0 as sum_178
  from  ap_fin.tfi_writeoff_acc_dd t1
  where t1.mo <= &l_mo
  group by t1.text_contract_number
)
, tmp_cre_adjustment as
(
  select  --+materialize
          t1.mo
          , t1.skp_credit_case
          , t1.amt_move_481 + t1.amt_move_483 - t1.amt_move_625 + t1.amt_move_701 + t1.amt_move_716 + t1.amt_move_801 + t1.amt_move_816 as amt_principal
          , t1.amt_move_702 + t1.amt_move_802 as amt_interest
  from  AP_FIN.tfi_cre_adjustment t1
  where t1.mo = &l_mo
)
select  &l_mo as mo
        , t1.skp_credit_case
        , t1.code_cross
        , case
            when t2.code_accounting_method = 'REL' then decode(t2.type_product, 'CC_CLX', 'CC_CLX', 'CC_CD')
--            when t2.code_accounting_method is null then substr(t1.CODE_CROSS,1,2)
            else t2.type_product
          end as prod_type
        , t1.amt_principal + nvl(t3.sum_176, 0) - nvl(t4.amt_principal, 0) - nvl(t9.amt_principal, 0) as amt_principal_outstanding
        , t1.amt_interest + nvl(t3.sum_177, 0) - nvl(t4.amt_interest, 0) as amt_interest
--        , case
--            when t2.code_accounting_method = 'REL' then t1.sum_2282 + t1.sum_282 - t1.sum_302 - t1.sum_542 - t1.sum_306 + nvl(t3.sum_177, 0) - nvl(t4.amt_interest, 0) - nvl(t9.amt_interest, 0)
--            else t1.amt_interest + nvl(t3.sum_177, 0) - nvl(t4.amt_interest, 0)
--          end as amt_interest
        , t1.amt_penalty + nvl(t3.sum_178, 0) - nvl(t4.amt_penalty, 0) as amt_penalty
        , t1.dpd_original as dpd
        , null as code_cross_previous
        , t1.skp_credit_status
        , 'Y' as code_status
--        , t7.stage_split
        , case
            when t1.dpd > 90 then 'stage 3'
            when t1.dpd > 30 then 'stage 2'
            when t8.skp_credit_case is not null then 'stage 2'
            when t7.stage_split is null then 'stage 1'
            else t7.stage_split
          end as stage_split
        , decode(t8.skp_credit_case, null, 'N', 'Y') as flag_covid
from  AP_FIN.tfi_acc_overview_2104 t1
 join  AP_FIN.tfi_contract t2 on t2.skp_credit_case = t1.skp_credit_case
left join tmp_writeoff_acc_dd t3 on t3.text_contract_number = t2.text_contract_number
left join AP_FIN.tfi_writeoff_acc t4 on t4.text_contract_number = t2.text_contract_number
                                    and t4.mo = &l_mo
left join AP_FIN.tfi_acc_overview t6 on t6.skp_credit_case = t1.skp_credit_case
                                    and t6.mo = to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -1), 'yyyy.mm')
left join AP_FIN.tfi_contract_stage t7 on t7.skp_credit_case = t1.skp_credit_case
                                      and trunc(t7.date_balance) = to_date(&l_mo, 'yyyy.mm') - 1
left join AP_RISK.covid_flag t8 on t8.skp_credit_case = t1.skp_credit_case
                               and t8.flag_covid = 1
                               and to_char(t8.date_application, 'yyyy.mm') = &l_mo
left join tmp_cre_adjustment t9 on t9.skp_credit_case = t1.skp_credit_case
where t1.mo = &l_mo
  and t6.skp_credit_case is null
  and t1.skp_credit_status not in (3, 4, 201)
--  and t1.skp_credit_case = 80213556
--  and t1.is_active = '1'
;
commit;
exec dbms_stats.gather_table_stats(ownname => 'ap_fin', tabname => 'tfi_acc_overview_new', estimate_percent => 0.01);

insert /*+append*/ into AP_FIN.tfi_acc_overview_new
with tmp_writeoff_acc_dd as
(
  select  t1.text_contract_number
--          , sum(t1.sum_176) as sum_176
--          , sum(t1.sum_177) as sum_177
--          , sum(t1.sum_178) as sum_178
          , 0 as sum_176
          , 0 as sum_177
          , 0 as sum_178
  from  ap_fin.tfi_writeoff_acc_dd t1
  where t1.mo <= &l_mo
  group by t1.text_contract_number
)
, tmp_cre_adjustment as
(
  select  --+materialize
          t1.mo
          , t1.skp_credit_case
          , t1.amt_move_481 + t1.amt_move_483 - t1.amt_move_625 + t1.amt_move_701 + t1.amt_move_716 + t1.amt_move_801 + t1.amt_move_816 as amt_principal
          , t1.amt_move_702 + t1.amt_move_802 as amt_interest
  from  AP_FIN.tfi_cre_adjustment t1
  where t1.mo = &l_mo
)
select  &l_mo as mo
        , t1.skp_credit_case
        , t2.code_accounting_method || '-' || case
                                                when t1.dpd <= 0 then 'aboc'
                                                when t1.dpd <= 15 then 'b001'
                                                when t1.dpd <= 30 then 'b016'
                                                when t1.dpd <= 60 then 'b031'
                                                when t1.dpd <= 90 then 'b061'
                                                when t1.dpd <= 120 then 'b091'
                                                when t1.dpd <= 150 then 'b121'
                                                when t1.dpd <= 180 then 'b151'
                                                when t1.dpd <= 210 then 'b181'
                                                when t1.dpd <= 240 then 'b211'
                                                when t1.dpd <= 270 then 'b241'
                                                when t1.dpd <= 300 then 'b271'
                                                when t1.dpd <= 330 then 'b301'
                                                when t1.dpd <= 360 then 'b331'
                                                when t1.dpd <= 390 then 'b361'
                                                when t1.dpd <= 420 then 'b391'
                                                when t1.dpd <= 450 then 'b421'
                                                when t1.dpd <= 480 then 'b451'
                                                when t1.dpd <= 510 then 'b481'
                                                when t1.dpd <= 540 then 'b511'
                                                when t1.dpd <= 570 then 'b541'
                                                when t1.dpd <= 600 then 'b571'
                                                when t1.dpd <= 630 then 'b601'
                                                when t1.dpd <= 660 then 'b631'
                                                when t1.dpd <= 690 then 'b661'
                                                when t1.dpd <= 720 then 'b691'
                                                when t1.dpd <= 750 then 'b721'
                                                when t1.dpd <= 780 then 'b751'
                                                when t1.dpd <= 810 then 'b781'
                                                when t1.dpd <= 840 then 'b811'
                                                when t1.dpd <= 870 then 'b841'
                                                when t1.dpd <= 900 then 'b871'
                                                when t1.dpd <= 930 then 'b901'
                                                when t1.dpd <= 960 then 'b931'
                                                when t1.dpd <= 990 then 'b961'
                                                when t1.dpd <= 1020 then 'b991'
                                                when t1.dpd <= 1050 then 'b1021'
                                                when t1.dpd <= 1080 then 'b1051'
                                                when t1.dpd > 1080 then 'b1081'
                                            end as code_cross
        , case
            when t2.code_accounting_method = 'REL' then decode(t2.type_product, 'CC_CLX', 'CC_CLX', 'CC_CD')
--                        when t2.code_accounting_method is null then substr(t1.CODE_CROSS,1,2)
            else t2.type_product
          end as prod_type
        , t1.amt_principal + nvl(t3.sum_176, 0) - nvl(t4.amt_principal, 0) - nvl(t9.amt_principal, 0) as amt_principal_outstanding
        , t1.amt_interest + nvl(t3.sum_177, 0) - nvl(t4.amt_interest, 0) as amt_interest
--        , case
--            when t2.code_accounting_method = 'REL' then t1.sum_2282 + t1.sum_282 - t1.sum_302 - t1.sum_542 - t1.sum_306 + nvl(t3.sum_177, 0) - nvl(t4.amt_interest, 0) - nvl(t9.amt_interest, 0)
--            else t1.amt_interest + nvl(t3.sum_177, 0) - nvl(t4.amt_interest, 0)
--          end as amt_interest
        , t1.amt_penalty + nvl(t3.sum_178, 0) - nvl(t4.amt_penalty, 0) as amt_penalty
        , t1.dpd_original as dpd
        , t6.code_cross as code_cross_previous
        , t1.skp_credit_status
        , 'Y' as code_status
--        , t7.stage_split
        , case
            when t1.dpd > 90 then 'stage 3'
            when t1.dpd > 30 then 'stage 2'
            when t8.skp_credit_case is not null then 'stage 2'
            when t7.stage_split is null then 'stage 1'
            else t7.stage_split
          end as stage_split
        , decode(t8.skp_credit_case, null, 'N', 'Y') as flag_covid
from  AP_FIN.tfi_acc_overview_2104 t1
 join  AP_FIN.tfi_contract t2 on t2.skp_credit_case = t1.skp_credit_case
left join tmp_writeoff_acc_dd t3 on t3.text_contract_number = t2.text_contract_number
left join AP_FIN.tfi_writeoff_acc t4 on t4.text_contract_number = t2.text_contract_number
                                    and t4.mo = &l_mo
join  AP_FIN.tfi_acc_overview_new t6 on t6.skp_credit_case = t1.skp_credit_case
                                    and t6.mo = to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -1), 'yyyy.mm')
left join AP_FIN.tfi_contract_stage t7 on t7.skp_credit_case = t1.skp_credit_case
                                      and trunc(t7.date_balance) = to_date(&l_mo, 'yyyy.mm') - 1
left join AP_RISK.covid_flag t8 on t8.skp_credit_case = t1.skp_credit_case
                               and t8.flag_covid = 1
                               and trunc(t8.date_application) = last_day(to_date(&l_mo, 'yyyy.mm'))
left join tmp_cre_adjustment t9 on t9.skp_credit_case = t1.skp_credit_case
where t1.mo = &l_mo
  and t1.code_cross not like '%abnc'
  and t1.skp_credit_status not in (3, 4, 201)
--  and t1.skp_credit_case = 80213556
--  and t1.is_active = '1'
;
commit;
exec dbms_stats.gather_table_stats(ownname => 'ap_fin', tabname => 'tfi_acc_overview_new', estimate_percent => 0.01);

merge into AP_FIN.tfi_acc_overview_new t10
using (
        select  t2.rowid as row_id
        from  AP_RISK.ifrs_tbl_industry_covid t1
        join  AP_FIN.tfi_acc_overview_new t2 on t2.skp_credit_case = t1.skp_credit_case
        where 1 = 1
          and trunc(t1.date_balance) = last_day(to_date(&l_mo, 'yyyy.mm'))
          and t1.impact_by_covid = 1
          and t2.mo = &l_mo
          and t2.stage_split = 'stage 1'
      ) t11
      on
      (
        t10.rowid = t11.row_id
      )
when matched then
  update set t10.stage_split = 'stage 2'
;
commit;

merge into AP_FIN.tfi_acc_overview_new t10
using (
        select  --+materialize
                t1.rowid as row_id
                , 'write down' as stage_split
        from  AP_FIN.tfi_acc_overview_new t1
        join  AP_FIN.tfi_writeoff t2 on t2.skp_credit_case = t1.skp_credit_case
        where t2.mo between '2019.07' and t1.mo
          and t1.mo = &l_mo
      ) t11
      on
      (
        t10.rowid = t11.row_id
      )
when matched then
  update set t10.stage_split = t11.stage_split
;
commit;

-- step 03: get data ( Sheet raw data)---------------------------------------------------------
-- PHAI LOAI EL RA KHI CHAY
-- get data - all product ----------------------------------------------------
-- New Taxonomy Raw data ----------------------------------------------------------

select  measures
        ,  type_product as prod
        , code_cross as bucket
        , code_cross_previous as bucket_pre
        , wdm
        , flag_covid as covid
        , segment
        , nvl(latest_month, 0) as latest_month
        , nvl(latest_month_1, 0) as latest_month_1
        , nvl(latest_month_2, 0) as latest_month_2
        , nvl(latest_month_3, 0) as latest_month_3
        , nvl(latest_month_4, 0) as latest_month_4
        , nvl(latest_month_5, 0) as latest_month_5
from
(
  select  t1.type_product
          , t1.code_cross
          , t1.mo
          , t1.code_cross_previous
          , t2.mo as wdm
          , t1.flag_covid
          , decode(t9.skp_class_status_acquisition, 5 ,'Acquisition', 2 , 'Non-Acquisition') as Segment
          , sum(t1.amt_principal_outstanding ) as principal
          , sum(t1.amt_interest ) as interest
          , sum(t1.amt_penalty) as penalty
  from  AP_FIN.tfi_acc_overview_new t1
  join AP_FIN.tfi_contract t3 on t1.skp_credit_case = t3.skp_credit_case
  left join AP_FIN.tfi_writeoff t2 on t2.skp_credit_case = t1.skp_credit_case
                                  and t2.mo >= '2019.07'
                                  and t2.mo <= &l_mo
  left join 
  (select * from 
        (
            Select skp_credit_case
                        , skp_class_status_acquisition
                        , row_number() over (partition by skp_credit_case order by dtime_proposal desc) as rnk
            From owner_dwh.dc_application
            where flag_deleted = 'N'
        ) t1 where t1.rnk = 1
    ) t9 on t1.skp_credit_case = t9.skp_credit_case
  where t1.code_status = 'Y'
    and t1.mo between to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -5), 'yyyy.mm') and &l_mo 
    and t3.code_product not in ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
  group by  t1.type_product
            , t1.code_cross
            , t1.mo
            , t1.code_cross_previous
            , t2.mo
            , t1.flag_covid
            , decode(t9.skp_class_status_acquisition, 5 ,'Acquisition', 2 , 'Non-Acquisition')
)
unpivot
(
  v for measures in (principal, interest, penalty)
)
pivot
(
  sum(v)
  for mo in (
                &l_mo as latest_month
              , to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -1), 'yyyy.mm') as latest_month_1
              , to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -2), 'yyyy.mm') as latest_month_2
              , to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -3), 'yyyy.mm') as latest_month_3
              , to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -4), 'yyyy.mm') as latest_month_4
              , to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -5), 'yyyy.mm') as latest_month_5
            )
)
order by  case
            when measures = 'PRINCIPAL' then 1
            when measures = 'INTEREST' then 2
            when measures = 'PENALTY' then 3
          end
          ,  type_product
          , case
              when regexp_like(code_cross, 'abnc') then 1
              when regexp_like(code_cross, 'aboc') then 2
              else to_number(substr(code_cross, instr(code_cross, 'b') + 1, length(code_cross)))
            end
          , case
              when regexp_like(code_cross_previous, 'abnc') then 1
              when regexp_like(code_cross_previous, 'aboc') then 2
              else to_number(substr(code_cross_previous, instr(code_cross_previous, 'b') + 1, length(code_cross_previous)))
            end
;


-- get data - acl product ----------------------------------------------------
--select  measures
--        , type_product as prod
--        , code_cross as bucket
--        , code_cross_previous as bucket_pre
--        , wdm
--        , flag_covid as covid
--        , nvl(latest_month, 0) as latest_month
--        , nvl(latest_month_1, 0) as latest_month_1
--        , nvl(latest_month_2, 0) as latest_month_2
--        , nvl(latest_month_3, 0) as latest_month_3
--        , nvl(latest_month_4, 0) as latest_month_4
--        , nvl(latest_month_5, 0) as latest_month_5
--from
--(
--  select  case
--            when t3.name_product like '%ACLX%' then 'ACLX'
--            else 'ACL'
--          end type_product
--          , t1.code_cross
--          , t1.mo
--          , t1.code_cross_previous
--          , t2.mo as wdm
--          , t1.flag_covid
--          , sum(t1.amt_principal_outstanding ) as principal
--          , sum(t1.amt_interest ) as interest
--          , sum(t1.amt_penalty) as penalty
--  from  AP_FIN.tfi_acc_overview_new t1
--  left join AP_FIN.tfi_writeoff t2 on t2.skp_credit_case = t1.skp_credit_case
--                                  and t2.mo >= '2019.07'
--                                  and t2.mo <= &l_mo
--  join  AP_FIN.tfi_contract t3 on t3.skp_credit_case = t1.skp_credit_case
--  where t1.code_status = 'Y'
--    and t1.mo between to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -5), 'yyyy.mm') and &l_mo
--    and t3.code_accounting_method = 'CLW'
--  group by  case
--              when t3.name_product like '%ACLX%' then 'ACLX'
--              else 'ACL'
--            end
--            , t1.code_cross
--            , t1.mo
--            , t1.code_cross_previous
--            , t2.mo
--            , t1.flag_covid
--)
--unpivot
--(
--  v for measures in (principal, interest, penalty)
--)
--pivot
--(
--  sum(v)
--  for mo in (
--                &l_mo as latest_month
--              , to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -1), 'yyyy.mm') as latest_month_1
--              , to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -2), 'yyyy.mm') as latest_month_2
--              , to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -3), 'yyyy.mm') as latest_month_3
--              , to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -4), 'yyyy.mm') as latest_month_4
--              , to_char(add_months(to_date(&l_mo, 'yyyy.mm'), -5), 'yyyy.mm') as latest_month_5
--            )
--)
--order by  case
--            when measures = 'PRINCIPAL' then 1
--            when measures = 'INTEREST' then 2
--            when measures = 'PENALTY' then 3
--          end
--          , prod
--          , bucket
--          , bucket_pre
--;

-- end step 03 ---------------------------------------------------------------


-- step 04: get data with stage ( sheet data stage) testing ----------------------------------------
with taxonomy as 
(select * from 
        (
            Select skp_credit_case
                        , skp_class_status_acquisition
                        , row_number() over (partition by skp_credit_case order by dtime_proposal desc) as rnk
            From owner_dwh.dc_application
            where flag_deleted ='N'
        ) t1 where t1.rnk = 1
    )
select   t1.type_product as prod
        , t1.code_cross as bucket
        , t1.mo
        , t2.mo as wdm
        , t1.stage_split as stage
        , t1.flag_covid as covid
        , decode(t9.skp_class_status_acquisition, 5 ,'Acquisition', 2 , 'Non-Acquisition') as Segment
        , sum(t1.amt_principal_outstanding) as principal
        , sum(t1.amt_interest) as interest
        , sum(t1.amt_penalty) as penalty
from  AP_FIN.tfi_acc_overview_new t1
join AP_FIN.tfi_contract t3 on t3.skp_credit_case = t1.skp_credit_case
left join AP_FIN.tfi_writeoff t2 on t2.skp_credit_case = t1.skp_credit_case
                                  and t2.mo >= '2019.07'
left join taxonomy  t9 on t9.skp_credit_case =t1.skp_credit_case
where t1.mo = &l_mo
  and t1.code_status = 'Y'
  and  t3.code_product not in ('CLXMCSC2NI','CLXSSC2NI','CLXSSC1NI','CLXMCSC1NI')
group by   t1.type_product
          , t1.code_cross
          , t1.mo
          , t2.mo
          , t1.stage_split
          , t1.flag_covid
          , decode(t9.skp_class_status_acquisition, 5 ,'Acquisition', 2 , 'Non-Acquisition')
order by  1, 2, 3
;


-- step 05: get data with stage - aclx ----------------------------------
--select  'ACLX' as prod
--        , t1.code_cross as bucket
--        , t1.mo
--        , t2.mo as wdm
--        , t1.stage_split as stage
--        , t1.flag_covid as covid
--        , sum(t1.amt_principal_outstanding) as principal
--        , sum(t1.amt_interest) as interest
--        , sum(t1.amt_penalty) as penalty
--from  AP_FIN.tfi_acc_overview_new t1
--left join AP_FIN.tfi_writeoff t2 on t2.skp_credit_case = t1.skp_credit_case
--                                  and t2.mo >= '2019.07'
--join  AP_FIN.tfi_contract t3 on t3.skp_credit_case = t1.skp_credit_case
--where 1 = 1
--  and t1.mo = &l_mo
----  and t1.mo between '2020.12' and '2021.05'
--  and t1.code_status = 'Y'
--  and t3.code_accounting_method = 'CLW'
--  and t3.name_product like '%ACLX%'
--group by  t1.code_cross
--          , t1.mo
--          , t2.mo
--          , t1.stage_split
--          , t1.flag_covid
;