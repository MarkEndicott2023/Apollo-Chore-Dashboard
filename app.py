from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

WORKBOOK = Path(__file__).parent / "chores_centralized.xlsx"
K_PRIOR = 10
STATUS_ORDER = ["done", "missed", "gone", "na"]
STATUS_COLORS = {
    "done": "#2ca02c",
    "missed": "#d62728",
    "gone": "#7f7f7f",
    "na": "#bcbd22",
}


@st.cache_data
def load_data():
    sheets = pd.read_excel(WORKBOOK, sheet_name=None)
    completions = sheets["completions"].copy()
    completions["period_start"] = pd.to_datetime(completions["period_start"])
    completions["week"] = completions["period_start"].dt.to_period("W-SUN").dt.start_time
    chore_values = sheets["chore_values"].copy()
    chore_values["period_start"] = pd.to_datetime(chore_values["period_start"])
    return {
        "people": sheets["people"],
        "chores": sheets["chores"],
        "completions": completions,
        "chore_values": chore_values,
    }


def leaderboard(completions: pd.DataFrame) -> pd.DataFrame:
    counted = completions[completions["status"].isin(["done", "missed"])]
    grouped = (
        counted.groupby("person_id")["status"]
        .value_counts()
        .unstack(fill_value=0)
        .reindex(columns=["done", "missed"], fill_value=0)
    )
    grouped["total"] = grouped["done"] + grouped["missed"]
    grouped["completion_pct"] = (grouped["done"] / grouped["total"] * 100).round(1)
    return grouped.sort_values("completion_pct", ascending=False).reset_index()


def leaderboard_v2(completions: pd.DataFrame) -> pd.DataFrame:
    counted = completions[completions["status"].isin(["done", "missed"])]
    done = counted[counted["status"] == "done"].groupby("person_id").size()
    total = counted.groupby("person_id").size()
    done = done.reindex(total.index, fill_value=0)
    house_p = done.sum() / total.sum()
    bayes = (done + K_PRIOR * house_p) / (total + K_PRIOR)
    out = pd.DataFrame(
        {
            "done": done.astype(int),
            "total": total.astype(int),
            "house_avg_pct": round(house_p * 100, 1),
            "k": K_PRIOR,
            "bayes_pct": (bayes * 100).round(1),
        }
    ).reset_index()
    return out.sort_values("bayes_pct", ascending=False).reset_index(drop=True)

