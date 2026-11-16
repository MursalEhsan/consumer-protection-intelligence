WITH comparison_months AS (
    SELECT 'current' AS period_name, :current_month AS month
    UNION ALL
    SELECT 'prior_year', :prior_year_month
),
period_values AS (
    SELECT
        comparison_months.period_name,
        comparison_months.month,
        monthly_issue_counts.issue AS issue,
        monthly_issue_counts.count AS issue_count,
        monthly_totals.complaint_count AS total_complaints,
        1.0 * monthly_issue_counts.count / monthly_totals.complaint_count AS issue_share
    FROM comparison_months
    LEFT JOIN source_monthly_totals AS monthly_totals
        ON monthly_totals.month = comparison_months.month
    LEFT JOIN source_monthly_issue_counts AS monthly_issue_counts
        ON monthly_issue_counts.month = comparison_months.month
        AND monthly_issue_counts.issue = :issue
)
SELECT
    MAX(CASE WHEN period_name = 'current' THEN month END) AS current_month,
    MAX(CASE WHEN period_name = 'current' THEN issue END) AS current_issue,
    MAX(CASE WHEN period_name = 'current' THEN issue_count END) AS current_issue_count,
    MAX(CASE WHEN period_name = 'current' THEN total_complaints END) AS current_total_complaints,
    MAX(CASE WHEN period_name = 'current' THEN issue_share END) AS current_issue_share,
    MAX(CASE WHEN period_name = 'prior_year' THEN month END) AS prior_year_month,
    MAX(CASE WHEN period_name = 'prior_year' THEN issue END) AS prior_year_issue,
    MAX(CASE WHEN period_name = 'prior_year' THEN issue_count END) AS prior_year_issue_count,
    MAX(CASE WHEN period_name = 'prior_year' THEN total_complaints END) AS prior_year_total_complaints,
    MAX(CASE WHEN period_name = 'prior_year' THEN issue_share END) AS prior_year_issue_share,
    CASE
        WHEN MAX(CASE WHEN period_name = 'current' THEN issue_share END) IS NULL
          OR MAX(CASE WHEN period_name = 'prior_year' THEN issue_share END) IS NULL
        THEN NULL
        ELSE 100.0 * (
            MAX(CASE WHEN period_name = 'current' THEN issue_share END)
            - MAX(CASE WHEN period_name = 'prior_year' THEN issue_share END)
        )
    END AS share_change_percentage_points
FROM period_values;
