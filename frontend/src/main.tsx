import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Status = 'checking' | 'ready' | 'offline';
function App() {
  const [status, setStatus] = useState<Status>('checking');
  useEffect(() => {
    const controller = new AbortController();
    fetch('/ready', {signal: controller.signal, cache: 'no-store'})
      .then(r => setStatus(r.ok ? 'ready' : 'offline'))
      .catch(() => { if (!controller.signal.aborted) setStatus('offline'); });
    return () => controller.abort();
  }, []);
  return <div className="layout">
    <aside><div className="brand"><span className="mark">D</span>Dhanora</div><p className="muted">PRIVATE WORKSPACE</p><nav>{['Overview','Transactions','Budgets','Vehicles','Assets','Investments','Documents','Settings'].map((name,i)=><div key={name} className={i===0?'active':'locked'}>{name}{i!==0 && <small>Planned</small>}</div>)}</nav><footer>LOCAL FIRST · ALPHA</footer></aside>
    <main><header><div><p className="eyebrow">PERSONAL FINANCE OS</p><h1>Overview</h1><p className="muted">Your wealth. Your life. Your control.</p></div><span className={'status '+status}>{status==='ready'?'System ready':status==='checking'?'Connecting':'Service unavailable'}</span></header>
    <section className="notice"><strong>Development workspace</strong><p>Authentication and family access are not enabled. No personal financial data should be entered yet.</p></section>
    <section className="metrics">{['Net worth','Monthly income','Monthly expenses','Safe daily spend'].map(name=><article key={name}><p>{name}</p><h2>—</h2><span>Not configured</span></article>)}</section>
    <section className="panel"><p className="eyebrow">FOUNDATION</p><h2>Welcome to Dhanora.</h2><p className="muted">This is the first working interface. Your accounts, financial insights and family assets will appear here as modules are implemented.</p><div className="system"><span>Backend & database</span><strong>{status}</strong></div><div className="system"><span>Local AI</span><strong>Disabled</strong></div><div className="system"><span>Authentication</span><strong>Planned</strong></div></section>
    </main></div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
