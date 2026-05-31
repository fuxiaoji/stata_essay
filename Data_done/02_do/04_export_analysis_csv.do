version 16.0
clear all
set more off

local envroot : env DATA_DONE_ROOT
if `"`envroot'"' != "" {
    global ROOT `"`envroot'"'
}
else {
    global ROOT "/Users/Zhuanz1/Desktop/code/stata_essay/Data_done"
}
global WORK "$ROOT/01_data"
global OUT  "$ROOT/03_logs"

capture log close
log using "$OUT/export_analysis_csv.log", replace text

use "$WORK/analysis.dta", clear
export delimited using "$WORK/analysis.csv", replace nolabel

display as text "Analysis CSV exported to $WORK/analysis.csv"
log close
