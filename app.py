import calendar
import json
import random
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st


OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "qwen2.5:7b"

POLICY_DOCS = [
    {
        "title": "Budget Review Policy",
        "content": (
            "Any department exceeding monthly budget by more than 10% requires CFO review. "
            "Variance between 5% and 10% should be monitored by the finance business partner."
        ),
    },
    {
        "title": "Cloud Cost Policy",
        "content": (
            "Cloud infrastructure expenses should be reviewed when month-over-month growth exceeds 15%. "
            "Engineering and IT teams should provide utilization evidence for major cloud cost increases."
        ),
    },
    {
        "title": "Marketing Spend Policy",
        "content": (
            "Marketing campaign expenses above 10000 require pre-approval. "
            "Campaign spend should be compared with pipeline contribution and monthly budget."
        ),
    },
    {
        "title": "CFO Report Guideline",
        "content": (
            "A monthly CFO report should include executive summary, revenue, expense, profit, budget variance, "
            "top cost drivers, risk notes, and recommended management actions."
        ),
    },
]


def call_ollama(model: str, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("message", {}).get("content", "").strip()
    except urllib.error.URLError as exc:
        return (
            "OLLAMA_CONNECTION_ERROR: Cannot connect to Ollama. "
            "Please run `ollama serve` and pull a model such as `ollama pull qwen2.5:7b`. "
            f"Details: {exc}"
        )


def extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


@st.cache_data
def create_mock_finance_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    random.seed(42)
    departments = ["Sales", "Marketing", "IT", "Operations", "HR", "Finance"]
    expense_categories = ["Cloud", "Payroll", "Software", "Travel", "Ads", "Consulting", "Office"]
    revenue_categories = ["Subscription Revenue", "Professional Services", "Enterprise Contract"]
    vendors = {
        "Cloud": ["Azure", "AWS", "Datadog"],
        "Payroll": ["ADP", "Workday"],
        "Software": ["Salesforce", "Notion", "Snowflake", "GitHub"],
        "Travel": ["Delta", "Marriott", "Uber"],
        "Ads": ["Google", "LinkedIn", "Meta"],
        "Consulting": ["Deloitte", "Accenture", "Boutique Advisors"],
        "Office": ["Staples", "WeWork"],
    }

    rows = []
    budget_rows = []
    months = pd.period_range("2025-11", "2026-04", freq="M")

    for month in months:
        month_str = str(month)
        _, last_day = calendar.monthrange(month.year, month.month)

        for department in departments:
            for category in expense_categories:
                base_budget = random.randint(6000, 24000)
                if department == "IT" and category == "Cloud":
                    base_budget = 32000
                if department == "Marketing" and category == "Ads":
                    base_budget = 28000
                if department == "HR" and category == "Payroll":
                    base_budget = 36000

                budget_rows.append(
                    {
                        "month": month_str,
                        "department": department,
                        "category": category,
                        "budget_amount": base_budget,
                        "currency": "USD",
                    }
                )

                txn_count = random.randint(1, 4)
                for _ in range(txn_count):
                    day = random.randint(1, last_day)
                    amount = round(base_budget / txn_count * random.uniform(0.55, 1.35), 2)

                    if month_str == "2026-04" and department == "Marketing" and category == "Ads":
                        amount *= 1.45
                    if month_str == "2026-04" and department == "IT" and category == "Cloud":
                        amount *= 1.25

                    rows.append(
                        {
                            "date": date(month.year, month.month, day).isoformat(),
                            "month": month_str,
                            "department": department,
                            "category": category,
                            "vendor": random.choice(vendors[category]),
                            "amount": round(amount, 2),
                            "type": "expense",
                            "currency": "USD",
                        }
                    )

        for category in revenue_categories:
            for _ in range(random.randint(5, 10)):
                day = random.randint(1, last_day)
                rows.append(
                    {
                        "date": date(month.year, month.month, day).isoformat(),
                        "month": month_str,
                        "department": "Sales",
                        "category": category,
                        "vendor": f"Client {random.choice(['A', 'B', 'C', 'D', 'E'])}",
                        "amount": round(random.uniform(25000, 85000), 2),
                        "type": "revenue",
                        "currency": "USD",
                    }
                )

    return pd.DataFrame(rows), pd.DataFrame(budget_rows)


def load_uploaded_data(uploaded_file: Any) -> pd.DataFrame:
    if uploaded_file is None:
        transactions, _ = create_mock_finance_data()
        return transactions

    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    if "date" in df.columns and "month" not in df.columns:
        df["month"] = pd.to_datetime(df["date"]).dt.to_period("M").astype(str)
    return df


def money(value: float) -> str:
    return f"${value:,.0f}"


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def previous_month(month: str) -> str:
    period = pd.Period(month, freq="M")
    return str(period - 1)


def monthly_metrics(transactions: pd.DataFrame, budget: pd.DataFrame, month: str) -> dict[str, Any]:
    current = transactions[transactions["month"] == month]
    previous = transactions[transactions["month"] == previous_month(month)]

    revenue = float(current[current["type"] == "revenue"]["amount"].sum())
    expense = float(current[current["type"] == "expense"]["amount"].sum())
    prev_expense = float(previous[previous["type"] == "expense"]["amount"].sum())
    profit = revenue - expense

    monthly_budget = float(budget[budget["month"] == month]["budget_amount"].sum())
    variance_amount = expense - monthly_budget
    variance_pct = variance_amount / monthly_budget if monthly_budget else 0
    mom_expense_change = (expense - prev_expense) / prev_expense if prev_expense else 0

    expense_rows = current[current["type"] == "expense"]
    top_departments = (
        expense_rows.groupby("department")["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
        .reset_index()
        .to_dict("records")
    )
    top_vendors = (
        expense_rows.groupby("vendor")["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
        .reset_index()
        .to_dict("records")
    )
    top_categories = (
        expense_rows.groupby("category")["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
        .reset_index()
        .to_dict("records")
    )

    department_spend = expense_rows.groupby("department")["amount"].sum().reset_index()
    department_budget = (
        budget[budget["month"] == month].groupby("department")["budget_amount"].sum().reset_index()
    )
    variance = department_spend.merge(department_budget, on="department", how="left")
    variance["variance_amount"] = variance["amount"] - variance["budget_amount"]
    variance["variance_pct"] = variance["variance_amount"] / variance["budget_amount"]
    variance = variance.sort_values("variance_pct", ascending=False)

    return {
        "month": month,
        "revenue": revenue,
        "expense": expense,
        "profit": profit,
        "budget": monthly_budget,
        "variance_amount": variance_amount,
        "variance_pct": variance_pct,
        "mom_expense_change": mom_expense_change,
        "top_departments": top_departments,
        "top_vendors": top_vendors,
        "top_categories": top_categories,
        "department_variance": variance.round(4).to_dict("records"),
    }


def retrieve_policy_context(question: str, metrics: dict[str, Any]) -> list[dict[str, str]]:
    query = f"{question} {json.dumps(metrics, ensure_ascii=False)}".lower()
    scored_docs = []
    for doc in POLICY_DOCS:
        score = 0
        for token in re.findall(r"[a-zA-Z]+", query):
            if token in doc["content"].lower() or token in doc["title"].lower():
                score += 1
        scored_docs.append((score, doc))
    return [doc for score, doc in sorted(scored_docs, reverse=True)[:2] if score > 0]


def classify_intent(question: str, model: str, month: str) -> dict[str, Any]:
    system_prompt = """
You are a finance assistant intent classifier.
Return only valid JSON.

Supported intents:
- monthly_expense
- monthly_revenue
- monthly_profit
- budget_variance
- top_departments
- top_vendors
- generate_report
- general_finance_question

JSON schema:
{
  "intent": "one of the supported intents",
  "month": "YYYY-MM",
  "needs_policy_context": true or false
}
"""
    user_prompt = f"""
Current selected month: {month}
User question: {question}
"""
    response = call_ollama(
        model,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    parsed = extract_json(response)
    return {
        "intent": parsed.get("intent", "general_finance_question"),
        "month": parsed.get("month", month),
        "needs_policy_context": bool(parsed.get("needs_policy_context", False)),
        "raw": response,
    }


def generate_answer(
    question: str,
    model: str,
    intent: dict[str, Any],
    metrics: dict[str, Any],
    policy_context: list[dict[str, str]],
) -> dict[str, Any]:
    context_text = "\n\n".join(
        f"{doc['title']}: {doc['content']}" for doc in policy_context
    )
    prompt = f"""
You are a CFO financial analyst.

Use only the provided financial metrics and policy context.
Do not invent numbers. If a number is missing, do not mention it.
Return only valid JSON.

Required JSON schema:
{{
  "answer": "direct answer in English",
  "insights": ["3 concise business insights"],
  "recommendations": ["2 practical recommendations"],
  "risk_flags": ["0-3 risk flags"]
}}

User question:
{question}

Detected intent:
{json.dumps(intent, ensure_ascii=False)}

Financial metrics:
{json.dumps(metrics, ensure_ascii=False)}

Policy context:
{context_text}
"""
    response = call_ollama(
        model,
        [
            {"role": "system", "content": "You are a precise CFO finance assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.25,
    )
    parsed = extract_json(response)
    if not parsed:
        return {
            "answer": response,
            "insights": [],
            "recommendations": [],
            "risk_flags": [],
        }
    return parsed


def generate_report(model: str, metrics: dict[str, Any], policy_context: list[dict[str, str]]) -> str:
    context_text = "\n\n".join(
        f"{doc['title']}: {doc['content']}" for doc in policy_context
    )
    prompt = f"""
Create a CFO monthly financial report in Markdown.

Sections:
- Executive Summary
- Key Metrics
- Expense Analysis
- Budget Variance
- Vendor / Department Highlights
- Policy and Risk Notes
- Management Recommendations

Use only these metrics:
{json.dumps(metrics, ensure_ascii=False)}

Policy context:
{context_text}

Keep the report concise, professional, and CFO-oriented.
"""
    return call_ollama(
        model,
        [
            {"role": "system", "content": "You write concise CFO management reports."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )


def render_metric_cards(metrics: dict[str, Any]) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Revenue", money(metrics["revenue"]))
    col2.metric("Expense", money(metrics["expense"]), pct(metrics["mom_expense_change"]))
    col3.metric("Profit", money(metrics["profit"]))
    col4.metric("Budget Variance", money(metrics["variance_amount"]), pct(metrics["variance_pct"]))


def render_list(title: str, values: list[str]) -> None:
    if not values:
        return
    st.subheader(title)
    for value in values:
        st.write(f"- {value}")


def main() -> None:
    st.set_page_config(page_title="Local Finance AI Chatbot", layout="wide")
    st.title("Local Finance AI Chatbot")
    st.caption("Ollama-powered CFO assistant with deterministic finance calculations.")

    default_transactions, default_budget = create_mock_finance_data()

    with st.sidebar:
        st.header("Settings")
        model = st.text_input("Ollama model", value=DEFAULT_MODEL)
        uploaded_file = st.file_uploader("Upload transactions CSV or Excel", type=["csv", "xlsx"])
        transactions = load_uploaded_data(uploaded_file)
        budget = default_budget

        available_months = sorted(transactions["month"].dropna().unique().tolist())
        default_index = len(available_months) - 1 if available_months else 0
        selected_month = st.selectbox("Month", available_months, index=default_index)

        st.divider()
        st.write("Try questions:")
        st.caption("What is the total expense this month?")
        st.caption("Which department is most over budget?")
        st.caption("Top vendors by spend?")
        st.caption("Generate a CFO monthly report.")

    metrics = monthly_metrics(transactions, budget, selected_month)
    render_metric_cards(metrics)

    tab_chat, tab_data, tab_report = st.tabs(["Chat", "Data", "Report"])

    with tab_chat:
        question = st.chat_input("Ask a finance question...")

        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if question:
            st.session_state.messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                with st.spinner("Classifying intent and calculating finance metrics..."):
                    intent = classify_intent(question, model, selected_month)
                    target_month = intent.get("month", selected_month)
                    if target_month in available_months:
                        metrics = monthly_metrics(transactions, budget, target_month)

                    policy_context = retrieve_policy_context(question, metrics)
                    answer = generate_answer(question, model, intent, metrics, policy_context)

                st.markdown(answer.get("answer", "No answer generated."))
                render_list("Insights", answer.get("insights", []))
                render_list("Recommendations", answer.get("recommendations", []))
                render_list("Risk Flags", answer.get("risk_flags", []))

                with st.expander("Structured output"):
                    st.json(
                        {
                            "intent": intent,
                            "metrics": metrics,
                            "policy_context": policy_context,
                            "answer": answer,
                        }
                    )

                assistant_text = answer.get("answer", "")
                if answer.get("insights"):
                    assistant_text += "\n\nInsights:\n" + "\n".join(
                        f"- {item}" for item in answer["insights"]
                    )
                if answer.get("recommendations"):
                    assistant_text += "\n\nRecommendations:\n" + "\n".join(
                        f"- {item}" for item in answer["recommendations"]
                    )
                st.session_state.messages.append({"role": "assistant", "content": assistant_text})

    with tab_data:
        left, right = st.columns(2)
        with left:
            st.subheader("Top Departments")
            st.dataframe(pd.DataFrame(metrics["top_departments"]), use_container_width=True)
            st.subheader("Department Budget Variance")
            st.dataframe(pd.DataFrame(metrics["department_variance"]), use_container_width=True)
        with right:
            st.subheader("Top Vendors")
            st.dataframe(pd.DataFrame(metrics["top_vendors"]), use_container_width=True)
            st.subheader("Top Categories")
            st.dataframe(pd.DataFrame(metrics["top_categories"]), use_container_width=True)

        with st.expander("Transactions sample"):
            st.dataframe(transactions.head(100), use_container_width=True)

    with tab_report:
        if st.button("Generate CFO Monthly Report"):
            with st.spinner("Generating report with Ollama..."):
                policy_context = retrieve_policy_context("monthly CFO report", metrics)
                report = generate_report(model, metrics, policy_context)
                st.session_state.report = report

        if "report" in st.session_state:
            st.markdown(st.session_state.report)
            st.download_button(
                "Download Markdown Report",
                data=st.session_state.report,
                file_name=f"cfo_report_{selected_month}.md",
                mime="text/markdown",
            )


if __name__ == "__main__":
    main()
