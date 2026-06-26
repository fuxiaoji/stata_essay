from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyreadstat
import statsmodels.formula.api as smf
from linearmodels.iv import IV2SLS
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DTA = ROOT / "01_data" / "source.dta"
OUT = ROOT / "05_latex"
FIG = OUT / "figures"
TAB = OUT / "tables"
SUMMARY_PATH = OUT / "analysis_summary.json"


EDU_LABELS = {
    0: "Illiterate",
    1: "Primary",
    2: "Junior high",
    3: "High school",
    4: "College",
    5: "Bachelor",
    6: "Master",
    7: "Doctorate",
}

EDU_LABELS_ZH = {
    0: "文盲",
    1: "小学",
    2: "初中",
    3: "高中",
    4: "大专",
    5: "本科",
    6: "硕士",
    7: "博士",
}

DESC_LABELS_ZH = {
    "Annual wage income": "年度工资收入",
    "ln(wage + 1)": "ln(工资 + 1)",
    "Years of education": "受教育年限",
    "College or above": "大专及以上",
    "Birth year": "出生年份",
    "Age": "年龄",
    "Male": "男性",
    "Rural hukou": "农业户口",
    "Urban residence": "城镇居住",
    "Internet use": "是否上网",
    "Self-rated health": "自评健康",
}

MODEL_LABELS_ZH = {
    "Years, basic controls": "年限: 基础控制",
    "Years, rich controls": "年限: 扩展控制",
    "College, basic controls": "大专: 基础控制",
    "College, rich controls": "大专: 扩展控制",
    "Winsorized wage": "工资缩尾",
    "Positive wage only": "正工资样本",
}

GROUP_LABELS_ZH = {
    "Women": "女性",
    "Men": "男性",
    "Non-rural hukou": "非农业户口",
    "Rural hukou": "农业户口",
}


@dataclass(frozen=True)
class AIPWResult:
    spec: str
    learner: str
    n: int
    treated_share: float
    ate: float
    se: float
    ci_low: float
    ci_high: float
    auc: float
    p01: float
    p05: float
    p50: float
    p95: float
    p99: float


def ensure_dirs() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)


def pstars(pvalue: float) -> str:
    if pvalue < 0.01:
        return "***"
    if pvalue < 0.05:
        return "**"
    if pvalue < 0.10:
        return "*"
    return ""


