import {useEffect,useState,type FormEvent} from 'react';
type Member={id:string;display_name:string;role:string};
type Invite={id:string;email:string;role:string;status:string;expires_at:string};
async function api(path:string, method='GET', body?:unknown) {
  const r=await fetch('/api/v1'+path,{method,cache:'no-store',...(body===undefined?{}:{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})});
  const data=await r.json();
  if(!r.ok) throw Error(typeof data.detail==='string'?data.detail:'Request failed');
  return data;
}
export function JoinFamily({signedIn,onDone}:{signedIn:boolean;onDone:()=>void}) {
  const [code,setCode]=useState(''),[name,setName]=useState(''),[password,setPassword]=useState(''),[msg,setMsg]=useState(''),[busy,setBusy]=useState(false);
  async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();setBusy(true);setMsg('');try{await api('/invitations/accept','POST',{code:code.trim(),...(signedIn?{}:{display_name:name,password})});setCode('');setPassword('');setMsg('Invitation accepted.');onDone();}catch(e){setMsg(e instanceof Error?e.message:'Unable to join');}finally{setBusy(false);}}
  return <form className="stack" onSubmit={submit}><label>Invitation code<input autoComplete="off" required minLength={43} maxLength={43} value={code} onChange={e=>setCode(e.target.value)}/></label>
    {!signedIn&&<><p className="muted">New accounts use the email specified by the inviter. If you already have an account, sign in first.</p><label>Display name<input required maxLength={120} value={name} onChange={e=>setName(e.target.value)}/></label><label>New password<input required type="password" autoComplete="new-password" minLength={12} maxLength={128} value={password} onChange={e=>setPassword(e.target.value)}/></label></>}
    <button disabled={busy}>Accept invitation</button>{msg&&<p role="status">{msg}</p>}</form>;
}
export function FamilyPanel({familyId,role,userId}:{familyId:string;role:string;userId:string}){
  const [members,setMembers]=useState<Member[]>([]),[invites,setInvites]=useState<Invite[]>([]),[email,setEmail]=useState(''),[inviteRole,setInviteRole]=useState('member'),[code,setCode]=useState(''),[msg,setMsg]=useState(''),[busy,setBusy]=useState(false);
  const manager=role==='owner'||role==='admin', root='/families/'+familyId;
  const roles=role==='owner'?['admin','member','viewer']:['member','viewer'];
  const manageable=(m:Member)=>manager&&m.id!==userId&&m.role!=='owner'&&(role==='owner'||m.role!=='admin');
  async function refresh(){setMembers(await api(root+'/members'));if(manager)setInvites(await api(root+'/invitations'));}
  useEffect(()=>{let live=true;Promise.all([api(root+'/members'),manager?api(root+'/invitations'):Promise.resolve([])]).then(([m,i])=>{if(live){setMembers(m);setInvites(i);}}).catch(e=>{if(live)setMsg(e.message);});return()=>{live=false;};},[familyId,manager]);
  async function run(action:()=>Promise<void>){setBusy(true);setMsg('');try{await action();await refresh();}catch(e){setMsg(e instanceof Error?e.message:'Request failed');}finally{setBusy(false);}}
  function invite(e:FormEvent<HTMLFormElement>){e.preventDefault();void run(async()=>{const result=await api(root+'/invitations','POST',{email,role:inviteRole});setCode(result.code);setEmail('');});}
  return <section className="panel"><p className="eyebrow">FAMILY MANAGEMENT</p><h2>Members</h2>
    {msg&&<p className="auth-error" role="alert">{msg}</p>}
    {members.map(m=><div className="member-row" key={m.id}><div><strong>{m.display_name}</strong><p className="muted">{m.role}{m.id===userId?' · You':''}</p></div>{manageable(m)&&<div className="member-actions"><select aria-label={'Role for '+m.display_name} value={m.role} disabled={busy} onChange={e=>{const next=e.target.value;if(window.confirm('Change this member’s role?'))void run(async()=>{await api(root+'/members/'+m.id,'PATCH',{role:next});});}}>{roles.map(r=><option key={r}>{r}</option>)}</select><button className="secondary" disabled={busy} onClick={()=>{if(window.confirm('Remove this member from the family?'))void run(async()=>{await api(root+'/members/'+m.id,'DELETE');});}}>Remove</button></div>}</div>)}
    {manager&&<><h3>Invite a family member</h3><form className="invite-form" onSubmit={invite}><label>Email<input type="email" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)}/></label><label>Role<select value={inviteRole} onChange={e=>setInviteRole(e.target.value)}>{roles.map(r=><option key={r}>{r}</option>)}</select></label><button disabled={busy}>Create invitation</button></form>
    {code&&<div className="notice"><strong>One-time invitation code</strong><p>Share privately with the intended recipient. Expires after 24 hours. It cannot be retrieved later.</p><input readOnly value={code} aria-label="Invitation code" onFocus={e=>e.target.select()}/><button className="secondary" onClick={()=>setCode('')}>Hide code</button></div>}
    <h3>Invitations</h3>{invites.length===0&&<p className="muted">No invitations yet.</p>}{invites.map(i=><div className="member-row" key={i.id}><div><strong>{i.email}</strong><p className="muted">{i.role} · {i.status} · {new Date(i.expires_at).toLocaleString()}</p></div>{i.status==='pending'&&<button className="secondary" disabled={busy} onClick={()=>void run(async()=>{await api(root+'/invitations/'+i.id,'DELETE');setCode('');})}>Revoke</button>}</div>)}</>}
  </section>;
}
