import { useEffect, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import {FamilyPanel, JoinFamily} from './FamilyPanel';

type Profile = {id: string; display_name: string; email: string; families: {id: string; name: string; role: string}[]};
type View = 'loading' | 'login' | 'dashboard' | 'error';
const base = '/api/v1/auth';
function App() {
  const [view, setView] = useState<View>('loading');
  const [profile, setProfile] = useState<Profile | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [familyId, setFamilyId] = useState('');
  const [joining, setJoining] = useState(false);
  const accept = (user: Profile) => {setProfile(user); setFamilyId(user.families[0]?.id ?? ''); setView('dashboard');};
  async function load() {
    try {
      const r = await fetch(base + '/me', {cache:'no-store'});
      if (r.ok) accept(await r.json());
      else if (r.status === 401) setView('login');
      else {setMessage('Open Dhanora using its configured private URL.'); setView('error');}
    } catch {setMessage('Cannot connect to Dhanora.'); setView('error');}
  }
  useEffect(() => {void load();}, []);
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage('');
    try {
      const r = await fetch(base + '/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email,password})});
      if (r.ok) {setPassword(''); await load();}
      else setMessage(r.status===429?'Too many attempts. Try again in five minutes.':r.status===401?'Invalid email or password.':'Unable to sign in. Check your private connection.');
    } catch {setMessage('Connection failed.');}
    finally {setBusy(false);}
  }
  async function logout() {
    setBusy(true); setMessage('');
    try {
      const r = await fetch(base + '/logout', {method:'POST'});
      if (!r.ok) throw Error('logout failed');
      setProfile(null); setFamilyId(''); setEmail(''); setView('login');
    } catch {setMessage('Could not sign out. Retry before leaving this device.');}
    finally {setBusy(false);}
  }
  if (view !== 'dashboard' || !profile) return <div className="auth-shell"><section className="auth-card">
    <div className="brand"><span className="mark">D</span>Dhanora</div>
    <p className="eyebrow">PRIVATE FINANCE WORKSPACE</p>
    <h1>{view==='login'?(joining?'Join your family':'Welcome back'):view==='loading'?'Connecting…':'Connection unavailable'}</h1>
    <p className="muted">Your wealth. Your life. Your control.</p>
    {view==='login' && !joining && <form onSubmit={login}>
      <label>Email address<input required type="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} maxLength={254}/></label>
      <label>Password<input required type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} maxLength={128}/></label>
      <button disabled={busy} type="submit">{busy?'Signing in…':'Sign in'}</button>
    </form>}
    {view==='login' && joining && <JoinFamily signedIn={false} onDone={()=>{setJoining(false);setMessage('Account created. Sign in with your invited email and new password.');}}/>}
    {view==='login' && <button className="secondary join-toggle" onClick={()=>{setJoining(!joining);setMessage('');}}>{joining?'Back to sign in':'Have an invitation?'}</button>}
    {message && <p role="alert" className="auth-error">{message}</p>}
    {view==='error' && <button onClick={()=>void load()}>Retry</button>}
    <p className="muted auth-foot">Self-hosted · Local-first · Development alpha</p>
  </section></div>;
  const family = profile.families.find(f=>f.id===familyId);
  return <div className="layout">
    <aside><div className="brand"><span className="mark">D</span>Dhanora</div><p className="muted">PRIVATE WORKSPACE</p><nav>{['Overview','Transactions','Budgets','Vehicles','Assets','Investments','Documents','Settings'].map((name,i)=><div key={name} className={i===0?'active':'locked'}>{name}{i!==0 && <small>Planned</small>}</div>)}</nav><footer>LOCAL FIRST · ALPHA</footer></aside>
    <main><header><div><p className="eyebrow">PERSONAL FINANCE OS</p><h1>Overview</h1><p className="muted">Welcome, {profile.display_name}</p></div><button className="secondary" disabled={busy} onClick={()=>void logout()}>Sign out</button></header>
    {message && <p role="alert" className="auth-error">{message}</p>}
    <section className="notice"><strong>Development workspace</strong><p>Authentication is active. Financial modules are not yet available. Use test data only.</p></section>
    <section className="metrics">{['Net worth','Monthly income','Monthly expenses','Safe daily spend'].map(name=><article key={name}><p>{name}</p><h2>—</h2><span>Not configured</span></article>)}</section>
    <section className="panel"><p className="eyebrow">YOUR WORKSPACE</p><h2>Family overview</h2>
      <label className="family-select">Family<select value={familyId} onChange={e=>setFamilyId(e.target.value)}>{profile.families.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select></label>
      <div className="system"><span>Signed in as</span><strong>{profile.email}</strong></div><div className="system"><span>Family role</span><strong>{family?.role ?? 'No membership'}</strong></div><div className="system"><span>Local AI</span><strong>Disabled</strong></div>
    </section>
    {family && <FamilyPanel key={family.id+family.role} familyId={family.id} role={family.role} userId={profile.id}/>}
    <section className="panel"><h2>Join another family</h2><JoinFamily signedIn onDone={()=>void load()}/></section>
    </main></div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