def tex_escape(value: object) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def write_tex_table(path: Path, headers: list[str], rows: list[list[object]], align: str | None = None) -> None:
    align = align or ("l" + "r" * (len(headers) - 1))
    lines = [
        rf"\begin{{tabular}}{{{align}}}",
        r"\toprule",
        " & ".join(headers) + r" \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(tex_escape(v) for v in row) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def fit_model(df: pd.DataFrame, formula: str):
    return smf.ols(formula, data=df).fit(cov_type="HC1")


def load_and_prepare() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    source, _ = pyreadstat.read_dta(SOURCE_DTA)
    df = source.copy()
    source_n = len(df)

    df["year"] = df["year"].fillna(2022)
    df["birth_year"] = 2022 - df["age_"]
    df["age2"] = df["age_"] ** 2
    df["lnwage"] = np.where(df["wage"].ge(0) & df["wage"].notna(), np.log(df["wage"] + 1), np.nan)
    df["college"] = np.where(df["educ"].notna(), (df["educ"] >= 15).astype(int), np.nan)
    df["lninc1"] = np.where(df["inc1"].ge(0) & df["inc1"].notna(), np.log(df["inc1"] + 1), np.nan)
    df["running"] = df["birth_year"] - 1981
    df["post1981"] = (df["birth_year"] >= 1981).astype(int)

    lo, hi = df.loc[df["wage"].notna(), "wage"].quantile([0.01, 0.99])
    df["wage_w"] = df["wage"].clip(lo, hi)
    df["lnwage_w"] = np.where(df["wage_w"].ge(0) & df["wage_w"].notna(), np.log(df["wage_w"] + 1), np.nan)

    core = ["lnwage", "educ", "college", "age_", "age2", "gen", "mar", "rural", "provcd"]
    analytic = df[df["age_"].between(18, 64)].copy()
    after_age = len(analytic)
    analytic = analytic[analytic["wage"].notna()].copy()
    after_wage = len(analytic)
    analytic = analytic.dropna(subset=core).copy()
    final_n = len(analytic)

    # Keep rich controls as nullable; tables and ML pipelines handle imputation.
    keep = [
        "pid",
        "year",
        "provcd",
        "countyid",
        "cid",
        "age_",
        "age2",
        "birth_year",
        "running",
        "post1981",
        "gen",
        "mar",
        "rural",
        "urban",
        "hukou",
        "edu",
        "educ",
        "college",
        "wage",
        "wage_w",
        "lnwage",
        "lnwage_w",
        "inc1",
        "lninc1",
        "job",
        "health",
        "size",
        "dw",
        "inter",
        "asset",
        "fin",
        "esta",
    ]
    analytic = analytic[[c for c in keep if c in analytic.columns]]

    audit = {
        "source_n": int(source_n),
        "after_age_18_64": int(after_age),
        "after_nonmissing_wage": int(after_wage),
        "final_core_complete": int(final_n),
        "wage_p01": float(lo),
        "wage_p99": float(hi),
    }
    return source, analytic, audit


def sample_audit_outputs(source: pd.DataFrame, df: pd.DataFrame, audit: dict[str, object]) -> None:
    flow_rows = [
        ["Raw CFPS 2022 data file", f"{audit['source_n']:,}", ""],
        ["Keep adults aged 18--64", f"{audit['after_age_18_64']:,}", "Age restriction"],
        ["Require wage variable observed", f"{audit['after_nonmissing_wage']:,}", "Outcome available"],
        ["Require core variables complete", f"{audit['final_core_complete']:,}", "Final analytic sample"],
    ]
    write_tex_table(TAB / "table_sample_flow.tex", ["Step", "N", "Rule"], flow_rows, align="lrl")
    write_tex_table(
        TAB / "table_sample_flow_zh.tex",
        ["步骤", "样本量", "规则"],
        [
            ["CFPS 2022 原始数据", f"{audit['source_n']:,}", ""],
            ["保留 18--64 岁成年人", f"{audit['after_age_18_64']:,}", "年龄限制"],
            ["要求工资变量非缺失", f"{audit['after_nonmissing_wage']:,}", "因变量可得"],
            ["要求核心变量完整", f"{audit['final_core_complete']:,}", "最终分析样本"],
        ],
        align="lrl",
    )

    miss_vars = ["wage", "educ", "age_", "gen", "mar", "rural", "urban", "health", "inter", "dw", "asset"]
    miss_rows = []
    for var in miss_vars:
        miss = int(source[var].isna().sum())
        miss_rows.append([var, f"{miss:,}", f"{100 * miss / len(source):.2f}"])
    write_tex_table(TAB / "table_missing_audit.tex", ["Variable", "Missing N", "Missing percent"], miss_rows, align="lrr")
    write_tex_table(
        TAB / "table_missing_audit_zh.tex",
        ["变量", "缺失样本量", "缺失比例"],
        miss_rows,
        align="lrr",
    )

    support = (
        df[df["running"].between(-10, 10)]
        .groupby("birth_year")
        .agg(n=("pid", "size"), college_share=("college", "mean"), mean_educ=("educ", "mean"))
        .reset_index()
    )
    support.to_csv(TAB / "cohort_support.csv", index=False)


def summary_outputs(df: pd.DataFrame) -> dict[str, object]:
    desc_vars = [
        ("wage", "Annual wage income"),
        ("lnwage", "ln(wage + 1)"),
        ("educ", "Years of education"),
        ("college", "College or above"),
        ("birth_year", "Birth year"),
        ("age_", "Age"),
        ("gen", "Male"),
        ("rural", "Rural hukou"),
        ("urban", "Urban residence"),
        ("inter", "Internet use"),
        ("health", "Self-rated health"),
    ]
    rows: list[list[object]] = []
    for var, label in desc_vars:
        series = pd.to_numeric(df[var], errors="coerce")
        rows.append(
            [
                label,
                f"{series.count():,}",
                f"{series.mean():.3f}",
                f"{series.std():.3f}",
                f"{series.min():.3f}",
                f"{series.quantile(0.5):.3f}",
                f"{series.max():.3f}",
            ]
        )
    write_tex_table(
        TAB / "table_descriptive_statistics.tex",
        ["Variable", "N", "Mean", "SD", "Min", "Median", "Max"],
        rows,
        align="lrrrrrr",
    )
    write_tex_table(
        TAB / "table_descriptive_statistics_zh.tex",
        ["变量", "样本量", "均值", "标准差", "最小值", "中位数", "最大值"],
        [[DESC_LABELS_ZH[row[0]], *row[1:]] for row in rows],
        align="lrrrrrr",
    )

    edu_counts = (
        df["edu"]
        .value_counts()
        .sort_index()
        .rename_axis("edu")
        .reset_index(name="n")
        .assign(label=lambda x: x["edu"].map(EDU_LABELS), share=lambda x: 100 * x["n"] / len(df))
    )
    edu_rows = [[row.label, f"{int(row.n):,}", f"{row.share:.2f}"] for row in edu_counts.itertuples()]
    write_tex_table(TAB / "table_education_distribution.tex", ["Education category", "N", "Percent"], edu_rows, "lrr")
    edu_rows_zh = [[EDU_LABELS_ZH[int(row.edu)], f"{int(row.n):,}", f"{row.share:.2f}"] for row in edu_counts.itertuples()]
    write_tex_table(TAB / "table_education_distribution_zh.tex", ["教育类别", "样本量", "占比(\\%)"], edu_rows_zh, "lrr")
    edu_counts.to_csv(TAB / "education_distribution.csv", index=False)
    return {"education_counts": edu_counts}


def education_slope_outputs(df: pd.DataFrame) -> pd.DataFrame:
    slopes = (
        df.groupby("edu")
        .agg(
            n=("pid", "size"),
            mean_educ=("educ", "mean"),
            mean_lnwage=("lnwage", "mean"),
        )
        .reset_index()
        .sort_values("edu")
    )
    slopes["label"] = slopes["edu"].map(EDU_LABELS)
    slopes["label_zh"] = slopes["edu"].map(EDU_LABELS_ZH)
    slopes["delta_lnwage"] = slopes["mean_lnwage"].diff()
    slopes["delta_educ"] = slopes["mean_educ"].diff()
    slopes["adjacent_slope"] = slopes["delta_lnwage"] / slopes["delta_educ"]
    slopes["exact_change_pct"] = 100 * (np.exp(slopes["adjacent_slope"]) - 1)

    rows = []
    rows_zh = []
    for row in slopes.itertuples():
        slope = "--" if pd.isna(row.adjacent_slope) else f"{row.adjacent_slope:.4f}"
        exact = "--" if pd.isna(row.exact_change_pct) else f"{row.exact_change_pct:.2f}"
        rows.append([row.label, f"{int(row.n):,}", f"{row.mean_educ:.2f}", f"{row.mean_lnwage:.3f}", slope, exact])
        rows_zh.append([row.label_zh, f"{int(row.n):,}", f"{row.mean_educ:.2f}", f"{row.mean_lnwage:.3f}", slope, exact])

    write_tex_table(
        TAB / "table_education_slopes.tex",
        ["Education level", "N", "Mean years", "Mean ln(wage+1)", "Adjacent slope", "Exact change (\\%)"],
        rows,
        "lrrrrr",
    )
    write_tex_table(
        TAB / "table_education_slopes_zh.tex",
        ["教育层级", "样本量", "平均年限", "平均ln(工资+1)", "相邻斜率", "精确变化(\\%)"],
        rows_zh,
        "lrrrrr",
    )
    slopes.to_csv(TAB / "education_adjacent_slopes.csv", index=False)
    return slopes


def employment_scope_outputs(df: pd.DataFrame) -> pd.DataFrame:
    labels = {0: "job = 0", 1: "job = 1"}
    labels_zh = {0: "job = 0", 1: "job = 1"}
    work = df.dropna(subset=["job"]).copy()
    grouped = (
        work.groupby("job")
        .agg(n=("pid", "size"), mean_wage=("wage", "mean"), mean_lnwage=("lnwage", "mean"))
        .reset_index()
        .sort_values("job")
    )
    grouped["share"] = 100 * grouped["n"] / len(work)
    rows = [
        [labels.get(int(row.job), str(row.job)), f"{int(row.n):,}", f"{row.share:.2f}", f"{row.mean_wage:.2f}", f"{row.mean_lnwage:.3f}"]
        for row in grouped.itertuples()
    ]
    rows_zh = [
        [labels_zh.get(int(row.job), str(row.job)), f"{int(row.n):,}", f"{row.share:.2f}", f"{row.mean_wage:.2f}", f"{row.mean_lnwage:.3f}"]
        for row in grouped.itertuples()
    ]
    write_tex_table(TAB / "table_employment_scope.tex", ["Status", "N", "Percent", "Mean wage", "Mean ln(wage+1)"], rows, "lrrrr")
    write_tex_table(TAB / "table_employment_scope_zh.tex", ["状态", "样本量", "占比(\\%)", "平均工资", "平均ln(工资+1)"], rows_zh, "lrrrr")
    grouped.to_csv(TAB / "employment_scope.csv", index=False)
    return grouped


def regression_outputs(df: pd.DataFrame) -> dict[str, object]:
    basic = "age_ + age2 + gen + mar + rural + C(provcd)"
    rich = "age_ + age2 + gen + mar + rural + urban + health + size + inter + dw + C(provcd)"
    formulas = {
        "Years, basic controls": f"lnwage ~ educ + {basic}",
        "Years, rich controls": f"lnwage ~ educ + {rich}",
        "College, basic controls": f"lnwage ~ college + {basic}",
        "College, rich controls": f"lnwage ~ college + {rich}",
        "Winsorized wage": f"lnwage_w ~ college + {basic}",
        "Positive wage only": f"lnwage ~ college + {basic}",
    }
    data_for_model = {
        name: df.dropna(subset=["lnwage", "lnwage_w", "college", "educ", "age_", "age2", "gen", "mar", "rural", "provcd"])
        for name in formulas
    }
    data_for_model["Positive wage only"] = data_for_model["Positive wage only"].query("wage > 0")

    rows: list[list[object]] = []
    rows_zh: list[list[object]] = []
    coef_rows: list[dict[str, float | str]] = []
    results = {}
    for name, formula in formulas.items():
        res = fit_model(data_for_model[name], formula)
        results[name] = res
        key = "educ" if name.startswith("Years") else "college"
        beta = float(res.params[key])
        se = float(res.bse[key])
        pvalue = float(res.pvalues[key])
        rows.append([name, f"{beta:.4f}{pstars(pvalue)}", f"({se:.4f})", f"{int(res.nobs):,}", f"{res.rsquared:.3f}"])
        rows_zh.append([MODEL_LABELS_ZH[name], f"{beta:.4f}{pstars(pvalue)}", f"({se:.4f})", f"{int(res.nobs):,}", f"{res.rsquared:.3f}"])
        coef_rows.append(
            {
                "model": name,
                "coef": beta,
                "se": se,
                "lower": beta - 1.96 * se,
                "upper": beta + 1.96 * se,
                "pvalue": pvalue,
                "nobs": float(res.nobs),
                "rsq": float(res.rsquared),
            }
        )

    write_tex_table(TAB / "table_regression_education_returns.tex", ["Specification", "Coefficient", "Robust SE", "N", "$R^2$"], rows, "lrrrr")
    write_tex_table(TAB / "table_regression_education_returns_zh.tex", ["估计设定", "系数", "稳健标准误", "样本量", "$R^2$"], rows_zh, "lrrrr")
    pd.DataFrame(coef_rows).to_csv(TAB / "model_coefficients.csv", index=False)
    return {"models": results, "coef_rows": coef_rows}


def prepare_ml_matrix(df: pd.DataFrame, covariates: list[str]) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    d = df[["lnwage", "college"] + covariates].copy()
    d = d.dropna(subset=["lnwage", "college", "age_", "gen", "rural", "provcd"])
    for col in covariates:
        if col == "provcd":
            d[col] = d[col].fillna(d[col].mode().iloc[0]).astype(int).astype(str)
        else:
            values = pd.to_numeric(d[col], errors="coerce")
            d[col] = values.fillna(values.median())
    x = pd.get_dummies(d[covariates], columns=["provcd"], drop_first=False, dtype=float)
    t = d["college"].astype(int).to_numpy()
    y = d["lnwage"].to_numpy()
    return x, t, y


def aipw_crossfit(df: pd.DataFrame, spec: str, covariates: list[str], learner: str) -> tuple[AIPWResult, pd.DataFrame]:
    x, t, y = prepare_ml_matrix(df, covariates)
    n = len(x)
    ehat = np.zeros(n)
    m0 = np.zeros(n)
    m1 = np.zeros(n)
    kfold = KFold(n_splits=5, shuffle=True, random_state=42)

    for train, test in kfold.split(x):
        if learner == "Linear":
            clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.5))
            reg0 = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
            reg1 = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        else:
            clf = GradientBoostingClassifier(random_state=42)
            reg0 = GradientBoostingRegressor(random_state=42)
            reg1 = GradientBoostingRegressor(random_state=42)

        clf.fit(x.iloc[train], t[train])
        ehat[test] = clf.predict_proba(x.iloc[test])[:, 1]
        reg0.fit(x.iloc[train][t[train] == 0], y[train][t[train] == 0])
        reg1.fit(x.iloc[train][t[train] == 1], y[train][t[train] == 1])
        m0[test] = reg0.predict(x.iloc[test])
        m1[test] = reg1.predict(x.iloc[test])

    clipped = np.clip(ehat, 0.02, 0.98)
    scores = (m1 - m0) + t * (y - m1) / clipped - (1 - t) * (y - m0) / (1 - clipped)
    ate = float(scores.mean())
    se = float(scores.std(ddof=1) / np.sqrt(n))
    qs = np.quantile(ehat, [0.01, 0.05, 0.50, 0.95, 0.99])
    result = AIPWResult(
        spec=spec,
        learner=learner,
        n=n,
        treated_share=float(t.mean()),
        ate=ate,
        se=se,
        ci_low=ate - 1.96 * se,
        ci_high=ate + 1.96 * se,
        auc=float(roc_auc_score(t, ehat)),
        p01=float(qs[0]),
        p05=float(qs[1]),
        p50=float(qs[2]),
        p95=float(qs[3]),
        p99=float(qs[4]),
    )
    diagnostics = x.copy()
    diagnostics["college"] = t
    diagnostics["lnwage"] = y
    diagnostics["propensity"] = ehat
    diagnostics["weight"] = np.where(t == 1, 1 / clipped, 1 / (1 - clipped))
    return result, diagnostics


