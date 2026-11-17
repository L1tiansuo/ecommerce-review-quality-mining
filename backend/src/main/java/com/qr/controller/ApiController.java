package com.qr.controller;
import com.qr.repository.Store;import com.qr.service.*;import com.qr.config.Auth;import com.qr.client.AlgoClient;
import org.springframework.web.bind.annotation.*;import org.springframework.web.multipart.MultipartFile;import org.springframework.http.*;import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import jakarta.servlet.http.HttpServletRequest;import java.util.*;import java.io.*;import java.nio.charset.StandardCharsets;import java.time.*;
import com.lowagie.text.*;import com.lowagie.text.pdf.*;
/** 统一 REST 契约。所有动态 SQL 字段均白名单，值使用绑定参数。 */
@RestController @RequestMapping("/api/v1") public class ApiController {
 private final Store s;private final QueryService q;private final ImportService imports;private final MiningService mining;private final AlertService alerts;private final Auth auth;private final AlgoClient algo;
 public ApiController(Store s,QueryService q,ImportService imports,MiningService mining,AlertService alerts,Auth auth,AlgoClient algo){this.s=s;this.q=q;this.imports=imports;this.mining=mining;this.alerts=alerts;this.auth=auth;this.algo=algo;}
 private Map<String,Object> ok(Object data){return Map.of("code",0,"message","ok","data",data);}
 private String actor(HttpServletRequest r){return r.getAttribute("actor").toString();}
 @PostMapping("/auth/login") public Object login(@RequestBody Map<String,String> p){
  if(!"2026".equals(p.get("captcha")))throw new IllegalArgumentException("演示验证码为 2026");
  var users=s.list("SELECT * FROM sys_user WHERE username=? AND enabled=1",p.get("username"));if(users.isEmpty()||!new BCryptPasswordEncoder().matches(p.getOrDefault("password",""),users.get(0).get("password_hash").toString()))throw new org.springframework.web.server.ResponseStatusException(HttpStatus.UNAUTHORIZED,"账号或口令错误");var u=users.get(0);return ok(Map.of("token",auth.token(u.get("username").toString(),u.get("role").toString()),"username",u.get("username"),"role",u.get("role")));
 }
 @GetMapping("/health") public Object health(){return ok(Map.of("status","ok","database",s.count("SELECT COUNT(*) FROM product")));}
 @GetMapping("/system/health")public Object system(){Object a;try{a=algo.health();}catch(Exception e){a=Map.of("status","unavailable","message",e.getMessage());}return ok(Map.of("algorithm",a,"database","ok","now",LocalDateTime.now().toString()));}
 @GetMapping("/dashboard/overview")public Object overview(@RequestParam(defaultValue="")String category,@RequestParam(defaultValue="false")boolean refresh){return ok(q.overview(category,refresh));}
 @GetMapping("/products")public Object products(@RequestParam(defaultValue="")String keyword,@RequestParam(defaultValue="")String category,@RequestParam(defaultValue="1")int page){return ok(q.products(keyword,category,page));}
 @GetMapping("/products/{id}/profile")public Object profile(@PathVariable long id,HttpServletRequest r){s.audit(actor(r),"view_product",Map.of("product_id",id));return ok(q.profile(id));}
 @GetMapping({"/reviews","/products/{id}/aspects"})public Object reviews(@PathVariable(required=false)Long id,@RequestParam(defaultValue="0")long product_id,@RequestParam(defaultValue="")String dimension,@RequestParam(defaultValue="")String sentiment,@RequestParam(defaultValue="")String fake,@RequestParam(defaultValue="1")int page){return ok(q.reviews(id==null?product_id:id,dimension,sentiment,fake,page));}
 @GetMapping("/dictionaries")public Object dictionaries(){return ok(Map.of("categories",s.list("SELECT * FROM category ORDER BY name"),"suppliers",s.list("SELECT * FROM supplier ORDER BY id"),"params",s.list("SELECT * FROM param_snapshot ORDER BY created_at DESC"),"rules",s.list("SELECT * FROM rule_config ORDER BY code")));}
 @PostMapping("/imports")public Object upload(@RequestParam("file")MultipartFile file,HttpServletRequest r)throws Exception{return ok(imports.upload(file,actor(r)));}
 @GetMapping("/imports")public Object batches(){var rows=s.list("SELECT * FROM import_batch ORDER BY id DESC LIMIT 100");for(var b:rows)b.put("error_rows",b.get("errors")==null?java.util.List.of():s.parse(b.get("errors")));return ok(rows);}
 @PostMapping("/imports/{id}/undo")public Object undo(@PathVariable long id,HttpServletRequest r){imports.undo(id,actor(r));return ok(Map.of("status","撤销成功，请重算受影响商品"));}
 @GetMapping("/mining/tasks")public Object tasks(){return ok(s.list("SELECT * FROM mining_task ORDER BY id DESC LIMIT 100"));}
 @PostMapping("/mining/tasks")public Object task(@RequestBody Map<String,Object>p,HttpServletRequest r){
  int scope=((Number)p.getOrDefault("scope_type",3)).intValue();if(scope<1||scope>3)throw new IllegalArgumentException("任务范围应为1/2/3");String value=p.getOrDefault("scope_value","").toString();if(scope!=3&&value.isBlank())throw new IllegalArgumentException("请填写商品或品类编号");
  // 固化词表内容到任务记录，之后在线编辑词表也不改变该任务的输入。
  p.put("dictionary_snapshot",s.parse(s.one("SELECT value_json FROM config_store WHERE code='aspect-dict'").get("value_json")));
  long id=s.insert("INSERT INTO mining_task(scope_type,scope_value,params,created_by) VALUES(?,?,?,?)",scope,value,s.stringify(p),actor(r));mining.run(id,p);return ok(Map.of("id",id));
 }
 @PostMapping("/mining/tasks/{id}/cancel")public Object cancel(@PathVariable long id){if(s.db.update("UPDATE mining_task SET cancelled=1 WHERE id=? AND status IN(0,1)",id)==0)throw new IllegalStateException("任务已经结束");return ok(Map.of("requested",true));}
 @GetMapping("/alerts")public Object alerts(@RequestParam(defaultValue="")String status,@RequestParam(defaultValue="")String level,@RequestParam(defaultValue="")String category,@RequestParam(defaultValue="1")int page){return ok(alerts.list(status,level,category,page));}
 @PostMapping("/alerts/scan")public Object scan(){return ok(Map.of("created",alerts.scan()));}
 @PostMapping("/alerts/{id}/dispose")public Object dispose(@PathVariable long id,@RequestBody Map<String,Object>p,HttpServletRequest r){alerts.dispose(id,((Number)p.getOrDefault("status",0)).intValue(),p.getOrDefault("note","").toString(),actor(r));return ok(Map.of("disposed",true));}
 @GetMapping("/admin/{kind}")public Object admin(@PathVariable String kind){return ok(switch(kind){case "products"->s.list("SELECT * FROM product ORDER BY id DESC LIMIT 200");case "categories"->s.list("SELECT * FROM category ORDER BY id");case "suppliers"->s.list("SELECT * FROM supplier ORDER BY id");case "rules"->s.list("SELECT * FROM rule_config ORDER BY code");case "aspect-dict"->s.parse(s.one("SELECT value_json FROM config_store WHERE code='aspect-dict'").get("value_json"));case "users"->s.list("SELECT id,username,role,enabled FROM sys_user ORDER BY id");case "audit"->s.list("SELECT * FROM audit_log ORDER BY id DESC LIMIT 200");case "params"->s.list("SELECT * FROM param_snapshot ORDER BY created_at DESC");default->throw new NoSuchElementException("管理资源不存在");});}
 @PostMapping("/admin/{kind}")public Object save(@PathVariable String kind,@RequestBody Map<String,Object>p,HttpServletRequest r){
  switch(kind){
   case "products":if(p.getOrDefault("name","").toString().isBlank())throw new IllegalArgumentException("商品名称必填");s.db.update("INSERT INTO product(id,name,category_id,supplier_id,scenario) VALUES(?,?,?,?,?)",p.get("id"),p.get("name"),p.get("category_id"),p.get("supplier_id"),"");break;
   case "categories":case "suppliers":s.db.update("INSERT INTO "+(kind.equals("categories")?"category":"supplier")+"(id,name) VALUES(?,?)",p.get("id"),p.get("name"));break;
   case "rules":{
    String code=p.get("code").toString();if(!Set.of("R1","R2","R3","R4","R5").contains(code))throw new IllegalArgumentException("规则编号无效");Map<String,Object> t=(Map<String,Object>)p.get("threshold_json");double red=((Number)t.get("red")).doubleValue(),orange=((Number)t.get("orange")).doubleValue();boolean lower=Set.of("R1","R2").contains(code);if((lower&&red>=orange)||(!lower&&(red<=orange||orange<=((Number)t.get("yellow")).doubleValue())))throw new IllegalArgumentException("分级阈值顺序不正确");s.db.update("UPDATE rule_config SET threshold_json=?,enabled=? WHERE code=?",s.stringify(t),p.getOrDefault("enabled",1),code);break;}
   case "aspect-dict":if(!(p.get("dimensions") instanceof java.util.List)||p.getOrDefault("version","").toString().isBlank())throw new IllegalArgumentException("词表须包含version和dimensions");s.db.update("UPDATE config_store SET value_json=? WHERE code='aspect-dict'",s.stringify(p));break;
   case "params":{
    String version=p.getOrDefault("version","").toString();Map<String,Object> params=(Map<String,Object>)p.get("params");Map<String,Number>w=(Map<String,Number>)params.get("weights");if(version.isBlank()||!w.keySet().equals(Set.of("quality","appearance","logistics","service","value","package"))||Math.abs(w.values().stream().mapToDouble(Number::doubleValue).sum()-1)>1e-8||w.values().stream().anyMatch(n->n.doubleValue()<0))throw new IllegalArgumentException("版本号必填，六维权重合计须为1");s.db.update("INSERT INTO param_snapshot(version,params_json) VALUES(?,?)",version,s.stringify(params));break;}
   case "users":{
    String role=p.getOrDefault("role","VIEWER").toString(),password=p.getOrDefault("password","").toString();if(!Set.of("ADMIN","ANALYST","VIEWER").contains(role)||password.length()<10)throw new IllegalArgumentException("角色无效或口令不足10位");s.db.update("INSERT INTO sys_user(username,password_hash,role) VALUES(?,?,?)",p.get("username"),new BCryptPasswordEncoder().encode(password),role);break;}
   default:throw new IllegalArgumentException("不支持的管理操作");
  }s.audit(actor(r),"configure_"+kind,kind.equals("users")?Map.of("username",p.get("username")):p);return ok(Map.of("saved",true));
 }
 private String cell(Object value){String t=value==null?"":value.toString();if(!t.isEmpty()&&"=+-@".indexOf(t.charAt(0))>=0)t="'"+t;return "\""+t.replace("\"","\"\"")+"\"";}
 @GetMapping("/reports/export")public ResponseEntity<byte[]> export(@RequestParam(defaultValue="products")String type,@RequestParam(defaultValue="csv")String format,@RequestParam(defaultValue="0")long product_id,@RequestParam(defaultValue="")String dimension,@RequestParam(defaultValue="")String sentiment,@RequestParam(defaultValue="")String fake,HttpServletRequest r)throws Exception{
  java.util.List<Map<String,Object>>rows;
  if(type.equals("alerts"))rows=s.list("SELECT a.*,p.name product_name FROM alert a JOIN product p ON p.id=a.product_id ORDER BY a.id DESC");
  else if(type.equals("reviews")){rows=new ArrayList<>();int page=1;while(true){Map<String,Object>pageData=q.reviews(product_id,dimension,sentiment,fake,page++);var items=(java.util.List<Map<String,Object>>)pageData.get("items");if(items.isEmpty())break;rows.addAll(items);}}
  else rows=s.list("SELECT p.name,q.* FROM product p JOIN quality_index q ON q.product_id=p.id ORDER BY p.id,q.period_start");
  s.audit(actor(r),"export",Map.of("type",type,"format",format,"rows",rows.size()));byte[]bytes;String mime;
  if(format.equals("pdf")){
   var out=new ByteArrayOutputStream();Document doc=new Document(PageSize.A4.rotate());PdfWriter.getInstance(doc,out);doc.open();BaseFont bf=BaseFont.createFont("STSong-Light","UniGB-UCS2-H",BaseFont.NOT_EMBEDDED);Font font=new Font(bf,9);doc.add(new Paragraph("商品评论质量报告 | "+type+" | "+LocalDateTime.now(),font));doc.add(new Paragraph("文本来自 yf_amazon，时间归一化，供应商与剧本商品为模拟。",font));
   for(var row:rows)doc.add(new Paragraph(row.toString(),font));doc.close();bytes=out.toByteArray();mime="application/pdf";
  }else{StringBuilder csv=new StringBuilder("\uFEFF");if(!rows.isEmpty()){var keys=rows.get(0).keySet();csv.append(String.join(",",keys)).append(",generated_at\r\n");for(var row:rows){for(String key:keys)csv.append(cell(row.get(key))).append(',');csv.append(cell(LocalDateTime.now())).append("\r\n");}}bytes=csv.toString().getBytes(StandardCharsets.UTF_8);mime="text/csv;charset=UTF-8";}
  return ResponseEntity.ok().header("Content-Disposition","attachment; filename=quality-report."+(format.equals("pdf")?"pdf":"csv")).contentType(MediaType.parseMediaType(mime)).body(bytes);
 }
}
