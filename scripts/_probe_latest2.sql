-- 加索引后重测窗口函数写法
CREATE INDEX idx_qi_latest ON quality_index(product_id, period_start DESC, computed_at DESC, id DESC);

SET @t1 = NOW(6);
SELECT COUNT(*) INTO @n FROM (
  SELECT q.id, ROW_NUMBER() OVER (PARTITION BY q.product_id
    ORDER BY q.period_start DESC, q.computed_at DESC, q.id DESC) rn
  FROM quality_index q) t WHERE t.rn=1;
SELECT @n AS rows_out, TIMESTAMPDIFF(MICROSECOND,@t1,NOW(6))/1000 AS ms_with_index;
