# CFPS 2022 教育水平与收入项目交付说明

注意：`01_data` 中的 `.dta` 文件是 Stata 二进制数据文件，用记事本打开出现乱码是正常现象，不代表文件损坏。需要查看数据时请用 Stata 打开，或用 `01_data/analysis.csv` 在 Excel / 记事本中预览。

## 一、文件夹结构

### 00_report

- `final_report.docx`：最终中文实证报告。
- `final_report.pdf`：由 Word 导出的 PDF 版本。

### 01_data

- `source.dta`：本项目使用的 CFPS 2022 原始输入数据副本。
- `analysis.dta`：清洗后的分析数据，可直接用于回归和画图。
- `cfps2022_education_income_analysis.dta`：分析数据备份文件。
- `analysis.csv`：`analysis.dta` 的文本版副本，方便用 Excel 或记事本预览。

### 02_do

- `00_master.do`：Stata 主控脚本，依次运行数据整理、基准回归、图表生成和 CSV 导出。
- `01_build_analysis_data.do`：从 `source.dta` 生成分析样本。
- `02_baseline_regression.do`：运行描述统计、基准回归、稳健性检验和敏感性检验。
- `03_make_report_figures.do`：生成报告中的三张图。
- `04_export_analysis_csv.do`：把清洗后的分析数据导出为 `analysis.csv`。
- `build_final_report_docx.py`：重新生成 Word 报告的 Python 脚本。

### 03_logs

- `build_analysis_data.log`：数据整理日志。
- `regression.log`：正式回归日志，包含全部模型输出。
- `report_figures.log`：图表生成日志。
- `export_analysis_csv.log`：CSV 导出日志。
- `batch_*.log`：批处理复现检查留下的运行记录。

### 04_figures

- `fig1_educ_distribution.png`：教育年限分布图。
- `fig2_mean_lnwage_by_edu.png`：不同教育水平的平均收入图。
- `fig3_educ_lnwage_fit.png`：教育年限与收入拟合关系图。

### 05_latex

- `education_income_en.tex`：英文 LaTeX 论文。
- `education_income_zh.tex`：中文 LaTeX 论文。
- `references.bib`：论文引用文献库，保留 DOI 或数据来源链接，避免编造引用。
- `figures/`：Python 生成的论文级可视化图表。
- `tables/`：由分析数据和回归结果导出的 LaTeX 表格。

## 二、如何复现

### 1. 复现数据整理、图表和回归结果

打开 Stata，运行：

```stata
do "02_do/00_master.do"
```

运行后会依次完成：

1. 从 `source.dta` 生成 `analysis.dta`。
2. 运行描述统计、基准回归和稳健性检验。
3. 生成报告所需三张图。
4. 导出 `analysis.csv`。
5. 生成对应日志文件。

如果 `Data_done` 文件夹被移动到其他位置，需要先打开 `02_do/00_master.do`，把：

```bash
DATA_DONE_ROOT="新的/Data_done/绝对路径" stata-mp -b do 02_do/00_master.do
```

或在 do 文件中修改 fallback 路径。

本机已于 2026-05-31 使用 Stata MP 重新运行主控脚本，`03_logs` 中的日志已经更新。

### 2. 复现论文级图表和 LaTeX 表格

在项目根目录运行：

```bash
python3 Data_done/02_do/05_publication_outputs.py
```

运行后会生成：

- `05_latex/figures/viz_*.png`
- `05_latex/tables/table_*.tex`
- `05_latex/analysis_summary.json`

### 3. 复现最终报告

最终报告材料包括：

- `00_report/final_report.docx`
- `00_report/final_report.pdf`
- `04_figures` 中的三张 PNG 图
- `03_logs/regression.log`
- `02_do/build_final_report_docx.py`

如需重新生成 Word 报告，可运行：

```bash
python 02_do/build_final_report_docx.py
```

PDF 可由更新后的 Word 文档另存为 PDF。

### 4. 编译英中文 LaTeX 论文

若系统安装了完整 TeX 发行版，可运行：

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

当前机器的命令行 `PATH` 中未发现 LaTeX 编译器，因此本次交付生成 `.tex` 源文件，但未在本机编译 PDF。

## 三、核心结论

主模型控制年龄、年龄平方、性别、婚姻、城乡户口、医保和省份固定效应。结果显示，教育年限系数为 `0.0882`，且在 1% 水平显著。这表示在控制其他变量后，受教育年限每增加 1 年，`ln(wage + 1)` 平均增加约 `0.0882` 个对数点，近似对应工资收入提高 `8.8%`。

加入省份固定效应后，模型能够控制不同省份之间相对稳定的地区发展水平、劳动力市场结构、工资水平和公共资源差异，从而减少地区层面差异对教育收入关系估计的干扰。

稳健性检验从教育变量定义、收入变量定义和样本筛选口径三个角度展开。使用教育分类变量替代教育年限、使用 `lninc1 = ln(inc1 + 1)` 替代 `lnwage`、以及仅保留正工资样本后，教育变量系数均保持显著为正，说明基准结论较为稳健。

由于本文使用横截面数据和常规 OLS 回归，结果应理解为教育水平与收入之间的条件相关关系，不能直接解释为严格因果效应。

## 四、文件完整性说明

本项目提交包中应包含完整的报告文件、数据文件、Stata do 文件、日志文件和图表文件。若仅检查数据整理和回归结果，可重点查看 `01_data/analysis.dta`、`02_do/00_master.do` 和 `03_logs/regression.log`。
