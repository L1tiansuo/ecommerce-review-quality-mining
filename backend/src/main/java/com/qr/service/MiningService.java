package com.qr.service;
import com.qr.repository.Store;import com.qr.client.AlgoClient;import org.springframework.stereotype.Service;import org.springframework.scheduling.annotation.Async;import java.util.*;import java.time.*;
/** 每商品提交一笔事务，可取消，失败可重新提交；已完成商品的结果可复用。 */
@Service public class MiningService {
 private final Store s;private final AlgoClient algo;private final AlertService alerts;
 public MiningService(Store s,AlgoClient algo,AlertService alerts){this.s=s;this.algo=algo;this.alerts=alerts;}
 @Async public synchronized void run(long id,Map<String,Object> params){
  s.db.update("UPDATE mining_task SET status=1 WHERE id=?",id);
  try{
   String version=params.getOrDefault("param_version","v1-2026-10").toString();Map<String,Object> snapshot=s.parse(s.one("SELECT params_json FROM param_snapshot WHERE version=?",version).get("params_json"));
   int scope=((Number)params.getOrDefault("scope_type",3)).intValue();String value=params.getOrDefault("scope_value","").toString();
   var products=scope==1?s.list("SELECT id,category_id FROM product WHERE id=?",value):scope==2?s.list("SELECT id,category_id FROM product WHERE category_id=?",value):s.list("SELECT id,category_id FROM product ORDER BY id");
   LocalDate end=LocalDate.parse(params.getOrDefault("period_end","2026-11-09").toString());LocalDate start=LocalDate.parse(params.getOrDefault("period_start",end.withDayOfMonth(1).toString()).toString());if(start.isAfter(end))throw new IllegalArgumentException("开始时间不能晚于结束时间");int done=0;
   Object dictionary=params.getOrDefault("dictionary_snapshot",s.parse(s.one("SELECT value_json FROM config_store WHERE code='aspect-dict'").get("value_json")));
   for(var p:products){if(s.count("SELECT COUNT(*) FROM mining_task WHERE id=? AND cancelled=1",id)>0){s.db.update("UPDATE mining_task SET status=4,message='任务已取消',finished_at=CURRENT_TIMESTAMP WHERE id=?",id);return;}
    Object pid=p.get("id");var raw=s.list("SELECT id review_id,product_id,content_clean content,rating,review_time FROM review WHERE product_id=? ORDER BY id",pid);if(raw.isEmpty())continue;
    // Java SQL Timestamp 先转标准字符串，避免 JSON 数字时间戳歧义。
    for(var r:raw)r.put("review_time",r.get("review_time").toString());
    Map<String,Object> analysis=algo.call("/internal/analyze",Map.of("reviews",raw,"dictionary",dictionary));List<Map<String,Object>> items=(List<Map<String,Object>>)analysis.get("items");
    new org.springframework.transaction.support.TransactionTemplate(new org.springframework.jdbc.datasource.DataSourceTransactionManager(s.db.getDataSource())).execute(st->{
     List<Object[]> inserts=new ArrayList<>();for(int i=0;i<items.size();i++){var x=items.get(i);String label=x.get("label").toString();s.db.update("DELETE FROM review_analysis WHERE review_id=?",raw.get(i).get("review_id"));inserts.add(new Object[]{raw.get(i).get("review_id"),label.equals("pos")?1:label.equals("neg")?-1:0,x.get("confidence"),x.get("fake_prob"),s.stringify(x.get("hits")),s.stringify(x.get("aspects")),analysis.get("model_version")});}
     s.db.batchUpdate("INSERT INTO review_analysis VALUES(?,?,?,?,?,?,?)",inserts);return null;
    });
    List<Map<String,Object>> rs=new ArrayList<>();for(int i=0;i<raw.size();i++){var r=raw.get(i);LocalDate time=LocalDate.parse(r.get("review_time").toString().substring(0,10));if(time.isBefore(start)||time.isAfter(end))continue;var x=items.get(i);rs.add(Map.of("review_time",r.get("review_time"),"fake_prob",x.get("fake_prob"),"aspects",x.get("aspects")));}
    // 品类先验取之前90天已发布维度得分中位数；没有数据才退回0.55。
    Map<String,List<Double>> pv=new HashMap<>();for(var prev:s.list("SELECT q.dim_scores FROM quality_index q JOIN product p ON p.id=q.product_id WHERE p.category_id=? AND q.period_end<? AND q.period_end>=? AND q.param_version=?",p.get("category_id"),start,end.minusDays(90),version)){List<Map<String,Object>> ds=s.parse(prev.get("dim_scores"));for(var d:ds)pv.computeIfAbsent(d.get("code").toString(),k->new ArrayList<>()).add(((Number)d.get("score")).doubleValue());}
    Map<String,Double> priors=new HashMap<>();for(var entry:pv.entrySet()){var list=entry.getValue();Collections.sort(list);int n=list.size();priors.put(entry.getKey(),n%2==1?list.get(n/2):(list.get(n/2-1)+list.get(n/2))/2);}
    var index=algo.call("/internal/index",Map.of("reviews",rs,"product_id",pid,"period_start",start.toString(),"period_end",end.toString(),"param_version",version,"params",snapshot,"priors",priors));
    new org.springframework.transaction.support.TransactionTemplate(new org.springframework.jdbc.datasource.DataSourceTransactionManager(s.db.getDataSource())).execute(st->{s.db.update("DELETE FROM quality_index WHERE product_id=? AND period_start=? AND param_version=?",pid,start,version);s.db.update("INSERT INTO quality_index(product_id,period_start,period_end,qi,grade,dim_scores,sample_size,param_version) VALUES(?,?,?,?,?,?,?,?)",pid,start,end,index.get("qi"),index.get("grade"),s.stringify(index.get("dims")),index.get("sample_size"),version);return null;});
    s.db.update("UPDATE mining_task SET progress=?,message=? WHERE id=?",++done*100/Math.max(1,products.size()),"已处理商品 "+pid,id);
   }
   alerts.scan();s.db.update("UPDATE mining_task SET status=2,progress=100,message='挖掘、指数与预警扫描完成',finished_at=CURRENT_TIMESTAMP WHERE id=?",id);
  }catch(Exception e){s.db.update("UPDATE mining_task SET status=3,message=?,finished_at=CURRENT_TIMESTAMP WHERE id=?","算法或存储环节："+e.getMessage(),id);}
 }
}
