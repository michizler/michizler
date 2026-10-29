<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="assets/hero-compact-dark.svg">
  <source media="(max-width: 600px)" srcset="assets/hero-compact-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
  <img alt="Bright Uzosike, Data Scientist and ML Engineer. I build ML systems that ship: evaluated, explainable, deployed." src="assets/hero-light.svg" width="100%">
</picture>

I'm a data scientist and ML engineer in Manchester. I take models past the notebook: tested on data they haven't seen, explained prediction by prediction, and served behind typed APIs.

**Now:** Research Data Scientist at Rebel Hive (sole data scientist on a client NLP tool) and AI Data Specialist (RLHF & SFT) at Mercor, reviewing model outputs for frontier training.<br>
**Background:** MSc Data Science with Distinction, University of Salford (2026) · BEng Electronic & Computer Engineering, First Class equivalent.<br>
**Looking for:** graduate and junior data science or ML engineering roles in the UK.

## Featured systems

<p align="center">
  <a href="https://github.com/michizler/alloy-tower-data-platform"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/cards/alloytower-dark.svg"><img alt="AlloyTower AVM: values a property through a live API and explains every estimate with SHAP. 8.5% MAPE with an assessment, 44.9% without (5-fold CV). LightGBM, SHAP, FastAPI, Docker." src="assets/cards/alloytower-light.svg" width="390"></picture></a>
  <picture><source media="(prefers-color-scheme: dark)" srcset="assets/cards/rebelhive-dark.svg"><img alt="Rebel Hive diagnostic, a client NLP tool in use: measures the gap between how colleges describe themselves and how Ofsted describes them. Macro-F1 0.82, 5-fold stratified CV on 24 Ofsted inspection reports. spaCy, scikit-learn, SHAP, Claude API." src="assets/cards/rebelhive-light.svg" width="390"></picture>
  <a href="https://github.com/michizler/data-science-projects/tree/master/llm-feedback-analyzer"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/cards/llm-feedback-dark.svg"><img alt="LLM Feedback Analyzer: turns customer feedback into schema-validated JSON, and falls back safely when the model fails. 13 of 15 correct on a 15-review gold set, for sentiment and for churn risk. Claude Haiku 4.5, Pydantic, Python." src="assets/cards/llm-feedback-light.svg" width="390"></picture></a>
  <a href="https://github.com/michizler/voyage-rails-analytics"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/cards/voyagerail-dark.svg"><img alt="VoyageRail pricing: predicts rail ticket prices from demand, booking time and capacity, served as two containers. R squared 0.97 on holdout with Random Forest, against a 0.77 linear baseline. scikit-learn, MLflow, FastAPI, Docker Compose." src="assets/cards/voyagerail-light.svg" width="390"></picture></a>
</p>

<p align="center"><sub>
  Try AlloyTower live: <a href="https://alloy-avm.streamlit.app/">app</a> · <a href="https://alloytower-avm-api.onrender.com/docs">API docs</a>. The free-tier API can take about 40 seconds to wake.<br>
  Rebel Hive is client work, so its code is private.
</sub></p>

## How I build

