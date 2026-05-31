version 16.0
clear all
set more off

* If this folder is moved, either run Stata with DATA_DONE_ROOT set to the
* new Data_done folder path or edit the fallback path below.
local envroot : env DATA_DONE_ROOT
if `"`envroot'"' != "" {
    global ROOT `"`envroot'"'
}
else {
    global ROOT "/Users/Zhuanz1/Desktop/code/stata_essay/Data_done"
}

global RAW  "$ROOT/01_data/source.dta"
global WORK "$ROOT/01_data"
global OUT  "$ROOT/03_logs"
global DO   "$ROOT/02_do"

cap mkdir "$WORK"
cap mkdir "$OUT"

do "$DO/01_build_analysis_data.do"
do "$DO/02_baseline_regression.do"
do "$DO/03_make_report_figures.do"
do "$DO/04_export_analysis_csv.do"

display as text "All CFPS 2022 education-income scripts finished."
