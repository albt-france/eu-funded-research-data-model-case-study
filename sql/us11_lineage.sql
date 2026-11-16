-- US11. Lineage: every project row points to the load batch (source file, download date, lines repaired).
SELECT b.batch_id, b.programme_code, b.source_url, b.downloaded_utc, b.loaded_utc, b.rows_read, b.lines_repaired,
       b.lines_rejected, COUNT(p.project_id) AS projects
FROM load_batch b LEFT JOIN project p USING (batch_id)
GROUP BY ALL ORDER BY b.batch_id;
