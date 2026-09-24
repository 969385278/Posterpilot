import {createRoot} from 'react-dom/client';
import App from './App';
import type {CaseRecord} from './types';
import './styles.css';
const root=createRoot(document.getElementById('root')!);
root.render(<p className="loading">正在读取已保存的案例记录…</p>);
fetch('/case/record.json').then(async response=>{if(!response.ok)throw new Error('记录读取失败');return response.json() as Promise<CaseRecord>;}).then(record=>{
  if(record.schemaVersion!==1||record.history.length!==8)throw new Error('案例结构不匹配');
  root.render(<App record={record}/>);
}).catch(error=>root.render(<div className="loading"><h1>案例暂时无法打开</h1><p>{String(error)}</p><p>请通过本地启动命令访问，确认 public/case/record.json 存在。</p></div>));