def standardized_mean_difference(values: np.ndarray, treatment: np.ndarray, weights: np.ndarray | None = None) -> float:
    mask = ~np.isnan(values)
    values = values[mask]
    treatment = treatment[mask]
    if weights is None:
        weights = np.ones_like(values, dtype=float)
    else:
        weights = weights[mask]
    mt = np.average(values[treatment == 1], weights=weights[treatment == 1])
    mc = np.average(values[treatment == 0], weights=weights[treatment == 0])
    vt = np.average((values[treatment == 1] - mt) ** 2, weights=weights[treatment == 1])
    vc = np.average((values[treatment == 0] - mc) ** 2, weights=weights[treatment == 0])
    denom = np.sqrt((vt + vc) / 2)
    return float((mt - mc) / denom) if denom > 0 else 0.0


def causal_outputs(df: pd.DataFrame) -> dict[str, object]:
    specs = {
        "Core": ["age_", "gen", "rural", "provcd", "urban"],
        "Core plus": ["age_", "gen", "rural", "provcd", "urban", "mar"],
        "Extended": ["age_", "gen", "rural", "provcd", "urban", "mar", "health", "size", "dw", "inter", "job"],
    }
    results: list[AIPWResult] = []
    main_diag: pd.DataFrame | None = None
    for spec, covariates in specs.items():
        for learner in ["Linear", "GBM"]:
            result, diag = aipw_crossfit(df, spec, covariates, learner)
            results.append(result)
            if spec == "Core plus" and learner == "GBM":
                main_diag = diag

    rows = [
        [
            r.spec,
            r.learner,
            f"{r.ate:.4f}***",
            f"({r.se:.4f})",
            f"[{r.ci_low:.4f}, {r.ci_high:.4f}]",
            f"{r.n:,}",
            f"{r.auc:.3f}",
        ]
        for r in results
    ]
    write_tex_table(TAB / "table_aipw_effects.tex", ["Covariates", "Learner", "ATE", "SE", "95\\% CI", "N", "AUC"], rows, "llrrlrr")
    write_tex_table(TAB / "table_aipw_effects_zh.tex", ["协变量", "学习器", "ATE", "标准误", "95\\% CI", "样本量", "AUC"], rows, "llrrlrr")
    pd.DataFrame([r.__dict__ for r in results]).to_csv(TAB / "aipw_effects.csv", index=False)

    assert main_diag is not None
    t = main_diag["college"].to_numpy()
    weights = main_diag["weight"].to_numpy()
    balance_vars = ["age_", "gen", "rural", "urban", "mar"]
    bal_rows = []
    for var in balance_vars:
        values = main_diag[var].to_numpy(dtype=float)
        raw = standardized_mean_difference(values, t)
        weighted = standardized_mean_difference(values, t, weights)
        bal_rows.append([var, f"{raw:.3f}", f"{weighted:.3f}"])
    write_tex_table(TAB / "table_balance.tex", ["Covariate", "Raw SMD", "Weighted SMD"], bal_rows, "lrr")
    write_tex_table(TAB / "table_balance_zh.tex", ["协变量", "原始 SMD", "加权 SMD"], bal_rows, "lrr")
    pd.DataFrame(bal_rows, columns=["covariate", "raw_smd", "weighted_smd"]).to_csv(TAB / "balance_diagnostics.csv", index=False)
    main_diag[["college", "lnwage", "propensity", "weight"]].to_csv(TAB / "propensity_diagnostics.csv", index=False)
    return {"aipw": results, "main_diag": main_diag}


