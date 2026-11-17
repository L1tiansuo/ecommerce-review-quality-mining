package com.qr;
import com.qr.repository.Store;
import com.qr.service.ImportService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.mock.web.MockMultipartFile;
import java.nio.charset.StandardCharsets;
import static org.junit.jupiter.api.Assertions.*;
/** 真实H2集成测试，专门覆盖驱动返回多个生成列及导入原子性。 */
@SpringBootTest(properties={"qr.seed=./no-seed-in-tests","spring.datasource.url=jdbc:h2:mem:unit;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1"})
@Transactional
@org.springframework.test.context.TestExecutionListeners(listeners={org.springframework.test.context.support.DependencyInjectionTestExecutionListener.class,org.springframework.test.context.transaction.TransactionalTestExecutionListener.class},mergeMode=org.springframework.test.context.TestExecutionListeners.MergeMode.REPLACE_DEFAULTS)
class StoreIntegrationTest {
 @Autowired Store s;@Autowired ImportService imports;
 @Test void generatedKeyIsIdOnly(){long id=s.insert("INSERT INTO import_batch(file_name,status) VALUES(?,?)","key-test.csv",1);assertEquals(id,((Number)s.one("SELECT * FROM import_batch WHERE id=?",id).get("id")).longValue());}
 @Test void excessiveErrorsRollbackValidRows()throws Exception{
  s.db.update("INSERT INTO category VALUES(?,?)",90001,"测试");s.db.update("INSERT INTO product(id,name,category_id) VALUES(?,?,?)",90001,"测试商品",90001);
  String csv="product_id,content_raw,rating,review_time\n90001,质量非常好且满意,5,2026-01-01 12:00:00\n-1,错误商品测试,5,2026-01-01 12:00:00\n-1,错误商品测试,5,2026-01-01 12:00:00\n";
  var result=imports.upload(new MockMultipartFile("file","sample.csv","text/csv",csv.getBytes(StandardCharsets.UTF_8)),"test");
  assertEquals(2,((Number)result.get("status")).intValue());assertEquals(0,s.count("SELECT COUNT(*) FROM review WHERE product_id=90001"));
 }
 @Test void validImportMasksAndPersists()throws Exception{
  s.db.update("INSERT INTO category VALUES(?,?)",90002,"测试");s.db.update("INSERT INTO product(id,name,category_id) VALUES(?,?,?)",90002,"测试商品",90002);
  String csv="product_id,content_raw,rating,review_time\n90002,质量很好联系13812345678,5,2026-01-01 12:00:00\n";
  var result=imports.upload(new MockMultipartFile("file","valid.csv","text/csv",csv.getBytes(StandardCharsets.UTF_8)),"test");
  assertEquals(1,((Number)result.get("success")).intValue());assertFalse(s.one("SELECT * FROM review WHERE product_id=90002").get("content_raw").toString().contains("13812345678"));
 }
}
