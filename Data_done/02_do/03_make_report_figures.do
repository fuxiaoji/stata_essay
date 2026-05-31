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
global FIG  "$ROOT/04_figures"

cap mkdir "$FIG"

capture log close
capture log using "$OUT/report_figures.log", replace text

use "$WORK/analysis.dta", clear

label define edu_clean 0 "文盲/半文盲" 1 "小学" 2 "初中" 3 "高中/中专" 4 "大专" 5 "大学本科" 6 "硕士" 7 "博士", replace
label values edu edu_clean

capture graph set window fontface "Microsoft YaHei"
capture graph set print fontface "Microsoft YaHei"
set scheme s1color

histogram educ, discrete percent start(0) width(1) ///
    xlabel(0 "0" 6 "6" 9 "9" 12 "12" 15 "15" 16 "16" 19 "19" 22 "22") ///
    xtitle("受教育年限") ytitle("样本比例（%）") ///
    title("图1 教育年限分布") ///
    note("数据来源：CFPS 2022；样本量 N = 4,699。") ///
    fcolor(navy%45) lcolor(navy) ///
    graphregion(color(white)) plotregion(color(white))
graph export "$FIG/fig1_educ_distribution.png", as(png) width(1800) replace

graph bar (mean) lnwage, over(edu, label(angle(25))) ///
    ytitle("平均 ln(wage + 1)") ///
    title("图2 不同教育水平的平均收入") ///
    note("教育水平按 CFPS 2022 分类变量 edu 分组。") ///
    bar(1, color(navy%55) lcolor(navy)) ///
    blabel(bar, format(%4.2f) color(black)) ///
    graphregion(color(white)) plotregion(color(white))
graph export "$FIG/fig2_mean_lnwage_by_edu.png", as(png) width(1800) replace

preserve
collapse (mean) mean_lnwage=lnwage (count) n=lnwage, by(educ)
twoway ///
    (scatter mean_lnwage educ, msymbol(circle) msize(large) mcolor(navy) lcolor(navy)) ///
    (lfit mean_lnwage educ [aw=n], lcolor(maroon) lwidth(medthick)), ///
    xlabel(0 "0" 6 "6" 9 "9" 12 "12" 15 "15" 16 "16" 19 "19" 22 "22") ///
    xtitle("受教育年限") ytitle("各教育年限组平均 ln(wage + 1)") ///
    title("图3 教育年限与收入的拟合关系") ///
    legend(order(1 "分组均值" 2 "线性拟合") rows(1) position(6)) ///
    note("点为各教育年限组均值；拟合线按组样本量加权。") ///
    graphregion(color(white)) plotregion(color(white))
graph export "$FIG/fig3_educ_lnwage_fit.png", as(png) width(1800) replace
restore

display as text "Report figures generated in $FIG"
capture log close
exit, clear
