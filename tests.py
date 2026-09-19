import main
from data import events_manual
from main import pd
import matplotlib.pyplot as plt

# beta_data = main.yf.download(
#     ["SEI", "SPY"],
#     start="2026-02-13",
#     end="2026-08-05",
#     interval="1d"
# )

# schedule = main.nyse.schedule(
#     start_date="2026-08-05",
#     end_date="2026-08-12"
# )

event = {
    "company": "Solaris Energy Infrastructure",
    "ticker": "SEI",
    "event_time": "2026-08-05 16:05",
    "event_type": "guidance_raise",
    "guidance_metric": "adjusted_ebitda",

    "previous_guidance_low": 80.00,
    "previous_guidance_high": 95.00,

    "new_guidance_low": 90.00,
    "new_guidance_high": 105.00
}

# sei = main.yf.download(
#     "SEI",
#     start="2026-08-05",
#     end="2026-08-11",
#     interval="5m"
# )

# spy = main.yf.download(
#     "SPY",
#     start="2026-08-05",
#     end="2026-08-11",
#     interval="5m"
# )

# returns = main.analyze_event(event)
# for key, value in returns.items():
#     print(f"{key}: {value:.2%}")

# print("\n\n\n Events catalogue:\n")

# for event in events_manual.events:
#     returns = main.analyze_event(event)
#     for key, value in returns.items():
#         print(f"{key}: {value:.2%}")

rows = []
for event in events_manual.events:
    result = main.analyze_event(event)

    row = {
        "company": event["company"],
        "ticker": event["ticker"],
        "event_time": event["event_time"],
        "event_type": event["event_type"],
        "guidance_metric": event["guidance_metric"],
        "guidance_revision": main.guidance_range_revision(
            event["previous_guidance_low"],
            event["previous_guidance_high"],
            event["new_guidance_low"],
            event["new_guidance_high"]
        ),

        "immediate_return": result["immediate return"],
        "1h_return": result["1 hour return"],
        "1d_return": result["1 day return"],
        "3d_return": result["3 days return"],

        "immediate_adjusted": result["immediate adjusted return"],
        "1h_adjusted": result["1 hour adjusted return"],
        "1d_adjusted": result["1 day adjusted return"],
        "3d_adjusted": result["3 days adjusted return"]
    }

    rows.append(row)

events_df = pd.DataFrame(rows)
events_df.index = events_df.index + 1

percentage_columns = [
    "guidance_revision",
    "immediate_return",
    "1h_return",
    "1d_return",
    "3d_return",
    "immediate_adjusted",
    "1h_adjusted",
    "1d_adjusted",
    "3d_adjusted"
]

pd.set_option("display.max_columns", None)
print(
    events_df.to_string(
        formatters={
            col: lambda x: f"{x:.2%}"
            for col in percentage_columns
        }
    )
)

# plot

horizons = ["immediate_adjusted", "1h_adjusted", "1d_adjusted", "3d_adjusted"]
labels = ["Immediate", "1 hour", "1 day", "3 days"]

plt.figure(figsize=(8, 5))

for _, row in events_df.iterrows():
    values = [row[col] * 100 for col in horizons]

    plt.plot(
        labels,
        values,
        marker="o",
        label=row["ticker"]
    )

plt.axhline(0)
plt.xlabel("Time after event")
plt.ylabel("Abnormal return (%)")
plt.title("Stock Reaction Trajectories After Guidance Events")
plt.legend()

plt.show()