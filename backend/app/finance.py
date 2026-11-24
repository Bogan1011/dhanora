"""INR ledger. One transfer row represents both linked account movements atomically."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, func, case
from sqlalchemy.orm import Session
from app.auth import current_session, check_origin, now
from app.families import membership, lock_changes
from app.models import Account, Transaction, AuditLog

router = APIRouter(prefix="/api/v1/families/{family_id}/finance",tags=["finance"])
Scope = Literal["personal","shared"]
Kind = Literal["income","expense","transfer"]
CATEGORIES = {
    "income": ["Salary","Business","Rent","Interest","Investment income","Other income"],
    "expense": ["Groceries","Dining","Fuel","Transport","Shopping","Utilities","Rent","EMI","Insurance","Healthcare","Education","Entertainment","Travel","Subscriptions","Vehicle maintenance","Other expense"],
    "transfer": ["Transfer"],
}
def today():
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()

class AccountInput(BaseModel):
    name: str = Field(min_length=1,max_length=120)
    kind: Literal["bank","cash","wallet","credit_card"]
    scope: Scope = "personal"
    opening_paise: int = Field(default=0,ge=-10**12,le=10**12,strict=True)
    opening_date: date

class TransactionInput(BaseModel):
    request_id: UUID
    kind: Kind
    account_id: UUID
    destination_id: UUID | None = None
    amount_paise: int = Field(gt=0,le=10**12,strict=True)
    occurred_on: date
    category: str = Field(min_length=1,max_length=60)
    note: str = Field(default="",max_length=300)

def actor(db,request,family_id,write=False):
    check_origin(request,write=write)
    if write:
        lock_changes(db)
    _, user = current_session(request,db)
    return user,membership(db,family_id,user.id)

def accounts_query(family_id,user_id,scope):
    predicate = Account.private_owner_id == user_id if scope=="personal" else Account.private_owner_id.is_(None)
    return select(Account).where(Account.family_id==family_id,predicate)

def account_for(db,family_id,account_id,user_id):
    a = db.get(Account,account_id)
    if not a or a.family_id!=family_id or (a.private_owner_id is not None and a.private_owner_id!=user_id):
        raise HTTPException(404,"Account not found")
    return a

def allow_write(a,member):
    if a.private_owner_id is None and member.role=="viewer":
        raise HTTPException(403,"Shared workspace is read-only")

def info(a,balance):
    return {"id":str(a.id),"name":a.name,"kind":a.kind,"scope":"personal" if a.private_owner_id else "shared","opening_date":a.opening_date.isoformat(),"opening_paise":str(a.opening_paise),"balance_paise":str(balance)}

def transaction_info(t):
    return {"id":str(t.id),"kind":t.kind,"account_id":str(t.account_id),"destination_id":str(t.destination_id) if t.destination_id else None,"amount_paise":str(t.amount_paise),"occurred_on":t.occurred_on.isoformat(),"category":t.category,"note":t.note,"voided":t.voided_at is not None}

@router.post("/accounts",status_code=201)
def create_account(family_id:UUID,payload:AccountInput,request:Request):
    with Session(request.app.state.engine) as db:
        user,member=actor(db,request,family_id,True)
        if payload.scope=="shared" and member.role not in {"owner","admin"}:
            raise HTTPException(403,"Only owners and admins can create shared accounts")
        name=payload.name.strip()
        if not name or payload.opening_date>today():
            raise HTTPException(400,"Enter a name and a non-future opening date")
        if payload.kind=="credit_card" and payload.opening_paise>0:
            raise HTTPException(400,"Enter credit card debt as a negative opening balance")
        a=Account(family_id=family_id,private_owner_id=user.id if payload.scope=="personal" else None,name=name,kind=payload.kind,opening_paise=payload.opening_paise,opening_date=payload.opening_date)
        db.add(a)
        db.add(AuditLog(user_id=user.id,event="finance_account_created"))
        db.flush()
        result=info(a,a.opening_paise)
        db.commit()
        return result

@router.post("/transactions",status_code=201)
def add_transaction(family_id:UUID,payload:TransactionInput,request:Request):
    with Session(request.app.state.engine) as db:
        user,member=actor(db,request,family_id,True)
        a=account_for(db,family_id,payload.account_id,user.id)
        allow_write(a,member)
        if payload.occurred_on<a.opening_date or payload.occurred_on>today():
            raise HTTPException(400,"Date must be between account opening and today")
        if payload.category not in CATEGORIES[payload.kind]:
            raise HTTPException(400,"Select a valid category")
        if payload.kind=="transfer":
            if not payload.destination_id or payload.destination_id==a.id:
                raise HTTPException(400,"Choose two different accounts")
            dest=account_for(db,family_id,payload.destination_id,user.id)
            allow_write(dest,member)
            if dest.private_owner_id!=a.private_owner_id:
                raise HTTPException(400,"Transfers must stay within the same privacy scope")
            if payload.occurred_on<dest.opening_date:
                raise HTTPException(400,"Transfer predates the destination account")
        elif payload.destination_id is not None:
            raise HTTPException(400,"Destination is only allowed for transfers")
        existing=db.scalar(select(Transaction).where(Transaction.family_id==family_id,Transaction.created_by==user.id,Transaction.request_id==payload.request_id))
        if existing:
            if any(getattr(existing,k)!=getattr(payload,k) for k in ("kind","account_id","destination_id","amount_paise","occurred_on","category","note")):
                raise HTTPException(409,"Request ID already used")
            return transaction_info(existing)
        t=Transaction(family_id=family_id,created_by=user.id,**payload.model_dump())
        db.add(t)
        db.add(AuditLog(user_id=user.id,event="finance_transaction_created"))
        db.flush()
        result=transaction_info(t)
        db.commit()
        return result

@router.post("/transactions/{transaction_id}/void")
def void_transaction(family_id:UUID,transaction_id:UUID,request:Request):
    with Session(request.app.state.engine) as db:
        user,member=actor(db,request,family_id,True)
        t=db.get(Transaction,transaction_id)
        if not t or t.family_id!=family_id:
            raise HTTPException(404,"Transaction not found")
        a=account_for(db,family_id,t.account_id,user.id)
        allow_write(a,member)
        if a.private_owner_id is None and member.role not in {"owner","admin"} and t.created_by!=user.id:
            raise HTTPException(403,"Cannot void another member's transaction")
        if t.voided_at is None:
            t.voided_at=now()
            t.voided_by=user.id
            db.add(AuditLog(user_id=user.id,event="finance_transaction_voided"))
        db.commit()
        return {"status":"voided"}

@router.get("/overview")
def overview(family_id:UUID,request:Request,scope:Scope="personal"):
    with Session(request.app.state.engine) as db:
        db.connection(execution_options={"isolation_level":"REPEATABLE READ"})
        user,member=actor(db,request,family_id)
        accounts=db.scalars(accounts_query(family_id,user.id,scope).order_by(Account.created_at)).all()
        ids=[a.id for a in accounts]
        base=select(Transaction).where(Transaction.family_id==family_id,Transaction.account_id.in_(ids))
        active=(Transaction.family_id==family_id,Transaction.voided_at.is_(None),Transaction.occurred_on<=today())
        balances={a.id:a.opening_paise for a in accounts}
        source=db.execute(select(Transaction.account_id,func.sum(case((Transaction.kind=="income",Transaction.amount_paise),else_=-Transaction.amount_paise))).where(*active,Transaction.account_id.in_(ids)).group_by(Transaction.account_id)).all()
        for aid,value in source:
            balances[aid]+=int(value)
        dest=db.execute(select(Transaction.destination_id,func.sum(Transaction.amount_paise)).where(*active,Transaction.kind=="transfer",Transaction.destination_id.in_(ids)).group_by(Transaction.destination_id)).all()
        for aid,value in dest:
            balances[aid]+=int(value)
        start=today().replace(day=1)
        monthly=db.execute(select(Transaction.kind,Transaction.category,func.sum(Transaction.amount_paise)).where(*active,Transaction.account_id.in_(ids),Transaction.occurred_on>=start,Transaction.kind!="transfer").group_by(Transaction.kind,Transaction.category)).all()
        income=sum(int(v) for k,c,v in monthly if k=="income")
        expense=sum(int(v) for k,c,v in monthly if k=="expense")
        recent=db.scalars(base.order_by(Transaction.occurred_on.desc(),Transaction.created_at.desc(),Transaction.id.desc()).limit(100)).all()
        liquid=sum(balances[a.id] for a in accounts if a.kind!="credit_card")
        card=sum(balances[a.id] for a in accounts if a.kind=="credit_card")
        return {"scope":scope,"today":today().isoformat(),"month":start.isoformat()[:7],"accounts":[info(a,balances[a.id]) for a in accounts],"transactions":[transaction_info(t) for t in recent],"categories":CATEGORIES,"can_create_account":scope=="personal" or member.role in {"owner","admin"},"can_write":scope=="personal" or member.role!="viewer","summary":{"liquid_paise":str(liquid),"credit_card_net_paise":str(card),"income_paise":str(income),"expense_paise":str(expense),"cashflow_paise":str(income-expense),"expense_categories":[{"category":c,"amount_paise":str(v)} for k,c,v in monthly if k=="expense"]}}
