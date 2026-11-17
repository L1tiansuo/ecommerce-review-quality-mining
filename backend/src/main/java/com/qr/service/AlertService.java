package com.qr.service;
import com.qr.repository.Store;import org.springframework.stereotype.Service;import java.util.*;import java.time.*;
/** 质量预警 R1..R5 与刷评 burst/contradict 等规则分属不同命名空间。 */
@Service public class AlertService {
 private final Store s;private final QueryService q;public AlertService(Store s,QueryService q){this.s=s;this.q=q;}
 private double num(Object x){return ((Number)x).doubleValue();}
 private int level(String code,double value,Map<String,Map<String,Object>>rules){
  var r=rules.get(code);if(r==null||((Number)r.get("enabled")).intValue()!=1)return 0;Map<String,Object>t=s.parse(r.get("threshold_json"));boolean lower=code.equals("R1")||code.equals("R2");
  if(lower){return value<num(t.get("red"))?3:value<num(t.get("orange"))?2:0;}
  return value>num(t.get("red"))?3:value>num(t.get("orange"))?2:value>num(t.get("yellow"))?1:0;
 }
 public synchronized int scan(){
  Map<String,Map<String,Object>>rules=new HashMap<>();for(var r:s.list("SELECT * FROM rule_config"))rules.put(r.get("code").toString(),r);int created=0;
  for(var index:s.list(q.latestFull())){
   long pid=((Number)index.get("product_id")).longValue();LocalDate end=LocalDate.parse(index.get("period_end").toString());List<Map<String,Object>>dims=s.parse(index.get("dim_scores"));
   Map<String,Double> metrics=new LinkedHashMap<>();metrics.put("R1",num(index.get("qi")));metrics.put("R2",dims.stream().mapToDouble(d->num(d.get("score"))).min().orElse(.55));
   var rates=s.one("SELECT COUNT(*) n,COALESCE(SUM(CASE WHEN a.fake_prob>=0.3 THEN 1 ELSE 0 END),0) fake,COALESCE(SUM(CASE WHEN r.review_time>=? AND a.fake_prob>=0.3 THEN 1 ELSE 0 END),0) fake7,COALESCE(SUM(CASE WHEN r.review_time>=? AND a.sentiment=-1 THEN 1 ELSE 0 END),0) neg7,COALESCE(SUM(CASE WHEN r.review_time>=? THEN 1 ELSE 0 END),0) n7,COALESCE(SUM(CASE WHEN r.review_time<? AND a.sentiment=-1 THEN 1 ELSE 0 END),0) neg28,COALESCE(SUM(CASE WHEN r.review_time<? THEN 1 ELSE 0 END),0) n28 FROM review r JOIN review_analysis a ON r.id=a.review_id WHERE r.product_id=? AND r.review_time>=? AND r.review_time<?",end.minusDays(6).atStartOfDay(),end.minusDays(6).atStartOfDay(),end.minusDays(6).atStartOfDay(),end.minusDays(6).atStartOfDay(),end.minusDays(6).atStartOfDay(),pid,end.minusDays(34).atStartOfDay(),end.plusDays(1).atStartOfDay());
   double n7=num(rates.get("n7")),n28=num(rates.get("n28")),prev=n28>0?num(rates.get("neg28"))/n28:0;
   // 七日差评率上升：两窗口都要有足够样本才判定；前窗用 2% 兜底，避免"前窗零差评"被当成无限上升。
   // 小样本（7 日内不足 5 条、28 日内不足 20 条）时相对变化没有统计意义，一律不告警。
   double r3=0.;
   if(n7>=5&&n28>=20){double base=Math.max(prev,0.02);r3=(num(rates.get("neg7"))/n7-base)/base;r3=Math.min(r3,2.);if(r3<0)r3=0;}
   metrics.put("R3",r3);
   // 刷评占比按最近 7 日窗口计：模板刷评的特征是"短期涌入"，全量分母会把新刷的评论稀释掉。
   metrics.put("R4",n7>=5?num(rates.get("fake7"))/n7:0.);
   var prior=s.list("SELECT dim_scores FROM quality_index WHERE product_id=? AND period_start<? ORDER BY period_start DESC,id DESC LIMIT 1",pid,index.get("period_start"));double drop=0;
   if(!prior.isEmpty()){List<Map<String,Object>> before=s.parse(prior.get(0).get("dim_scores"));for(var d:dims)for(var b:before)if(d.get("code").equals(b.get("code")))drop=Math.max(drop,num(b.get("score"))-num(d.get("score")));}metrics.put("R5",drop);
   List<Map<String,Object>>hits=new ArrayList<>();int highest=0;
   for(var entry:metrics.entrySet()){int lv=level(entry.getKey(),entry.getValue(),rules);if(lv>0){hits.add(Map.of("rule",entry.getKey(),"metric",entry.getValue(),"level",lv));highest=Math.max(highest,lv);}}
   if(hits.isEmpty())continue;
   var existing=s.list("SELECT * FROM alert WHERE product_id=? AND created_at>=? ORDER BY id DESC LIMIT 1",pid,LocalDateTime.now().minusDays(7));
   if(existing.isEmpty()){s.db.update("INSERT INTO alert(product_id,rule_code,level,metric_value,message) VALUES(?,?,?,?,?)",pid,"MULTI",highest,metrics.get("R1"),s.stringify(hits));created++;}
   else if(highest>((Number)existing.get(0).get("level")).intValue())s.db.update("UPDATE alert SET level=?,message=? WHERE id=?",highest,s.stringify(hits),existing.get(0).get("id"));
  }return created;
 }
 public Map<String,Object> list(String status,String level,String category,int page){String where=" WHERE 1=1";List<Object>a=new ArrayList<>();if(!status.isBlank()){where+=" AND a.status=?";a.add(status);}if(!level.isBlank()){where+=" AND a.level=?";a.add(level);}if(!category.isBlank()){where+=" AND p.category_id=?";a.add(category);}String from=" FROM alert a JOIN product p ON p.id=a.product_id";long count=s.count("SELECT COUNT(*)"+from+where,a.toArray());a.add(20);a.add(Math.max(0,page-1)*20);return Map.of("items",s.list("SELECT a.*,p.name product_name"+from+where+" ORDER BY a.level DESC,a.id DESC LIMIT ? OFFSET ?",a.toArray()),"total",count);}
 public void dispose(long id,int status,String note,String actor){if(status<1||status>3||note.isBlank()||note.length()>500)throw new IllegalArgumentException("请选择处置动作并填写1至500字意见");if(s.db.update("UPDATE alert SET status=?,disposal_note=?,disposed_by=?,disposed_at=CURRENT_TIMESTAMP WHERE id=? AND status=0",status,note,actor,id)!=1)throw new IllegalStateException("预警已被处置或不存在，请刷新");s.audit(actor,"dispose",Map.of("id",id,"status",status,"note",note));}
}
