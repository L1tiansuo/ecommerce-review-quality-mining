package com.qr.client;
import org.springframework.stereotype.Component;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.client.RestClient;
import java.util.*;
@Component public class AlgoClient {
 private final RestClient client;
 public AlgoClient(@Value("${qr.algo}")String url){client=RestClient.builder().baseUrl(url).requestFactory(new org.springframework.http.client.SimpleClientHttpRequestFactory(){{setConnectTimeout(5000);setReadTimeout(120000);}}).build();}
 @SuppressWarnings("unchecked") public Map<String,Object> call(String path,Object body){var response=client.post().uri(path).body(body).retrieve().body(Map.class);return (Map<String,Object>)response.get("data");}
 public Object health(){return client.get().uri("/v1/health").retrieve().body(Map.class);}
}
