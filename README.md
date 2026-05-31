# CFPS 2022 Education and Income Essay

This repository contains a reproducible Stata/Python/LaTeX workflow for an empirical essay on the relationship between education and income using the CFPS 2022 analytic sample.

## Structure

- `Data_done/01_data`: source and analysis datasets.
- `Data_done/02_do`: Stata and Python reproduction scripts.
- `Data_done/03_logs`: Stata reproduction logs.
- `Data_done/04_figures`: original Stata figures.
- `Data_done/05_latex`: publication figures, regression tables, and English/Chinese LaTeX papers.

## Reproduce

Run the Stata workflow:

```bash
DATA_DONE_ROOT="/Users/Zhuanz1/Desktop/code/stata_essay/Data_done" \
/Applications/Stata/StataMP.app/Contents/MacOS/stata-mp -b do Data_done/02_do/00_master.do
```

Run the independent Python checks and publication figures:

```bash
python3 Data_done/02_do/05_publication_outputs.py
```

Compile the English and Chinese LaTeX papers from `Data_done/05_latex` with a full TeX distribution:

```bash
cd Data_done/05_latex
pdflatex education_income_en.tex
bibtex education_income_en
pdflatex education_income_en.tex
pdflatex education_income_en.tex

xelatex education_income_zh.tex
bibtex education_income_zh
xelatex education_income_zh.tex
xelatex education_income_zh.tex
```

On this machine, Stata MP was available and the Stata workflow was rerun successfully on 2026-05-31. A LaTeX engine was not available in `PATH`, so the `.tex` sources were generated but not compiled locally.
