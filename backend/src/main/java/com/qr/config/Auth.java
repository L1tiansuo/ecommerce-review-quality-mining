package com.qr.config;
import com.qr.repository.Store;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.*;
import jakarta.servlet.http.*;
import javax.crypto.Mac;import javax.crypto.spec.SecretKeySpec;
import java.util.*;import java.nio.charset.StandardCharsets;
/** HS256 JWT，30 分钟超时；不把口令、密钥或个人标识写入日志。 */
@Component public class Auth implements HandlerInterceptor,WebMvcConfigurer {
 private final Store s;private final String secret;
 public Auth(Store s,@Value("${qr.jwt-secret}")String secret){this.s=s;this.secret=secret;}
 private String b64(byte[] v){return Base64.getUrlEncoder().withoutPadding().encodeToString(v);}
 private String sign(String value)throws Exception{Mac m=Mac.getInstance("HmacSHA256");m.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8),"HmacSHA256"));return b64(m.doFinal(value.getBytes(StandardCharsets.UTF_8)));}
 public String token(String username,String role){try{String h=b64("{\"alg\":\"HS256\",\"typ\":\"JWT\"}".getBytes(StandardCharsets.UTF_8));String p=b64(s.stringify(Map.of("sub",username,"role",role,"exp",System.currentTimeMillis()/1000+1800)).getBytes(StandardCharsets.UTF_8));return h+"."+p+"."+sign(h+"."+p);}catch(Exception e){throw new IllegalStateException(e);}}
 @Override public boolean preHandle(HttpServletRequest req,HttpServletResponse res,Object handler)throws Exception{
  String uri=req.getRequestURI();if(uri.equals("/api/v1/auth/login")||uri.equals("/api/v1/health"))return true;
  try{String header=req.getHeader("Authorization");if(header==null||!header.startsWith("Bearer "))throw new Exception();String[] t=header.substring(7).split("\\.");if(t.length!=3||!java.security.MessageDigest.isEqual(sign(t[0]+"."+t[1]).getBytes(),t[2].getBytes()))throw new Exception();Map<String,Object> p=s.parse(new String(Base64.getUrlDecoder().decode(t[1]),StandardCharsets.UTF_8));if(((Number)p.get("exp")).longValue()<System.currentTimeMillis()/1000)throw new Exception();var u=s.one("SELECT * FROM sys_user WHERE username=? AND enabled=1",p.get("sub"));req.setAttribute("actor",u.get("username"));req.setAttribute("role",u.get("role"));
   String role=u.get("role").toString();boolean write=!Set.of("GET","HEAD","OPTIONS").contains(req.getMethod());
   if((write&&role.equals("VIEWER"))||((uri.startsWith("/api/v1/admin")||uri.endsWith("/dispose"))&&!role.equals("ADMIN"))){error(res,403,"当前角色无权执行此操作");return false;}return true;
  }catch(Exception e){error(res,401,"请登录，或会话已过期");return false;}
 }
 private void error(HttpServletResponse r,int code,String message)throws Exception{r.setStatus(code);r.setContentType("application/json;charset=UTF-8");r.getWriter().write("{\"code\":"+code+",\"message\":\""+message+"\",\"data\":null}");}
 @Override public void addInterceptors(InterceptorRegistry registry){registry.addInterceptor(this).addPathPatterns("/api/**");}
}
