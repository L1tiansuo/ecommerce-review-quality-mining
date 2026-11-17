package com.qr.service;
import com.qr.repository.Store;
import org.springframework.stereotype.Component;import org.springframework.boot.CommandLineRunner;
import org.springframework.beans.factory.annotation.Value;import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.apache.commons.csv.*;import java.nio.file.*;import java.nio.charset.StandardCharsets;import java.util.*;
/** 只在空库导入经过脱敏的 seed。重启不会重复入库。 */
@Component public class Bootstrap implements CommandLineRunner {
 private final Store s;private final String seed,password;private final AlertService alerts;
 public Bootstrap(Store s,AlertService alerts,@Value("${qr.seed}")String seed,@Value("${qr.password}")String password){this.s=s;this.alerts=alerts;this.seed=seed;this.password=password;}
 private List<CSVRecord> csv(Path p)throws Exception{try(var r=Files.newBufferedReader(p,StandardCharsets.UTF_8);var c=CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build().parse(r)){return c.getRecords();}}
 @org.springframework.transaction.annotation.Transactional
 public void run(String...args)throws Exception{
  if(s.count("SELECT COUNT(*) FROM sys_user")==0){var encoder=new BCryptPasswordEncoder();for(String role:List.of("ADMIN","ANALYST","VIEWER"))s.db.update("INSERT INTO sys_user(username,password_hash,role) VALUES(?,?,?)",role.toLowerCase(),encoder.encode(password),role);}
  if(s.count("SELECT COUNT(*) FROM param_snapshot")==0){s.db.update("INSERT INTO param_snapshot VALUES(?,?,CURRENT_TIMESTAMP)","v1-2026-10","{\"weights\":{\"quality\":0.28,\"appearance\":0.12,\"logistics\":0.15,\"service\":0.13,\"value\":0.17,\"package\":0.15},\"half_life\":90,\"m\":10,\"model_version\":\"tfidf-svc-v1\",\"dictionary_version\":\"2026-11-v1\"}");String[] names={"综合指数过低","单维度得分过低","七日差评率上升","刷评风险占比过高","方面情感下滑"};String[] thresholds={"{\"red\":52,\"orange\":56}","{\"red\":0.45,\"orange\":0.50}","{\"red\":1,\"orange\":0.5,\"yellow\":0.3}","{\"red\":0.5,\"orange\":0.3,\"yellow\":0.2}","{\"red\":0.5,\"orange\":0.3,\"yellow\":0.2}"};for(int i=0;i<5;i++)s.db.update("INSERT INTO rule_config(code,name,threshold_json) VALUES(?,?,?)","R"+(i+1),names[i],thresholds[i]);}
  Path base=Path.of(seed);
  // 索引在每次启动时补建（已存在则被忽略）。必须放在"已有数据就直接返回"之前，
  // 否则老库升级上来永远补不到新索引。缺 idx_qi_latest 时 latest() 的窗口函数要全表排序。
  for(String ddl:List.of("CREATE INDEX idx_review_product_time ON review(product_id,review_time)","CREATE INDEX idx_qi_period ON quality_index(period_start,product_id)","CREATE INDEX idx_alert_status ON alert(status,created_at)","CREATE INDEX idx_qi_latest ON quality_index(product_id,period_start DESC,computed_at DESC,id DESC,qi,grade,sample_size,param_version)")){try{s.db.execute(ddl);}catch(Exception ignored){}}
  if(s.count("SELECT COUNT(*) FROM config_store WHERE code='aspect-dict'")==0&&Files.exists(base.resolve("aspect_dict.json")))s.db.update("INSERT INTO config_store VALUES(?,?)","aspect-dict",Files.readString(base.resolve("aspect_dict.json")));
  if(s.count("SELECT COUNT(*) FROM product")>0||!Files.exists(base.resolve("products.csv")))return;
  for(var r:csv(base.resolve("categories.csv")))s.db.update("INSERT INTO category VALUES(?,?)",r.get(0),r.get("name"));
  for(int i=1;i<=12;i++)s.db.update("INSERT INTO supplier VALUES(?,?)",i,"合成供应商 "+i+"（模拟）");
  for(var r:csv(base.resolve("products.csv")))s.db.update("INSERT INTO product(id,name,category_id,supplier_id,scenario) VALUES(?,?,?,?,?)",r.get(0),r.get("name"),r.get("category_id"),r.get("supplier_id"),r.get("scenario"));
  // 种子评论按固定行顺序编号，分析文件使用同一编号，全部写入一笔事务。
  new org.springframework.transaction.support.TransactionTemplate(new org.springframework.jdbc.datasource.DataSourceTransactionManager(s.db.getDataSource())).execute(status->{try{
   long batch=s.insert("INSERT INTO import_batch(file_name,status,operator) VALUES(?,1,'bootstrap')","seed/reviews.csv");var rows=csv(base.resolve("reviews.csv"));List<Object[]> values=new ArrayList<>();long id=0;
   for(var r:rows)values.add(new Object[]{++id,r.get(0),r.get("content_raw"),r.get("content_raw"),r.get("rating"),r.get("review_time"),r.get("source_type"),batch});
   s.db.batchUpdate("INSERT INTO review(id,product_id,content_raw,content_clean,rating,review_time,source_type,batch_id) VALUES(?,?,?,?,?,?,?,?)",values);s.db.update("UPDATE import_batch SET total=?,success=? WHERE id=?",rows.size(),rows.size(),batch);
   Path analysis=base.resolve("analysis.jsonl");if(Files.exists(analysis)){values.clear();try(var lines=Files.lines(analysis)){lines.forEach(l->{Map<String,Object> a=s.parse(l);values.add(new Object[]{a.get("review_id"),a.get("sentiment"),a.get("confidence"),a.get("fake_prob"),s.stringify(a.get("hits")),s.stringify(a.get("aspects")),a.get("model_version")});});}s.db.batchUpdate("INSERT INTO review_analysis VALUES(?,?,?,?,?,?,?)",values);}
   Path indices=base.resolve("indices.jsonl");if(Files.exists(indices)){values.clear();try(var lines=Files.lines(indices)){lines.forEach(l->{Map<String,Object> a=s.parse(l);values.add(new Object[]{a.get("product_id"),a.get("period_start"),a.get("period_end"),a.get("qi"),a.get("grade"),s.stringify(a.get("dims")),a.get("sample_size"),a.get("param_version")});});}s.db.batchUpdate("INSERT INTO quality_index(product_id,period_start,period_end,qi,grade,dim_scores,sample_size,param_version) VALUES(?,?,?,?,?,?,?,?)",values);}
   return null;
  }catch(Exception e){throw new RuntimeException(e);}});
  // 索引已在本方法开头统一补建，这里只做预警扫描。
  alerts.scan();
 }
}