def iv_diagnostics(df: pd.DataFrame) -> list[dict[str, object]]:
    controls = "gen + mar + rural + C(provcd)"
    rows: list[list[object]] = []
    rows_zh: list[list[object]] = []
    out: list[dict[str, object]] = []
    for bw in [5, 7, 9, 12, 15, 20]:
        d = df.dropna(subset=["lnwage", "educ", "college", "running", "post1981", "gen", "mar", "rural", "provcd"]).copy()
        d = d[d["running"].abs() <= bw]
        fs = smf.ols(f"educ ~ post1981 + running + post1981:running + {controls}", d).fit(cov_type="HC1")
        fstat = float(fs.tvalues["post1981"] ** 2)
        try:
            iv = IV2SLS.from_formula(
                "lnwage ~ 1 + running + post1981:running + gen + mar + rural + C(provcd) + [educ ~ post1981]",
                d,
            ).fit(cov_type="robust")
            iv_beta = float(iv.params["educ"])
            iv_se = float(iv.std_errors["educ"])
            iv_p = float(iv.pvalues["educ"])
            iv_cell = f"{iv_beta:.4f}{pstars(iv_p)}"
            se_cell = f"({iv_se:.4f})"
        except Exception:
            iv_beta = np.nan
            iv_se = np.nan
            fstat = np.nan
            iv_cell = "--"
            se_cell = "--"
        first = float(fs.params["post1981"])
        rows.append([f"+/-{bw}", f"{len(d):,}", f"{first:.4f}", f"{fstat:.2f}", iv_cell, se_cell])
        rows_zh.append([f"+/-{bw}", f"{len(d):,}", f"{first:.4f}", f"{fstat:.2f}", iv_cell, se_cell])
        out.append({"bandwidth": bw, "n": int(len(d)), "first_stage": first, "first_stage_f": fstat, "iv_beta": iv_beta, "iv_se": iv_se})

    write_tex_table(TAB / "table_iv_diagnostics.tex", ["Window", "N", "First stage", "F-stat", "IV estimate", "SE"], rows, "lrrrrr")
    write_tex_table(TAB / "table_iv_diagnostics_zh.tex", ["窗口", "样本量", "第一阶段", "F 统计量", "IV 估计", "标准误"], rows_zh, "lrrrrr")
    pd.DataFrame(out).to_csv(TAB / "iv_diagnostics.csv", index=False)
    return out