def status_share_over_time(df: pd.DataFrame) -> pd.DataFrame:
    counts = (
        df.groupby(["week", "status"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=STATUS_ORDER, fill_value=0)
    )
    totals = counts.sum(axis=1).replace(0, pd.NA)
    shares = counts.div(totals, axis=0).fillna(0) * 100
    return shares.reset_index().melt(
        id_vars="week", var_name="status", value_name="share"
    )


def status_area_chart(df: pd.DataFrame, title: str):
    long = status_share_over_time(df)
    fig = px.area(
        long,
        x="week",
        y="share",
        color="status",
        category_orders={"status": STATUS_ORDER},
        color_discrete_map=STATUS_COLORS,
        title=title,
    )
    fig.update_layout(
        yaxis=dict(title="Share (%)", range=[0, 100]),
        xaxis=dict(title="Week"),
        legend_title="Status",
        hovermode="x unified",
    )
    return fig


def bounty_traces(chore_values: pd.DataFrame, chores: pd.DataFrame):
    merged = chore_values.merge(
        chores[["chore_id", "name", "category"]], on="chore_id", how="left"
    )
    fig = px.line(
        merged.sort_values("period_start"),
        x="period_start",
        y="points",
        color="chore_id",
        markers=True,
        hover_data=["category"],
        title="Bounty escalation by chore (chore_values.points over time)",
    )
    fig.update_layout(
        xaxis=dict(title="Week"),
        yaxis=dict(title="Points"),
        legend_title="Chore",
        hovermode="closest",
    )
    return fig


st.set_page_config(page_title="Apollo Chore Dashboard", layout="centered")
st.title("Apollo Chore Dashboard")
st.markdown(
    "Tracking chore reliability and bounty dynamics at Apollo Cooperative, a "
    "cooperative house. Data is consolidated from monthly tracking workbooks "
    "covering Aug 2025 onward. Completion statuses: **done**, **missed**, "
    "**gone** (resident away from the house), **na** (chore not applicable that week)."
)

data = load_data()
completions = data["completions"]
chores = data["chores"]
people = data["people"]

st.header("Leaderboard — completion %")
st.caption(
    "Who completes their assigned chores most reliably. Bar length is the share of "
    "`done` outcomes out of chores the resident was on the hook for "
    "(`done + missed`). `gone` and `na` are excluded since they weren't controllable. "
    "Hover a bar for the underlying counts."
)
board = leaderboard(completions)

board_display = board.merge(
    people[["person_id", "display_name"]], on="person_id", how="left"
)
fig_board = px.bar(
    board_display,
    x="completion_pct",
    y="display_name",
    orientation="h",
    text="completion_pct",
    hover_data={"done": True, "missed": True, "total": True, "completion_pct": False},
    labels={"completion_pct": "Completion %", "display_name": ""},
)
fig_board.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
fig_board.update_layout(
    yaxis=dict(categoryorder="total ascending"),
    xaxis=dict(range=[0, 105]),
    height=max(400, 28 * len(board_display)),
)
st.plotly_chart(fig_board, width="stretch")

st.header("Leaderboard — adjusted for chore count")
st.caption(
    f"The raw % above isn't quite fair: someone who's only had a handful of chores "
    f"(new residents, officers, people who travel a lot) can land near the top or "
    f"bottom just from a lucky or unlucky stretch. This version evens things out. "
    f"Think of it like this: everyone starts with **{K_PRIOR} 'practice' chores** "
    f"scored at the house's overall completion rate, and then their real chores get "
    f"added on top. If you've done 50 real chores, those 10 practice ones barely "
    f"matter — your score is basically your real performance. If you've only done 5, "
    f"the practice chores still weigh in and your score sits closer to the group "
    f"average until you've built up more of a track record. Weeks you were `gone` "
    f"or had no chore assigned (`na`) don't count either way."
)
board_v2 = leaderboard_v2(completions).merge(
    people[["person_id", "display_name"]], on="person_id", how="left"
)
board_v2 = board_v2[
    ["display_name", "done", "total", "house_avg_pct", "k", "bayes_pct"]
]
board_v2_display = board_v2.rename(
    columns={
        "display_name": "Resident",
        "done": "Chores completed",
        "total": "Chores assigned",
        "house_avg_pct": "House completion rate %",
        "k": "Practice chores (k)",
        "bayes_pct": "Adjusted completion %",
    }
)
st.table(
    board_v2_display.style.format(
        {"House completion rate %": "{:.1f}", "Adjusted completion %": "{:.1f}"}
    ).hide(axis="index")
)

st.header("Status mix over time — by person")
st.caption(
    "Weekly breakdown of completion outcomes for one resident (or all residents "
    "aggregated). Each stacked band shows the share of that week's completions "
    "with each status. Useful for spotting streaks, recoveries, and extended "
    "absences."
)
person_options = ["All"] + sorted(
    people["display_name"].dropna().tolist()
)
selected_person = st.selectbox("Person", person_options, key="person_select")
if selected_person == "All":
    person_df = completions
    person_title = "All people"
else:
    pid = people.loc[people["display_name"] == selected_person, "person_id"].iloc[0]
    person_df = completions[completions["person_id"] == pid]
    person_title = selected_person
st.plotly_chart(
    status_area_chart(person_df, f"Status mix — {person_title}"),
    width="stretch",
)

st.header("Status mix over time — by chore")
st.caption(
    "Same view, but slicing by chore instead of person. Surfaces chores that "
    "are routinely skipped, or stretches where nobody was around to do them."
)
chore_options = ["All"] + sorted(chores["chore_id"].tolist())
selected_chore = st.selectbox("Chore", chore_options, key="chore_select")
if selected_chore == "All":
    chore_df = completions
    chore_title = "All chores"
else:
    chore_df = completions[completions["chore_id"] == selected_chore]
    chore_title = selected_chore
st.plotly_chart(
    status_area_chart(chore_df, f"Status mix — {chore_title}"),
    width="stretch",
)

st.header("Bounty escalation traces")
st.caption(
    "How a chore's point value grows when nobody claims it. Per constitution "
    "§3.a.ii.1, each uncompleted week adds 5 points to the bounty; claiming a "
    "bounty resets the next week to 15. A line dropping back to 15 means someone "
    "took the bounty. Only chores with dynamic point values appear here."
)
all_chore_ids = sorted(data["chore_values"]["chore_id"].unique().tolist())
selected_chores = st.multiselect(
    "Filter chores (empty = all)", all_chore_ids, default=[]
)
cv = data["chore_values"]
if selected_chores:
    cv = cv[cv["chore_id"].isin(selected_chores)]
st.plotly_chart(bounty_traces(cv, chores), width="stretch")
