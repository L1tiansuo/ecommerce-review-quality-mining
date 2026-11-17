package com.qr.repository;
import java.util.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.stereotype.Component;
import java.sql.Statement;
/** 显式参数化 SQL 与批处理，便于开发者检查聚合查询和优化索引。 */
@Component public class Store {
 public final JdbcTemplate db; public final ObjectMapper json;
 public Store(JdbcTemplate db,ObjectMapper json){this.db=db;this.json=json;}
 public List<Map<String,Object>> list(String sql,Object...args){return db.queryForList(sql,args);}
 public Map<String,Object> one(String sql,Object...args){var rows=list(sql,args);if(rows.isEmpty())throw new NoSuchElementException("资源不存在");return rows.get(0);}
 public long count(String sql,Object...args){return db.queryForObject(sql,Long.class,args);}
 public long insert(String sql,Object...args){var key=new GeneratedKeyHolder();db.update(c->{var p=c.prepareStatement(sql,new String[]{"id"});for(int i=0;i<args.length;i++)p.setObject(i+1,args[i]);return p;},key);return key.getKey().longValue();}
 public String stringify(Object value){try{return json.writeValueAsString(value);}catch(Exception e){throw new IllegalArgumentException(e);}}
 @SuppressWarnings("unchecked") public <T>T parse(Object value){try{return (T)json.readValue(value.toString(),Object.class);}catch(Exception e){throw new IllegalArgumentException("JSON 格式无效");}}
 public void audit(String actor,String action,Object detail){db.update("INSERT INTO audit_log(actor,action,detail) VALUES(?,?,?)",actor,action,stringify(detail));}
}