- **Evaluate before you trust.** A hand-labelled gold set for the [LLM analyzer](https://github.com/michizler/data-science-projects/tree/master/llm-feedback-analyzer), 5-fold CV for [AlloyTower](https://github.com/michizler/alloy-tower-data-platform), and Ljung-Box residual tests that ruled out two of three [US Bancorp](https://github.com/michizler/usb-stock-timeseries-model) models.
- **Explain every prediction.** Each [AlloyTower](https://github.com/michizler/alloy-tower-data-platform) valuation comes back with the SHAP contributions behind it.
- **Document the limitations.** AlloyTower's [data-quality report](https://github.com/michizler/alloy-tower-data-platform/blob/master/project_brief/AlloyTower_Data_Quality_Findings.pdf) ranks 11 findings by severity, including coordinates that turned out to be random.
- **Ship it.** A [live app](https://alloy-avm.streamlit.app/) and [API](https://alloytower-avm-api.onrender.com/docs) that redeploy on every push, and services that start with one Docker Compose command.

<details>
<summary><b>How AlloyTower fits together</b></summary>
<br>

```mermaid
flowchart LR
  subgraph Training
    T["train_avm.py"] --> ML[("MLflow runs")]
    T --> B[("Model bundles A and B")]
  end
  U(["User"]) --> S["Streamlit app<br/>Streamlit Cloud"]
  S -- "JSON over HTTPS" --> A["FastAPI service<br/>Docker on Render"]
  B --> A
  A --> R{"Assessed value<br/>given?"}
  R -- yes --> MA["Model A<br/>assessment-aware"]
  R -- no --> MB["Model B<br/>fundamentals-only"]
  MA --> X["SHAP TreeExplainer"]
  MB --> X
  X --> O["Estimate, range<br/>and top drivers"]
  A --> C["/comparables<br/>similar properties"]
```

</details>

## Toolkit

| Area | Tools |
| --- | --- |
| **ML & stats** | Python · scikit-learn · LightGBM · SHAP · R (forecast, rugarch) |
| **LLMs & evaluation** | Claude API · Pydantic schemas · retries with backoff · gold-set evaluation |
| **Data & SQL** | pandas · NumPy · SQL Server (T-SQL) · Spark SQL · PySpark · Databricks |
| **Serving & MLOps** | FastAPI · Streamlit · Docker · Docker Compose · MLflow · Render |
| **BI** | Power BI (DAX) · Altair · React + Vite |

## More work

| Project | What it shows | Stack |
| --- | --- | --- |
| [US Bancorp volatility](https://github.com/michizler/usb-stock-timeseries-model) | Holt-Winters and ARIMA failed Ljung-Box. ARIMA(1,0,1) + sGARCH(1,1) passed (p = 0.2369) and gives a 365-day price and volatility forecast from 11,835 daily prices. | R · forecast · rugarch |
| [StrataForge](https://github.com/michizler/strataforge-prediction) | Multiple regression for concrete strength (R² 81.35%, all five assumptions tested), turned into a worked £21,600 saving on a 2,000 m³ project. | R |
| [Reder churn](https://github.com/michizler/reder-analytics) | Flattens nine nested JSON columns into a 12,483 × 55 table, adds RFM features, selects by mutual information and serves the model through FastAPI. | Python · scikit-learn · FastAPI |
| [Databricks big data](https://github.com/michizler/data-science-projects/tree/master/databricks-bigdata-analytics) | Spark SQL over 572,935 clinical trial records, and an ALS game recommender tuned by grid search and tracked in MLflow. | PySpark · Spark SQL · MLlib · MLflow |
| [SQL Server design](https://github.com/michizler/sql-database-projects) | A 9-table 3NF banking database with salted password hashes, procedures and triggers, plus NHS prescribing analysis with window functions and z-score outliers. | T-SQL · SQL Server |
| [IMF global economy](https://github.com/michizler/imf-globaleconomy-analytics) | A Power BI star schema over 180+ countries and 44 IMF indicators from 2001 to 2020, with custom DAX. | Power BI · DAX |

<sub>Every metric on this page comes from the linked repo, except Rebel Hive, which is private client work.</sub>

<br>

<p align="center">
  <a href="mailto:michizler@gmail.com"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/footer/email-dark.svg"><img alt="Email" src="assets/footer/email-light.svg" width="87" height="36"></picture></a>
  <a href="https://www.linkedin.com/in/bright-uzosike"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/footer/linkedin-dark.svg"><img alt="LinkedIn" src="assets/footer/linkedin-light.svg" width="106" height="36"></picture></a>
  <a href="https://github.com/michizler/data-science-projects"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/footer/portfolio-dark.svg"><img alt="Portfolio" src="assets/footer/portfolio-light.svg" width="105" height="36"></picture></a>
</p>
