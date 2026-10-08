"""Charts for the fictional example (reference for a project charts.py). Every string goes through ctx.esc via bar_chart."""

def charts(ctx):
    weeks = ["Jul 6", "", "", "", "Aug 3", "", "", "", "Aug 31", "", "", "", "Sep 28"]
    deposits = [6.1, 7.4, 9.0, 12.8, 18.5, 26.0, 33.9, 44.2, 50.3, 47.0, 41.8, 38.2, 41.2]
    fig = ctx.bar_chart(deposits, weeks, title="Vault deposits by week, $M (fictional)",
                        caption="Deposits rose during the points boost (Aug 3 to Sep 7) and fell 35% after it ended.",
                        source="Source: fictional example data.", aria="Bar chart of weekly vault deposits in millions of dollars",
                        ymax=60, yticks=[0, 20, 40, 60], highlight=(8,), notes=[(8, "Boost ends")],
                        tips=[f"Week {i + 1}: ${v}M" for i, v in enumerate(deposits)], table_headers=("Week", "$M"))
    return {"Weekly deposits": fig}
