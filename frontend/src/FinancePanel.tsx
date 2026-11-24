import {useEffect,useState,useRef,type FormEvent} from 'react';
type Scope='personal'|'shared';
type Kind='income'|'expense'|'transfer';
type Account={id:string;name:string;kind:string;opening_date:string;opening_paise:string;balance_paise:string};
type Tx={id:string;kind:Kind;account_id:string;destination_id:string|null;amount_paise:string;occurred_on:string;category:string;note:string;voided:boolean};
type Data={today:string;month:string;accounts:Account[];transactions:Tx[];categories:Record<Kind,string[]>;can_create_account:boolean;can_write:boolean;summary:{liquid_paise:string;credit_card_net_paise:string;income_paise:string;expense_paise:string;cashflow_paise:string;expense_categories:{category:string;amount_paise:string}[]}};
export type FinancePage='Overview'|'Accounts'|'Transactions';
const money=(value:string)=>{const n=BigInt(value),a=n<0n?-n:n;return (n<0n?'−':'')+'₹'+(a/100n).toLocaleString('en-IN')+'.'+(a%100n).toString().padStart(2,'0');};
function paise(value:string,negative=false){
  const v=value.trim();
  if(!/^-?\d+(\.\d{1,2})?$/.test(v)||(!negative&&v.startsWith('-')))throw Error('Enter an amount with up to two decimal places.');
  const [whole,fraction='']=v.replace(/^-/,'').split('.');
  const n=BigInt(whole)*100n+BigInt(fraction.padEnd(2,'0'));
  if(n>1000000000000n)throw Error('Amount exceeds the supported limit.');
  return Number(v.startsWith('-')?-n:n);
}
const kinds:Record<string,string>={bank:'Bank account',cash:'Cash',wallet:'Wallet',credit_card:'Credit card'};
async function api(path:string,method='GET',body?:unknown,signal?:AbortSignal){
  const r=await fetch(path,{method,signal,cache:'no-store',...(body===undefined?{}:{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})});
  const d=await r.json();
  if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Request failed');
  return d;
}
export function FinancePanel({familyId,page}:{familyId:string;page:FinancePage}){
  const [scope,setScope]=useState<Scope>('personal');
  return <><div className="finance-toolbar"><div><p className="eyebrow">FINANCIAL WORKSPACE</p><strong>{scope==='personal'?'Your private accounts':'Shared family accounts'}</strong></div><div className="scope-toggle"><button className={scope==='personal'?'':'secondary'} onClick={()=>setScope('personal')}>Personal</button><button className={scope==='shared'?'':'secondary'} onClick={()=>setScope('shared')}>Shared</button></div></div><Workspace key={familyId+scope} familyId={familyId} scope={scope} page={page}/></>;
}
function Workspace({familyId,scope,page}:{familyId:string;scope:Scope;page:FinancePage}){
  const root='/api/v1/families/'+familyId+'/finance';
  const [data,setData]=useState<Data|null>(null),[msg,setMsg]=useState(''),[busy,setBusy]=useState(false);
  const [name,setName]=useState(''),[accountKind,setAccountKind]=useState('bank'),[opening,setOpening]=useState('0'),[openingDate,setOpeningDate]=useState('');
  const [kind,setKind]=useState<Kind>('expense'),[source,setSource]=useState(''),[dest,setDest]=useState(''),[amount,setAmount]=useState(''),[category,setCategory]=useState('Groceries'),[note,setNote]=useState(''),[date,setDate]=useState('');
  const retry=useRef<{fingerprint:string;id:string}|null>(null);
  const alive=useRef(true);
  async function refresh(){const d:Data=await api(root+'/overview?scope='+scope);if(alive.current){setData(d);setDate(old=>old||d.today);setOpeningDate(old=>old||d.today);setSource(old=>d.accounts.some(a=>a.id===old)?old:d.accounts[0]?.id||'');}}
  useEffect(()=>{alive.current=true;void refresh().catch(e=>{if(alive.current)setMsg(e.message);});return()=>{alive.current=false;};},[]);
  async function run(action:()=>Promise<void>){setBusy(true);setMsg('');try{await action();await refresh();}catch(e){if(alive.current)setMsg(e instanceof Error?e.message:'Request failed');}finally{if(alive.current)setBusy(false);}}
  function addAccount(e:FormEvent<HTMLFormElement>){e.preventDefault();void run(async()=>{await api(root+'/accounts','POST',{name,kind:accountKind,scope,opening_paise:paise(opening,true),opening_date:openingDate});setName('');setOpening('0');});}
  function addTransaction(e:FormEvent<HTMLFormElement>){e.preventDefault();void run(async()=>{const payload={kind,account_id:source,destination_id:kind==='transfer'?dest:null,amount_paise:paise(amount),occurred_on:date,category,note};const fingerprint=JSON.stringify(payload);if(retry.current?.fingerprint!==fingerprint)retry.current={fingerprint,id:crypto.randomUUID()};await api(root+'/transactions','POST',{...payload,request_id:retry.current.id});retry.current=null;setAmount('');setNote('');});}
  if(!data)return <section className="panel">{msg?<><p role="alert">{msg}</p><button onClick={()=>void refresh().catch(e=>setMsg(e.message))}>Retry</button></>:<p>Loading financial workspace…</p>}</section>;
  const names=Object.fromEntries(data.accounts.map(a=>[a.id,a.name]));
  const s=data.summary;
  const sorted=[...s.expense_categories].sort((a,b)=>BigInt(a.amount_paise)>BigInt(b.amount_paise)?-1:1);
  return <>{msg&&<p role="alert" className="auth-error">{msg}</p>}
    {page==='Overview'&&<><section className="metrics">{[['Liquid balance',s.liquid_paise],['Income this month',s.income_paise],['Expenses this month',s.expense_paise],['Net monthly cash flow',s.cashflow_paise]].map(([label,value])=><article key={label}><p>{label}</p><h2 className="amount">{money(value)}</h2><span>{label==='Liquid balance'?'Bank, cash & wallets':data.month}</span></article>)}</section>
    <section className="panel"><p className="eyebrow">ACCOUNT SUMMARY</p><h2>Your balances</h2><p className="muted">Credit card net balance: {money(s.credit_card_net_paise)} (negative means debt). Net worth is not calculated yet.</p>{data.accounts.length===0?<p className="muted">Create an account in Accounts to begin.</p>:data.accounts.map(a=><div className="system" key={a.id}><span>{a.name} · {kinds[a.kind]}</span><strong>{money(a.balance_paise)}</strong></div>)}</section>
    <section className="panel"><h2>Spending by category</h2>{sorted.length===0?<p className="muted">No expenses this month.</p>:sorted.map(c=><div className="spend-row" key={c.category}><div className="system"><span>{c.category}</span><strong>{money(c.amount_paise)}</strong></div><progress value={Number(BigInt(c.amount_paise)*10000n/BigInt(s.expense_paise))/100} max={100}/></div>)}</section></>}
    {page==='Accounts'&&<><section className="panel"><h2>Accounts</h2>{data.accounts.length===0&&<p className="muted">No accounts yet.</p>}{data.accounts.map(a=><div className="member-row" key={a.id}><div><strong>{a.name}</strong><p className="muted">{kinds[a.kind]} · Opened {a.opening_date} · Opening balance {money(a.opening_paise)}</p></div><strong className="amount">{money(a.balance_paise)}</strong></div>)}</section>
    {data.can_create_account&&<section className="panel"><h2>Add account</h2><form className="finance-form" onSubmit={addAccount}><label>Account name<input required maxLength={120} value={name} onChange={e=>setName(e.target.value)} placeholder="e.g. Salary account"/></label><label>Account type<select value={accountKind} onChange={e=>setAccountKind(e.target.value)}>{Object.entries(kinds).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label><label>Opening balance (₹)<input required inputMode="decimal" value={opening} onChange={e=>setOpening(e.target.value)}/></label><label>Opening date<input required type="date" max={data.today} value={openingDate} onChange={e=>setOpeningDate(e.target.value)}/></label><p className="muted">Enter debt as a negative balance for credit cards. Opening balances are not counted as income. Transactions must be on or after this date.</p><button disabled={busy}>Create account</button></form></section>}</>}
    {page==='Transactions'&&<>{data.can_write&&<section className="panel"><h2>Record transaction</h2>{!data.accounts.length?<p className="muted">Create an account first.</p>:<form className="finance-form" onSubmit={addTransaction}>
    <label>Transaction type<select value={kind} onChange={e=>{const k=e.target.value as Kind;setKind(k);setCategory(data.categories[k][0]);setDest('');}}>{['income','expense','transfer'].map(k=><option key={k}>{k}</option>)}</select></label><label>{kind==='transfer'?'From account':'Account'}<select required value={source} onChange={e=>{setSource(e.target.value);if(dest===e.target.value)setDest('');}}>{data.accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
    {kind==='transfer'&&<label>To account<select required value={dest} onChange={e=>setDest(e.target.value)}><option value="">Select destination</option>{data.accounts.filter(a=>a.id!==source).map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>}
    <label>Amount (₹)<input required inputMode="decimal" placeholder="0.00" value={amount} onChange={e=>setAmount(e.target.value)}/></label><label>Transaction date<input required type="date" max={data.today} value={date} onChange={e=>setDate(e.target.value)}/></label><label>Category<select value={category} onChange={e=>setCategory(e.target.value)}>{data.categories[kind].map(c=><option key={c}>{c}</option>)}</select></label><label className="full">Description (optional)<input maxLength={300} value={note} onChange={e=>setNote(e.target.value)}/></label><button disabled={busy}>Save transaction</button></form>}</section>}
    <section className="panel"><h2>Transaction history</h2><p className="muted">Latest 100 records. Transfers are excluded from income and expense totals.</p>{data.transactions.length===0&&<p className="muted">No transactions yet.</p>}<div className="transaction-table">{data.transactions.map(t=><div key={t.id} className={'member-row '+(t.voided?'voided':'')}><div><strong>{t.note||t.category}</strong><p className="muted">{t.occurred_on} · {names[t.account_id]}{t.destination_id?' → '+names[t.destination_id]:''} · {t.kind}{t.voided?' · Voided':''}</p></div><div className="member-actions"><strong className={t.kind==='income'?'income':t.kind==='expense'?'expense':''}>{t.kind==='income'?'+':t.kind==='expense'?'−':''}{money(t.amount_paise)}</strong>{data.can_write&&!t.voided&&<button className="secondary" disabled={busy} onClick={()=>{if(window.confirm('Void this transaction? It will remain in history but no longer affect totals.'))void run(async()=>{await api(root+'/transactions/'+t.id+'/void','POST');});}}>Void</button>}</div></div>)}</div></section></>}
  </>;
}
