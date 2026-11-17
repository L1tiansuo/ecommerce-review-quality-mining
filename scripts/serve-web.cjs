/** 零依赖本地静态服务器：提供构建产物并代理API。生产部署使用nginx。 */
const http=require('http'),fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../web/dist');
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png','.svg':'image/svg+xml'};
http.createServer((req,res)=>{
 if(req.url.startsWith('/api/')||req.url.startsWith('/swagger-ui')||req.url.startsWith('/v3/')){
  const upstream=http.request({hostname:'127.0.0.1',port:8080,path:req.url,method:req.method,headers:req.headers},r=>{res.writeHead(r.statusCode,r.headers);r.pipe(res);});
  upstream.on('error',()=>{res.writeHead(502,{'Content-Type':'application/json;charset=utf-8'});res.end(JSON.stringify({code:502,message:'后端尚未启动，请检查日志',data:null}));});req.pipe(upstream);return;
 }
 let file;try{file=path.resolve(root,'.'+decodeURIComponent(req.url.split('?')[0]));}catch{res.writeHead(400);res.end();return;}
 if(file!==root&&!file.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
 if(!fs.existsSync(file)||!fs.statSync(file).isFile())file=path.join(root,'index.html');
 if(!fs.existsSync(file)){res.writeHead(503);res.end('Please build web first');return;}
 res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});fs.createReadStream(file).pipe(res);
}).listen(8088,'127.0.0.1',()=>console.log('Quality Lens: http://127.0.0.1:8088'));
