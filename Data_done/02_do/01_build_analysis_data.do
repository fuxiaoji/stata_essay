version 16.0
clear all
set more off

capture log close
log using "$OUT/build_analysis_data.log", replace text

use "$RAW", clear

capture confirm variable year
if _rc == 0 {
    keep if year == 2022
}
else {
    gen year = 2022
}

gen age2 = age_^2 if !missing(age_)
label variable age_ "Respondent age"
label variable age2 "Respondent age squared"

gen lnwage = ln(wage + 1) if wage >= 0 & !missing(wage)
label variable lnwage "Log individual wage income ln(wage+1)"

keep if inrange(age_, 18, 64)
keep if !missing(wage)

egen miss_core = rowmiss(lnwage educ age_ age2 gen mar rural medsure_dum provcd)
keep if miss_core == 0
drop miss_core

keep pid year provcd age_ age2 gen mar rural medsure_dum edu educ wage lnwage inc1 job
order pid year provcd age_ age2 gen mar rural medsure_dum edu educ wage lnwage inc1 job

assert year == 2022
assert inrange(age_, 18, 64)
assert !missing(lnwage, educ, age2, gen, mar, rural, medsure_dum, provcd)

compress
save "$WORK/analysis.dta", replace
save "$WORK/cfps2022_education_income_analysis.dta", replace

describe
summarize wage lnwage educ age_ age2
log close