def heterogeneity_outputs(df: pd.DataFrame) -> list[dict[str, float | str]]:
    groups = [
        ("Women", df[df["gen"] == 0]),
        ("Men", df[df["gen"] == 1]),
        ("Non-rural hukou", df[df["rural"] == 0]),
        ("Rural hukou", df[df["rural"] == 1]),
    ]
    rows: list[list[object]] = []
    coef_rows: list[dict[str, float | str]] = []
    formula = "lnwage ~ educ + age_ + age2 + mar + C(provcd)"
    for label, subdf in groups:
        res = fit_model(subdf, formula)
        beta = float(res.params["educ"])
        se = float(res.bse["educ"])
        pvalue = float(res.pvalues["educ"])
        rows.append([label, f"{beta:.4f}{pstars(pvalue)}", f"({se:.4f})", f"{int(res.nobs):,}", f"{res.rsquared:.3f}"])
        coef_rows.append(
            {
                "group": label,
                "coef": beta,
                "se": se,
                "lower": beta - 1.96 * se,
                "upper": beta + 1.96 * se,
                "pvalue": pvalue,
                "nobs": float(res.nobs),
                "rsq": float(res.rsquared),
            }
        )
    write_tex_table(TAB / "table_heterogeneity_returns.tex", ["Subsample", "Education coefficient", "Robust SE", "N", "$R^2$"], rows, "lrrrr")
    write_tex_table(
        TAB / "table_heterogeneity_returns_zh.tex",
        ["子样本", "教育系数", "稳健标准误", "样本量", "$R^2$"],
        [[GROUP_LABELS_ZH[row[0]], *row[1:]] for row in rows],
        "lrrrr",
    )
    pd.DataFrame(coef_rows).to_csv(TAB / "heterogeneity_coefficients.csv", index=False)
    return coef_rows


