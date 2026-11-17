package com.qr.controller;
import org.springframework.web.bind.annotation.*;import org.springframework.http.*;import org.springframework.web.server.ResponseStatusException;import java.util.*;
@RestControllerAdvice public class Errors {
 @ExceptionHandler(Exception.class)public ResponseEntity<Object> handle(Exception e){int status=e instanceof ResponseStatusException r?r.getStatusCode().value():e instanceof NoSuchElementException?404:e instanceof IllegalStateException||e instanceof org.springframework.dao.DuplicateKeyException?409:e instanceof IllegalArgumentException||e instanceof org.springframework.dao.DataIntegrityViolationException?400:500;String message=status==500?"服务执行失败，请查看服务日志":e.getMessage();if(status==500)e.printStackTrace();Map<String,Object>body=new LinkedHashMap<>();body.put("code",status);body.put("message",message);body.put("data",null);return ResponseEntity.status(status).body(body);}
}
