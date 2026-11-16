# Historical event alignment

| method    |   matched_events |   events |    recall |   median_delay_months |   unmatched_alerts_per_year |   alerts |
|:----------|-----------------:|---------:|----------:|----------------------:|----------------------------:|---------:|
| legacy    |                2 |       15 | 0.133333  |                     1 |                     6.73684 |       34 |
| rolling_z |                8 |       15 | 0.533333  |                     0 |                    52.6316  |      260 |
| ewma      |                8 |       15 | 0.533333  |                     0 |                    22.1053  |      114 |
| glm       |                1 |       15 | 0.0666667 |                     2 |                     7.78947 |       38 |

Retained method: legacy. Matched date is measured from the public action, not incident onset. Legacy tests all-product labels and has broader match eligibility. Zero-history product series and taxonomy changes can reduce GLM coverage. Overlapping action windows are dependent. Unmatched alerts per year is a workload proxy. A census of false alarms is unavailable.

[Event-by-event results](event_results.csv) · [Event register](../docs/backtest_events.csv) · [Aggregate snapshot](product_monthly.json).