def configure_plot() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 160,
            "savefig.dpi": 320,
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#273241",
            "axes.edgecolor": "#9AA6B2",
            "xtick.color": "#354150",
            "ytick.color": "#354150",
            "text.color": "#1F2937",
            "axes.titleweight": "bold",
        }
    )


def figure_education_distribution(edu_counts: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    colors = plt.cm.viridis(np.linspace(0.18, 0.82, len(edu_counts)))
    ax.barh(edu_counts["label"], edu_counts["share"], color=colors, edgecolor="white", linewidth=0.8)
    for idx, row in edu_counts.reset_index(drop=True).iterrows():
        ax.text(row["share"] + 0.35, idx, f"{row['share']:.1f}%  (n={int(row['n']):,})", va="center", fontsize=9)
    ax.set_xlabel("Share of analytic sample (%)")
    ax.set_ylabel("")
    ax.set_title("Education Composition of the CFPS 2022 Analytic Sample")
    ax.set_xlim(0, max(edu_counts["share"]) + 6)
    ax.grid(axis="x", alpha=0.18)
    fig.tight_layout()
    fig.savefig(FIG / "viz_education_distribution.png", bbox_inches="tight")
    plt.close(fig)


def figure_wage_by_education(df: pd.DataFrame) -> None:
    grouped = (
        df.groupby("edu")
        .agg(mean_lnwage=("lnwage", "mean"), sd=("lnwage", "std"), n=("lnwage", "size"))
        .reset_index()
        .assign(label=lambda x: x["edu"].map(EDU_LABELS), se=lambda x: x["sd"] / np.sqrt(x["n"]))
    )
    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    x = np.arange(len(grouped))
    ax.errorbar(x, grouped["mean_lnwage"], yerr=1.96 * grouped["se"], fmt="o", markersize=8, color="#1E6091", ecolor="#9B2226", elinewidth=1.6, capsize=4)
    ax.plot(x, grouped["mean_lnwage"], color="#2A9D8F", linewidth=2.4, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(grouped["label"], rotation=25, ha="right")
    ax.set_ylabel("Mean ln(wage + 1), with 95% CI")
    ax.set_title("Average Wage Income Rises with Education Category")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIG / "viz_wage_by_education.png", bbox_inches="tight")
    plt.close(fig)


def figure_education_slopes(slopes: pd.DataFrame) -> None:
    data = slopes.dropna(subset=["adjacent_slope"]).copy()
    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    x = np.arange(len(data))
    ax.plot(x, data["adjacent_slope"], marker="o", markersize=8, linewidth=2.3, color="#1E6091")
    ax.axhline(0, color="#6B7280", linewidth=1.0, linestyle="--")
    for idx, row in enumerate(data.itertuples()):
        ax.annotate(
            f"{row.adjacent_slope:.3f}",
            (idx, row.adjacent_slope),
            textcoords="offset points",
            xytext=(0, 9 if row.adjacent_slope >= 0 else -16),
            ha="center",
            fontsize=9,
            color="#111827",
        )
    ax.set_xticks(x)
    ax.set_xticklabels(data["label"], rotation=25, ha="right")
    ax.set_ylabel("Adjacent slope in mean ln(wage + 1)")
    ax.set_title("Adjacent Income Slope by Education Level")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIG / "viz_education_adjacent_slopes.png", bbox_inches="tight")
    plt.close(fig)


