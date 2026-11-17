package com.qr.service;
import com.qr.repository.Store;import org.springframework.stereotype.Service;import org.springframework.web.multipart.MultipartFile;
import org.apache.commons.csv.*;import java.io.*;import java.nio.charset.StandardCharsets;import java.time.*;import java.util.*;
import org.springframework.transaction.support.TransactionTemplate;import org.springframework.jdbc.datasource.DataSourceTransactionManager;
/** 小批量 CSV 原子提交。失败率超过一半时整批回滚，仅保留失败报告。 */
@Service public class ImportService {
 private final Store s;public ImportService(Store s){this.s=s;}
 public static String mask(String text){return text.replaceAll("(?<!\\d)1[3-9]\\d{9}(?!\\d)","[已脱敏]").replaceAll("(?<!\\d)\\d{17}[\\dXx](?!\\d)","[已脱敏]").replaceAll("[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}","[已脱敏]");}
 public Map<String,Object> upload(MultipartFile file,String actor)throws Exception{
  if(file.isEmpty())throw new IllegalArgumentException("请选择 UTF-8 CSV 文件");
  long batch=s.insert("INSERT INTO import_batch(file_name,operator) VALUES(?,?)",file.getOriginalFilename(),actor);
  List<Map<String,Object>> errors=new ArrayList<>();List<Object[]> values=new ArrayList<>();Set<String>seen=new HashSet<>();int total=0,skipped=0;
  try(var reader=new BufferedReader(new InputStreamReader(file.getInputStream(),StandardCharsets.UTF_8))){
   reader.mark(1);if(reader.read()!=0xFEFF)reader.reset();
   try(var csv=CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build().parse(reader)){
    for(var r:csv){total++;try{
     if(total>50000)throw new IllegalArgumentException("每批最多五万行，请拆分文件");
     long pid=Long.parseLong(r.get("product_id"));if(s.count("SELECT COUNT(*) FROM product WHERE id=?",pid)==0)throw new IllegalArgumentException("商品编号不存在");
     String original=r.get("content_raw");String raw=mask(original);String clean=raw.replaceAll("<[^>]+>","").replaceAll("\\s+"," ").strip();if(clean.length()<5||raw.length()>2000)throw new IllegalArgumentException("正文长度应为5至2000字符");
     String rt=r.get("rating");Integer rating=rt.isBlank()?null:Integer.parseInt(rt);if(rating!=null&&(rating<1||rating>5))throw new IllegalArgumentException("评分必须为1至5");
     LocalDateTime time=LocalDateTime.parse(r.get("review_time").replace(' ','T'));if(time.isAfter(LocalDateTime.now()))throw new IllegalArgumentException("评论时间不得晚于当前时间");
     String key=pid+":"+clean;boolean duplicate=!seen.add(key)||s.count("SELECT COUNT(*) FROM review WHERE product_id=? AND content_clean=?",pid,clean)>0;
     int source=r.isMapped("source_type")?Integer.parseInt(r.get("source_type")):2;if(source<1||source>3)throw new IllegalArgumentException("来源类型必须为1/2/3");
     values.add(new Object[]{pid,raw,clean,rating,time,source,batch,duplicate?1:0,raw.equals(original)?0:1});if(duplicate)skipped++;
    }catch(Exception ex){errors.add(Map.of("line",r.getRecordNumber()+1,"reason",ex.getMessage()==null?"字段缺失或类型错误":ex.getMessage()));}}
   }
   int success=values.size();boolean failed=total==0||errors.size()>.5*total;
   if(!failed)new TransactionTemplate(new DataSourceTransactionManager(s.db.getDataSource())).execute(st->{s.db.batchUpdate("INSERT INTO review(product_id,content_raw,content_clean,rating,review_time,source_type,batch_id,dup_flag,mask_flag) VALUES(?,?,?,?,?,?,?,?,?)",values);return null;});
   s.db.update("UPDATE import_batch SET total=?,success=?,failed=?,skipped=?,status=?,errors=? WHERE id=?",total,failed?0:success,errors.size(),skipped,failed?2:1,s.stringify(errors),batch);
   s.audit(actor,"import",Map.of("batch",batch,"rows",total));return s.one("SELECT * FROM import_batch WHERE id=?",batch);
  }catch(Exception e){s.db.update("UPDATE import_batch SET status=2,errors=? WHERE id=?",s.stringify(List.of(Map.of("line",0,"reason",e.getMessage()==null?"文件解析失败":e.getMessage()))),batch);throw new IllegalArgumentException("导入失败，请查看批次错误明细");}
 }
 public void undo(long id,String actor){
  new TransactionTemplate(new DataSourceTransactionManager(s.db.getDataSource())).execute(st->{s.one("SELECT * FROM import_batch WHERE id=? AND status=1 FOR UPDATE",id);var pids=s.list("SELECT DISTINCT product_id FROM review WHERE batch_id=?",id);s.db.update("DELETE FROM review WHERE batch_id=?",id);for(var p:pids)s.db.update("DELETE FROM quality_index WHERE product_id=?",p.get("product_id"));s.db.update("UPDATE import_batch SET status=3 WHERE id=?",id);s.audit(actor,"undo_import",Map.of("batch",id,"indices_invalidated",true));return null;});
 }
}
