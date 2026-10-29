// Local visual QA only. Synthetic values never enter the application data store.
import http from 'node:http';
import { createServer } from 'vite';
const groups = {
 'Banks': ['HDFCBANK','ICICIBANK','SBIN','AXISBANK','KOTAKBANK','INDUSINDBK'],
 'Information Technology': ['TCS','INFY','HCLTECH','WIPRO','TECHM','LTIM'],
 'Industrials': ['LT','SIEMENS','ABB','BEL','HAL','BHEL'],
 'Consumer': ['ITC','HINDUNILVR','NESTLEIND','TITAN','BRITANNIA','DABUR'],
 'Energy': ['RELIANCE','ONGC','NTPC','POWERGRID','BPCL','IOC'],
 'Healthcare': ['SUNPHARMA','CIPLA','DRREDDY','DIVISLAB','APOLLOHOSP','LUPIN'],
 'Automobiles': ['MARUTI','M&M','TATAMOTORS','BAJAJ-AUTO','EICHERMOT','HEROMOTOCO'],
};
const nodes = Object.entries(groups).flatMap(([industry,symbols])=>symbols.map(symbol=>({id:symbol,symbol,industry,observations_used:252})));
const edges=nodes.slice(1).map((node,i)=>{ const parent=nodes[i%6===5?0:Math.floor((i+1)/6)*6]; return {source:parent.id,target:node.id,symbol_a:parent.symbol,symbol_b:node.symbol,correlation:.35+(i%13)*.045,distance:.7+(i%5)*.1,paired_observations:252,edge_rank:i+1}; });
const now=new Date().toISOString();
const run={id:'DESIGN-QA',window_start:'2025-10-28',window_end:'2026-10-28',data_cutoff:now,computed_at:now,requested_symbol_count:nodes.length,included_symbol_count:nodes.length,edge_count:edges.length,is_connected:true,is_acyclic:true,implementation_version:'synthetic-preview',configuration:{},exclusions:[]};
const sentiment={label:'neutral',score:0,confidence:.77,probabilities:{positive:.15,neutral:.77,negative:.08},model:'QA fixture',chunks_analyzed:1,truncated:false};
const news={status:{configured:true,model_ready:true,running:false,stale:false,last_success_at:now,next_refresh_at:null,error:null,warnings:['DESIGN QA: synthetic articles, not real reports.'],sources:['Synthetic QA feed'],credits_reserved_today:0,daily_credit_budget:0,refresh_minutes:60,auto_refresh:false,can_refresh:false},articles:nodes.slice(0,8).map((node,i)=>({url:`https://example.com/qa/${i}`,title:`[SYNTHETIC] ${node.symbol} · quarterly operating review and sector context`,publisher:'DESIGN QA',published_at:now,retrieved_at:now,excerpt:'Synthetic content used only to verify layout.',sentiment,companies:{[node.symbol]:sentiment}}))};
const api=http.createServer((req,res)=>{
 res.setHeader('Access-Control-Allow-Origin','http://127.0.0.1:5181');res.setHeader('Access-Control-Allow-Headers','*');res.setHeader('Content-Type','application/json');
 if(req.method==='OPTIONS'){res.end();return;}
 const url=new URL(req.url,'http://127.0.0.1');let body;
 if(url.pathname.endsWith('/mst/latest'))body={run,nodes,edges,limitations:['Synthetic QA fixture']};
 else if(url.pathname.endsWith('/benchmark'))body={symbol:'NIFTY50',name:'Synthetic QA benchmark',latest_price:24000,previous_close:23900,change:100,change_percent:.42,as_of:'SYNTHETIC QA'};
 else if(url.pathname.endsWith('/rankings'))body={horizon:Number(url.searchParams.get('horizon')??20),run:{...run,signal_date:'SYNTHETIC QA',observation_basis:'closing'},results:nodes.map((n,i)=>({...n,divergence_value:((i*17)%51-25)/4,industry_percentile:(i*11)%100,interpretation:i%4===0?'strong':'normal'}))};
 else if(url.pathname.endsWith('/refresh-status'))body={enabled:false,market_open:false,running:false};
 else if(url.pathname.endsWith('/news'))body=news;
 else if(url.pathname.endsWith('/securities'))body=nodes.map(n=>({...n,company_name:n.symbol,latest_price:null,isin:n.id}));
 else {res.statusCode=503;body={detail:'DESIGN QA: this service is intentionally unavailable'};}
 res.end(JSON.stringify(body));
});
api.listen(5190,'127.0.0.1');
process.env.VITE_API_URL='http://127.0.0.1:5190/api/v1';
process.env.VITE_SUPABASE_URL='';process.env.VITE_SUPABASE_PUBLISHABLE_KEY='';
const server=await createServer({root:process.cwd(),server:{host:'127.0.0.1',port:5181,strictPort:true},plugins:[{name:'qa-banner',transformIndexHtml:html=>html.replace('</body>','<div style="position:fixed;bottom:0;right:0;background:var(--line-strong);color:var(--white);padding:var(--space-1) var(--space-3);z-index:9999;font:var(--text-tag) var(--font-data)">DESIGN QA / SYNTHETIC DATA / NOT LIVE</div></body>')}]});
await server.listen();server.printUrls();
const shutdown=async()=>{api.close();await server.close();process.exit(0);};process.on('SIGINT',shutdown);process.on('SIGTERM',shutdown);