def figure_coefficients(coef_rows: list[dict[str, float | str]]) -> None:
    data = pd.DataFrame(coef_rows)
    fig, ax = plt.subplots(figsize=(8.5, 5.3))
    y = np.arange(len(data))[::-1]
    ax.errorbar(data["coef"], y, xerr=[data["coef"] - data["lower"], data["upper"] - data["coef"]], fmt="o", color="#111827", ecolor="#5B677A", elinewidth=1.8, capsize=4)
    ax.scatter(data["coef"], y, s=95, c=plt.cm.Set2(np.linspace(0, 1, len(data))), edgecolor="white", linewidth=0.8, zorder=3)
    ax.axvline(0, color="#6B7280", linewidth=1.0, linestyle="--")
    ax.set_yticks(y)
    ax.set_yticklabels(data["model"])
    ax.set_xlabel("Coefficient, with 95% robust confidence interval")
    ax.set_title("Regression Estimates Across Specifications")
    ax.grid(axis="x", alpha=0.18)
    fig.tight_layout()
    fig.savefig(FIG / "viz_regression_coefficients.png", bbox_inches="tight")
    plt.close(fig)


def figure_heterogeneity(coef_rows: list[dict[str, float | str]]) -> None:
    data = pd.DataFrame(coef_rows)
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    y = np.arange(len(data))[::-1]
    colors = ["#7A4EAB", "#1E6091", "#E07A5F", "#2A9D8F"]
    ax.errorbar(data["coef"], y, xerr=[data["coef"] - data["lower"], data["upper"] - data["coef"]], fmt="o", color="#111827", ecolor="#5B677A", elinewidth=1.8, capsize=4)
    ax.scatter(data["coef"], y, s=105, c=colors[: len(data)], edgecolor="white", linewidth=0.9, zorder=3)
    ax.axvline(0, color="#6B7280", linewidth=1.0, linestyle="--")
    ax.set_yticks(y)
    ax.set_yticklabels(data["group"])
    ax.set_xlabel("Education coefficient by subsample, with 95% robust confidence interval")
    ax.set_title("Heterogeneous Education-Income Associations")
    ax.grid(axis="x", alpha=0.18)
    fig.tight_layout()
    fig.savefig(FIG / "viz_heterogeneity_coefficients.png", bbox_inches="tight")
    plt.close(fig)


