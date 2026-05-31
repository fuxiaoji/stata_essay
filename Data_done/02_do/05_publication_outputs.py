from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "01_data" / "analysis.csv"
OUT = ROOT / "05_latex"
FIG = OUT / "figures"
TAB = OUT / "tables"


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


def regression_outputs(df: pd.DataFrame) -> dict[str, object]:
    df = df.copy()
    df["lninc1"] = np.where(df["inc1"].ge(0) & df["inc1"].notna(), np.log(df["inc1"] + 1), np.nan)

    formulas = {
        "M1": "lnwage ~ educ",
        "M2": "lnwage ~ educ + age_ + age2 + gen + mar + rural + medsure_dum",
        "M3": "lnwage ~ educ + age_ + age2 + gen + mar + rural + medsure_dum + C(provcd)",
        "Alt. income": "lninc1 ~ educ + age_ + age2 + gen + mar + rural + medsure_dum + C(provcd)",
        "Positive wage": "lnwage ~ educ + age_ + age2 + gen + mar + rural + medsure_dum + C(provcd)",
    }
    data_for_model = {
        "M1": df,
        "M2": df,
        "M3": df,
        "Alt. income": df.dropna(subset=["lninc1"]),
        "Positive wage": df[df["wage"] > 0],
    }

    results = {name: fit_model(data_for_model[name], formula) for name, formula in formulas.items()}

    reg_rows: list[list[object]] = []
    coef_rows: list[dict[str, float | str]] = []
    for name, res in results.items():
        beta = float(res.params["educ"])
        se = float(res.bse["educ"])
        pvalue = float(res.pvalues["educ"])
        reg_rows.append(
            [
                name,
                f"{beta:.4f}{pstars(pvalue)}",
                f"({se:.4f})",
                f"{int(res.nobs):,}",
                f"{res.rsquared:.3f}",
            ]
        )
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

    write_tex_table(
        TAB / "table_regression_education_returns.tex",
        ["Model", "Education coefficient", "Robust SE", "N", "$R^2$"],
        reg_rows,
        align="lrrrr",
    )

    pd.DataFrame(coef_rows).to_csv(TAB / "model_coefficients.csv", index=False)
    return {"models": results, "coef_rows": coef_rows}


def summary_outputs(df: pd.DataFrame) -> dict[str, object]:
    desc_vars = [
        ("wage", "Annual wage income"),
        ("lnwage", "ln(wage + 1)"),
        ("educ", "Years of education"),
        ("age_", "Age"),
        ("gen", "Male"),
        ("rural", "Rural hukou"),
    ]
    rows: list[list[object]] = []
    for var, label in desc_vars:
        series = df[var]
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

    edu_counts = (
        df["edu"]
        .value_counts()
        .sort_index()
        .rename_axis("edu")
        .reset_index(name="n")
        .assign(label=lambda x: x["edu"].map(EDU_LABELS), share=lambda x: 100 * x["n"] / len(df))
    )
    edu_rows = [[row.label, f"{int(row.n):,}", f"{row.share:.2f}"] for row in edu_counts.itertuples()]
    write_tex_table(
        TAB / "table_education_distribution.tex",
        ["Education category", "N", "Percent"],
        edu_rows,
        align="lrr",
    )
    edu_counts.to_csv(TAB / "education_distribution.csv", index=False)
    return {"education_counts": edu_counts}


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
    ax.errorbar(
        x,
        grouped["mean_lnwage"],
        yerr=1.96 * grouped["se"],
        fmt="o",
        markersize=8,
        color="#1E6091",
        ecolor="#9B2226",
        elinewidth=1.6,
        capsize=4,
    )
    ax.plot(x, grouped["mean_lnwage"], color="#2A9D8F", linewidth=2.4, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(grouped["label"], rotation=25, ha="right")
    ax.set_ylabel("Mean ln(wage + 1), with 95% CI")
    ax.set_title("Average Wage Income Rises with Education Category")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIG / "viz_wage_by_education.png", bbox_inches="tight")
    plt.close(fig)


def figure_binned_fit(df: pd.DataFrame) -> None:
    grouped = df.groupby("educ").agg(mean_lnwage=("lnwage", "mean"), n=("lnwage", "size")).reset_index()
    slope, intercept = np.polyfit(grouped["educ"], grouped["mean_lnwage"], 1, w=grouped["n"])
    xline = np.linspace(grouped["educ"].min(), grouped["educ"].max(), 100)
    sizes = 42 + 360 * grouped["n"] / grouped["n"].max()
    fig, ax = plt.subplots(figsize=(8.2, 5.3))
    ax.scatter(
        grouped["educ"],
        grouped["mean_lnwage"],
        s=sizes,
        color="#0F766E",
        alpha=0.78,
        edgecolor="white",
        linewidth=0.8,
        label="Education-year mean",
    )
    ax.plot(xline, intercept + slope * xline, color="#B42318", linewidth=2.5, label="Weighted linear fit")
    ax.set_xlabel("Years of education")
    ax.set_ylabel("Mean ln(wage + 1)")
    ax.set_title("Binned Education-Wage Gradient")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(alpha=0.18)
    fig.tight_layout()
    fig.savefig(FIG / "viz_binned_education_wage_fit.png", bbox_inches="tight")
    plt.close(fig)


def figure_coefficients(coef_rows: list[dict[str, float | str]]) -> None:
    data = pd.DataFrame(coef_rows)
    fig, ax = plt.subplots(figsize=(8.3, 4.9))
    y = np.arange(len(data))[::-1]
    colors = ["#264653", "#2A9D8F", "#1E6091", "#E9C46A", "#9B2226"]
    ax.errorbar(
        data["coef"],
        y,
        xerr=[data["coef"] - data["lower"], data["upper"] - data["coef"]],
        fmt="o",
        color="#111827",
        ecolor="#5B677A",
        elinewidth=1.8,
        capsize=4,
    )
    ax.scatter(data["coef"], y, s=95, c=colors[: len(data)], edgecolor="white", linewidth=0.8, zorder=3)
    ax.axvline(0, color="#6B7280", linewidth=1.0, linestyle="--")
    ax.set_yticks(y)
    ax.set_yticklabels(data["model"])
    ax.set_xlabel("Education coefficient, with 95% robust confidence interval")
    ax.set_title("Estimated Education-Income Association Across Specifications")
    ax.grid(axis="x", alpha=0.18)
    fig.tight_layout()
    fig.savefig(FIG / "viz_regression_coefficients.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ensure_dirs()
    configure_plot()
    df = pd.read_csv(DATA)
    summary = summary_outputs(df)
    regressions = regression_outputs(df)
    figure_education_distribution(summary["education_counts"])
    figure_wage_by_education(df)
    figure_binned_fit(df)
    figure_coefficients(regressions["coef_rows"])

    overview = {
        "n": int(len(df)),
        "main_educ_coef": float(regressions["models"]["M3"].params["educ"]),
        "main_educ_se_hc1": float(regressions["models"]["M3"].bse["educ"]),
        "main_r2": float(regressions["models"]["M3"].rsquared),
        "positive_wage_coef": float(regressions["models"]["Positive wage"].params["educ"]),
        "alt_income_coef": float(regressions["models"]["Alt. income"].params["educ"]),
    }
    (OUT / "analysis_summary.json").write_text(json.dumps(overview, indent=2), encoding="utf-8")
    print(json.dumps(overview, indent=2))


if __name__ == "__main__":
    main()
