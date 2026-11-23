-- Load data by running analyze.py; it creates outputs/mauna_loa_co2.sqlite.

-- 1. Annual concentration summary.
SELECT year, ROUND(AVG(co2), 2) AS mean_co2_ppm,
       ROUND(MIN(co2), 2) AS min_weekly_co2_ppm,
       ROUND(MAX(co2), 2) AS max_weekly_co2_ppm,
       COUNT(*) AS observations
FROM weekly_co2
GROUP BY year
ORDER BY year;

-- 2. Average seasonal pattern by calendar month.
SELECT month, ROUND(AVG(co2), 2) AS mean_co2_ppm,
       COUNT(*) AS observations
FROM weekly_co2
GROUP BY month
ORDER BY month;

-- 3. Inspect the 10 highest weekly readings in this historical snapshot.
SELECT date, co2
FROM weekly_co2
ORDER BY co2 DESC
LIMIT 10;

-- 4. Inspect earliest and latest observations.
SELECT date, co2 FROM weekly_co2 ORDER BY date ASC LIMIT 1;
SELECT date, co2 FROM weekly_co2 ORDER BY date DESC LIMIT 1;
