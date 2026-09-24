const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 page.setDefaultTimeout(10000);
 const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 const out=path.resolve(__dirname,'../.runtime/qa');fs.mkdirSync(out,{recursive:true});
 const base=process.env.LEARN_URL||'http://127.0.0.1:8879';
 const passed=[];
 async function check(name,fn){await fn();passed.push(name);console.log('PASS '+name);}
 async function shot(name){await page.screenshot({path:path.join(out,name+'.png')});}
 async function fit(desktop=true){const d=await page.evaluate(()=>({w:innerWidth,h:innerHeight,sw:document.documentElement.scrollWidth,sh:document.documentElement.scrollHeight}));assert(d.sw<=d.w,'horizontal overflow');if(desktop)assert(d.sh<=d.h,'desktop should fit one screen');}
 async function mode(id){await page.locator('.main-tabs [data-id="'+id+'"]').click();}
 async function runLab(){await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/lab')),page.locator('#lab-form button.primary').click()]);await page.locator('#lab-jump').waitFor();}
 try{
  await page.goto(base);await page.locator('.workbench').waitFor();
  await check('one canvas with adjacent prose and no old question blocks',async()=>{
   await fit();assert.equal(await page.locator('.study-canvas').count(),1);assert.equal(await page.locator('.plain-explanation').count(),1);
   const text=await page.locator('main').innerText();for(const old of ['必须要有吗？','如果没有这一步','为什么这样就能解决','有没有更简单的做法'])assert(!text.includes(old));
   await shot('canvas-overview');
  });
  await check('drill down directly through canvas nodes',async()=>{
   for(const id of ['production','rag','filter','filter-status'])await page.locator('.diagram-node[data-action="node"][data-id="'+id+'"]').click();
   assert.match(await page.locator('h1').innerText(),/审核状态/);
   await page.locator('.diagram-node[data-action="line"][data-id="3"]').click();
   assert.match(await page.locator('.line-explanation').innerText(),/审核/);
   await shot('canvas-leaf');
  });
  await check('keyboard code selection and source comparison',async()=>{
   await page.locator('.code-line[data-id="4"]').focus();await page.keyboard.press('Enter');
   assert.equal(await page.locator('.code-line.selected').getAttribute('data-line'),'4');
   await page.getByRole('button',{name:'对照仓库源码',exact:true}).click();await page.locator('.code-meta').waitFor();assert.match(await page.locator('.code-meta').innerText(),/retriever.py/);
   await page.getByRole('button',{name:'初级伪代码',exact:true}).click();
  });
  await check('collapsed quiz and saved learning progress',async()=>{
   await page.locator('.quiet-detail summary').first().click();await page.locator('[data-action="quiz"][data-id="1"]').click();await page.locator('.quiz-feedback').waitFor({state:'visible'});assert.match(await page.locator('.quiz-feedback').innerText(),/理解正确/);
   await page.getByRole('button',{name:'我已理解这一节',exact:true}).click();await page.reload();await page.getByRole('button',{name:'✓ 已理解（点击取消）',exact:true}).waitFor();
  });
  await check('search and planned work still identifiable',async()=>{
   await page.locator('#search').fill('改期');await page.locator('.nav-node[data-id="activities"]').click();assert.match(await page.locator('.canvas-caption').innerText(),/规划中/);await page.locator('#search').fill('');
  });
  await check('all 39 lessons retain a single prose explanation',async()=>{
   const ids=await page.evaluate(async()=>{const r=await(await fetch('/api/catalog')).json();return r.nodes.map(n=>n.id);});
   for(const id of ids){await page.evaluate(id=>location.hash=id,id);await page.waitForFunction(id=>document.querySelector('.canvas-location button:last-of-type')?.dataset.id===id,id);assert.equal(await page.locator('.plain-explanation').count(),1);assert((await page.locator('.plain-explanation').innerText()).length>45);await fit();}
  });
  await check('learning path, glossary and definition dialog',async()=>{
   await page.locator('#learning-path').selectOption('rag');await page.getByRole('button',{name:'下一节',exact:true}).click();assert.match(await page.locator('h1').innerText(),/检索问题/);
   await mode('glossary');assert(await page.locator('.glossary-item').count()>15);
   await mode('learn');await page.evaluate(()=>location.hash='system');await page.locator('.term[data-id="Agent"]').click();await page.locator('#term-dialog').waitFor({state:'visible'});await page.getByRole('button',{name:'知道了'}).click();
  });
  await check('runtime playback, seek and automatic human pause in canvas',async()=>{
   await mode('runtime');await page.locator('#step-jump').waitFor();await page.locator('[data-action="next"]').click();assert.equal(await page.locator('#step-jump').inputValue(),'1');await page.locator('[data-action="prev"]').click();assert.equal(await page.locator('#step-jump').inputValue(),'0');
   const wait=await page.evaluate(async()=>{const r=await(await fetch('/api/trace')).json();return r.steps.findIndex(s=>s.wait);});
   await page.locator('#step-jump').selectOption(String(wait-1));await page.locator('#speed').selectOption('500');await page.locator('[data-action="play"]').click();await page.waitForTimeout(800);
   assert.equal(await page.locator('#step-jump').inputValue(),String(wait));assert.equal(await page.locator('[data-action="play"]').innerText(),'播放');
   assert.match(await page.locator('.diagram-node.current').textContent(),/等待用户反馈/);await fit();await shot('canvas-runtime');
  });
  await check('editable scenario and folded provenance',async()=>{
   await page.locator('[name="scenario"]').selectOption('missing_signal');await page.locator('[name="title"]').fill('周末画展');await Promise.all([page.waitForResponse(r=>r.url().includes('/api/trace')),page.locator('#trace-form button').click()]);
   const total=await page.locator('#step-jump option').count();await page.locator('#step-jump').selectOption(String(total-1));await page.getByText('追踪数据来源',{exact:true}).click();await page.locator('#provenance').selectOption('brief');await page.locator('.provenance').waitFor({state:'visible'});assert.match(await page.locator('.provenance').innerText(),/周末画展/);
  });
  await check('real function stack, source highlight, output and comparison',async()=>{
   await mode('lab');await runLab();await page.locator('#lab-jump').selectOption('4');assert.match(await page.locator('.diagram').textContent(),/_expand_roles/);assert.equal(await page.locator('.code-line.selected').count(),1);await page.locator('[data-action="out"]').click();assert.match(await page.locator('.panel-heading').innerText(),/return/);
   await page.locator('[name="include_candidates"]').check();await runLab();await page.locator('.lab-summary summary').click();assert.match(await page.locator('.lab-summary').innerText(),/B-待审核/);assert.match(await page.locator('.lab-summary').innerText(),/上次输出/);await page.locator('.lab-summary summary').click();await page.locator('#lab-jump').selectOption('4');await fit();await shot('canvas-lab');
  });
  await check('five experiments, two desktop sizes and narrow-screen reading',async()=>{
   for(const id of ['similarity','scores','budget','revision']){await page.locator('#lab-choice').selectOption(id);if(id==='scores')await page.locator('[name="vision_score"]').fill('0');await runLab();assert(await page.locator('#lab-jump option').count()>5);await fit();}
   await page.setViewportSize({width:1920,height:1080});await fit();await mode('learn');await page.evaluate(()=>location.hash='system');await page.locator('.diagram-node[data-id="production"]').waitFor();await fit();await shot('canvas-wide');
   await page.setViewportSize({width:390,height:844});await fit(false);await page.getByRole('button',{name:'打开模块菜单'}).click();await page.locator('.nav-node[data-id="intake"]').click();await fit(false);await shot('canvas-mobile');
  });
  await check('no browser errors',async()=>assert.deepEqual(errors,[]));
  fs.writeFileSync(path.join(out,'browser-results.json'),JSON.stringify({passed,errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