def figure_propensity(main_diag: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    treated = main_diag.query("college == 1")["propensity"]
    control = main_diag.query("college == 0")["propensity"]
    bins = np.linspace(0, 1, 34)
    ax.hist(control, bins=bins, alpha=0.62, label="Below college", color="#1E6091", density=True)
    ax.hist(treated, bins=bins, alpha=0.62, label="College or above", color="#E07A5F", density=True)
    ax.set_xlabel("Estimated propensity score")
    ax.set_ylabel("Density")
    ax.set_title("Overlap in Estimated Propensity Scores")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.18)
    fig.tight_layout()
    fig.savefig(FIG / "viz_propensity_overlap.png", bbox_inches="tight")
    plt.close(fig)


def figure_balance() -> None:
    balance = pd.read_csv(TAB / "balance_diagnostics.csv")
    y = np.arange(len(balance))[::-1]
    fig, ax = plt.subplots(figsize=(7.8, 4.6))
    ax.scatter(balance["raw_smd"].astype(float).abs(), y + 0.12, label="Raw", color="#9B2226", s=80)
    ax.scatter(balance["weighted_smd"].astype(float).abs(), y - 0.12, label="Weighted", color="#2A9D8F", s=80)
    ax.axvline(0.1, color="#6B7280", linestyle="--", linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(balance["covariate"])
    ax.set_xlabel("Absolute standardized mean difference")
    ax.set_title("Covariate Balance Before and After AIPW Weighting")
    ax.legend(frameon=False)
    ax.grid(axis="x", alpha=0.18)
    fig.tight_layout()
    fig.savefig(FIG / "viz_balance_diagnostics.png", bbox_inches="tight")
    plt.close(fig)


def figure_cohort_first_stage(df: pd.DataFrame) -> None:
    cohort = (
        df[df["running"].between(-12, 12)]
        .groupby("birth_year")
        .agg(college_share=("college", "mean"), mean_educ=("educ", "mean"), n=("pid", "size"))
        .reset_index()
    )
    fig, ax1 = plt.subplots(figsize=(8.6, 5.0))
    ax1.plot(cohort["birth_year"], cohort["college_share"], marker="o", color="#1E6091", label="College share")
    ax1.axvline(1981, color="#9B2226", linestyle="--", linewidth=1.4, label="1981 cutoff")
    ax1.set_ylabel("College-or-above share")
    ax1.set_xlabel("Birth year")
    ax1.set_title("Cohort Pattern Around the 1999 Expansion Eligibility Cutoff")
    ax1.grid(alpha=0.18)
    ax2 = ax1.twinx()
    ax2.plot(cohort["birth_year"], cohort["mean_educ"], marker="s", color="#2A9D8F", label="Mean years")
    ax2.set_ylabel("Mean years of education")
    lines = ax1.get_lines() + ax2.get_lines()
    ax1.legend(lines, [line.get_label() for line in lines], frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "viz_cohort_first_stage.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ensure_dirs()
    configure_plot()
    source, df, audit = load_and_prepare()
    sample_audit_outputs(source, df, audit)
    summary = summary_outputs(df)
    slopes = education_slope_outputs(df)
    employment_scope_outputs(df)
    regressions = regression_outputs(df)
    causal = causal_outputs(df)
    iv = iv_diagnostics(df)
    heterogeneity = heterogeneity_outputs(df)

    figure_education_distribution(summary["education_counts"])
    figure_wage_by_education(df)
    figure_education_slopes(slopes)
    figure_coefficients(regressions["coef_rows"])
    figure_heterogeneity(heterogeneity)
    figure_propensity(causal["main_diag"])
    figure_balance()
    figure_cohort_first_stage(df)

    main_aipw = [r for r in causal["aipw"] if r.spec == "Core plus" and r.learner == "GBM"][0]
    overview = {
        **audit,
        "main_educ_coef": float(regressions["models"]["Years, basic controls"].params["educ"]),
        "main_college_ols": float(regressions["models"]["College, basic controls"].params["college"]),
        "main_aipw_college_ate": main_aipw.ate,
        "main_aipw_college_se": main_aipw.se,
        "aipw": [r.__dict__ for r in causal["aipw"]],
        "iv_diagnostics": iv,
        "heterogeneity": heterogeneity,
    }
    SUMMARY_PATH.write_text(json.dumps(overview, indent=2), encoding="utf-8")
    print(json.dumps(overview, indent=2))


if __name__ == "__main__":
    main()
