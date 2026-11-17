package com.qr.service;
import com.qr.repository.Store;import org.springframework.stereotype.Service;import java.util.*;
/** 查询层使用预计算指数，不在页面请求中重跑 NLP。 */
@Service public class QueryService {
 public final Store s;public QueryService(Store s){this.s=s;}
 public String latest(){return "SELECT * FROM (SELECT q.product_id,q.period_start,q.qi,q.grade,q.sample_size,q.param_version,ROW_NUMBER() OVER (PARTITION BY q.product_id ORDER BY q.period_start DESC,q.computed_at DESC,q.id DESC) rn FROM quality_index q) t WHERE t.rn=1";}
 /** 预警扫描需要 dim_scores 与 period_end，不能复用收窄后的 latest()。批量任务，走全列窗口函数即可。 */
 public String latestFull(){return "SELECT * FROM (SELECT q.*,ROW_NUMBER() OVER (PARTITION BY q.product_id ORDER BY q.period_start DESC,q.computed_at DESC,q.id DESC) rn FROM quality_index q) t WHERE t.rn=1";}
 public Map<String,Object> products(String keyword,String category,int page){
  String where=" WHERE p.status=1 AND p.name LIKE ?";List<Object>a=new ArrayList<>();a.add("%"+keyword+"%");if(!category.isBlank()){where+=" AND p.category_id=?";a.add(category);}
  long total=s.count("SELECT COUNT(*) FROM product p"+where,a.toArray());a.add(20);a.add(Math.max(0,page-1)*20);
  var rows=s.list("SELECT p.*,c.name category_name,su.name supplier_name,q.qi,q.grade,q.sample_size,q.param_version FROM product p JOIN category c ON c.id=p.category_id LEFT JOIN supplier su ON su.id=p.supplier_id LEFT JOIN ("+latest()+") q ON p.id=q.product_id"+where+" ORDER BY CASE WHEN p.scenario<>'' THEN 0 ELSE 1 END,p.id LIMIT ? OFFSET ?",a.toArray());return Map.of("items",rows,"total",total,"page",page);
 }
 private final Map<String,Object[]> cache=new java.util.concurrent.ConcurrentHashMap<>();
  private static final long TTL_MS=15000L;
  @SuppressWarnings("unchecked")
  public Map<String,Object> overview(String category,boolean refresh){
   Object[] hit=cache.get(category);
   if(!refresh&&hit!=null&&System.currentTimeMillis()-(Long)hit[0]<TTL_MS)return (Map<String,Object>)hit[1];
  String where=category.isBlank()?"":" WHERE p.category_id=?";Object[] args=category.isBlank()?new Object[]{}:new Object[]{category};
  var stats=s.one("SELECT COUNT(*) products,COALESCE(AVG(q.qi),0) average_qi FROM product p LEFT JOIN ("+latest()+") q ON q.product_id=p.id"+where,args);
  stats.putAll(counts());
  var trend=s.list("SELECT q.period_start,AVG(q.qi) qi,COUNT(*) products FROM quality_index q JOIN product p ON p.id=q.product_id"+where+" GROUP BY q.period_start ORDER BY q.period_start",args);
  var rank=s.list("SELECT c.name,AVG(q.qi) qi,COUNT(*) products FROM ("+latest()+") q JOIN product p ON p.id=q.product_id JOIN category c ON c.id=p.category_id"+where+" GROUP BY c.name ORDER BY qi ASC LIMIT 8",args);
  var out=Map.of("stats",stats,"trend",trend,"ranking",rank,"alerts",s.list("SELECT a.*,p.name product_name FROM alert a JOIN product p ON p.id=a.product_id ORDER BY a.created_at DESC LIMIT 8"),"disclosure","文本来自 yf_amazon；时间归一化至 2026-11-09；供应商为合成数据；S-01～05 为模拟剧本","period","按月预计算，图表展示月度趋势");
  cache.put(category,new Object[]{System.currentTimeMillis(),out});
  return out;
 }
  private volatile Map<String,Object> countsCache;
  private volatile long countsAt;
  private Map<String,Object> counts(){
   long now=System.currentTimeMillis();
   if(countsCache!=null&&now-countsAt<60000L)return countsCache;
   var c=s.one("SELECT (SELECT COUNT(*) FROM review) reviews,(SELECT COUNT(*) FROM alert WHERE status=0) pending,(SELECT COUNT(*) FROM alert WHERE created_at>=?) weekly_alerts,(SELECT COUNT(*) FROM alert WHERE status=0 AND created_at<?) overdue",java.sql.Timestamp.valueOf(java.time.LocalDateTime.now().minusDays(7)),java.sql.Timestamp.valueOf(java.time.LocalDateTime.now().minusDays(3)));
   countsCache=c;countsAt=now;return c;
  }
 public Map<String,Object> profile(long id){
  var p=s.one("SELECT p.*,c.name category_name,su.name supplier_name FROM product p JOIN category c ON c.id=p.category_id LEFT JOIN supplier su ON su.id=p.supplier_id WHERE p.id=?",id);
  var qs=s.list("SELECT * FROM quality_index WHERE product_id=? ORDER BY period_start DESC,computed_at DESC,id DESC",id);for(var q:qs)q.put("dims",s.parse(q.get("dim_scores")));
  var dist=s.list("SELECT a.sentiment,COUNT(*) n FROM review r JOIN review_analysis a ON r.id=a.review_id WHERE r.product_id=? GROUP BY a.sentiment",id);
  var comments=reviews(id,"","","",1);
  Map<String,Long> keywords=new TreeMap<>();for(var r:s.list("SELECT a.aspects_json FROM review r JOIN review_analysis a ON r.id=a.review_id WHERE r.product_id=? AND a.sentiment=-1",id)){List<Map<String,Object>> aspects=s.parse(r.get("aspects_json"));for(var x:aspects)keywords.merge(x.get("word").toString(),1L,Long::sum);}
  return Map.of("product",p,"indices",qs,"distribution",dist,"comments",comments,"keywords",keywords,"summary",qs.isEmpty()?"暂无分析结果，请到评论挖掘创建任务。":"质量指数依据六维方面情感加权计算；低样本量结果仅供参考。点击维度可查看评论证据。");
 }
 public Map<String,Object> reviews(long pid,String dimension,String sentiment,String fake,int page){
  String where=" WHERE 1=1";List<Object>a=new ArrayList<>();if(pid>0){where+=" AND r.product_id=?";a.add(pid);}if(!sentiment.isBlank()){where+=" AND a.sentiment=?";a.add(Integer.parseInt(sentiment));}if(!dimension.isBlank()){if(!Set.of("quality","appearance","logistics","service","value","package").contains(dimension))throw new IllegalArgumentException("未知维度");where+=" AND a.aspects_json LIKE ?";a.add("%\"dimension\":\""+dimension+"\"%");}if(fake.equals("1"))where+=" AND a.fake_prob>=0.3";if(fake.equals("0"))where+=" AND a.fake_prob<0.3";
  String from=" FROM review r LEFT JOIN review_analysis a ON a.review_id=r.id";long total=s.count("SELECT COUNT(*)"+from+where,a.toArray());a.add(20);a.add(Math.max(0,page-1)*20);
  var rows=s.list("SELECT r.*,a.sentiment,a.confidence,a.fake_prob,a.fake_reason,a.aspects_json,a.model_version"+from+where+" ORDER BY r.review_time DESC,r.id DESC LIMIT ? OFFSET ?",a.toArray());
  for(var r:rows){r.put("aspects",r.get("aspects_json")==null?List.of():s.parse(r.get("aspects_json")));r.put("hits",r.get("fake_reason")==null?List.of():s.parse(r.get("fake_reason")));}
  return Map.of("items",rows,"total",total,"page",page);
 }
}
