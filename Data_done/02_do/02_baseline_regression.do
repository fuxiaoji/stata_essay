version 16.0
clear all
set more off

capture log close
log using "$OUT/regression.log", replace text

use "$WORK/analysis.dta", clear

display as text "Sample size"
count

display as text "Descriptive statistics: wage / lnwage / educ"
summarize wage lnwage educ, detail

display as text "Education group frequency"
tabulate edu, missing

display as text "Gender distribution"
tabulate gen, missing

display as text "Rural hukou distribution"
tabulate rural, missing

display as text "Baseline model 1: lnwage on educ"
regress lnwage educ, robust
estimates store m1

display as text "Baseline model 2: add demographic and household controls"
regress lnwage educ age_ age2 gen mar rural medsure_dum, robust
estimates store m2

display as text "Baseline model 3: add province fixed effects"
regress lnwage educ age_ age2 gen mar rural medsure_dum i.provcd, robust
estimates store m3

display as text "Robustness 1: categorical education instead of education years"
regress lnwage i.edu age_ age2 gen mar rural medsure_dum i.provcd, robust
estimates store r_edu_cat

display as text "Robustness 2: household per-capita net income as alternative outcome"
gen lninc1 = ln(inc1 + 1) if inc1 >= 0 & !missing(inc1)
label variable lninc1 "Log household per-capita net income ln(inc1+1)"
regress lninc1 educ age_ age2 gen mar rural medsure_dum i.provcd, robust
estimates store r_inc1

display as text "Sensitivity check: wage > 0 sample"
regress lnwage educ age_ age2 gen mar rural medsure_dum i.provcd if wage > 0, robust
estimates store s_wage_pos

log close
