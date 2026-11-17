-- 对比两种 latest() 写法的执行耗时
SELECT '--- 旧写法：相关子查询 ---' AS step;
SET @t0 = NOW(6);
SELECT COUNT(*) INTO @n FROM quality_index q
WHERE q.id=(SELECT z.id FROM quality_index z WHERE z.product_id=q.product_id
            ORDER BY z.period_start DESC, z.computed_at DESC, z.id DESC LIMIT 1);
SELECT @n AS rows_out, TIMESTAMPDIFF(MICROSECOND,@t0,NOW(6))/1000 AS ms;

SELECT '--- 新写法：窗口函数 ---' AS step;
SET @t1 = NOW(6);
SELECT COUNT(*) INTO @n FROM (
  SELECT q.id, ROW_NUMBER() OVER (PARTITION BY q.product_id
    ORDER BY q.period_start DESC, q.computed_at DESC, q.id DESC) rn
  FROM quality_index q) t WHERE t.rn=1;
SELECT @n AS rows_out, TIMESTAMPDIFF(MICROSECOND,@t1,NOW(6))/1000 AS ms;
