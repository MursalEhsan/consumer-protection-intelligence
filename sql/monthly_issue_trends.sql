CREATE INDEX IF NOT EXISTS idx_complaint_sample_date
    ON complaint_sample("Date received");

CREATE INDEX IF NOT EXISTS idx_source_issue_month
    ON source_monthly_issue_counts(month, issue);

CREATE VIEW vw_monthly_issue_trends AS
SELECT
    i.month AS complaint_month,
    i.issue AS issue,
    i.count AS complaint_count,
    t.complaint_count AS monthly_denominator,
    1.0 * i.count / t.complaint_count AS complaint_share
FROM source_monthly_issue_counts AS i
JOIN source_monthly_totals AS t ON i.month = t.month;
