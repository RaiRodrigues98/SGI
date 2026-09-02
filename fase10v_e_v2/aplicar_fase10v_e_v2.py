from pathlib import Path
from datetime import datetime
import ast, shutil, py_compile

ROOT = Path.cwd()
SERVICE = ROOT / "services" / "rodadas" / "finalizacao_rotativo.py"
DOMAIN = ROOT / "domain" / "exceptions.py"
R1 = "_encerrar_inventario_rotativo_apos_r1_sem_recontagem"
R2 = "_encerrar_inventario_rotativo_apos_r2"

PREREQS = {
    "A": "A R2 do inventário ROTATIVO ainda não foi concluída operacionalmente. Encerre todas as sessões e conclua todas as localizações previstas.",
    "B": "Não foi possível localizar a R1 do inventário ROTATIVO.",
    "C": "Não foi possível finalizar o inventário ROTATIVO.",
    "D": "Encerramento ROTATIVO pela R1 disponível somente para a primeira rodada.",
}
TARGET = "Existem sessões abertas na R1. Encerre todas antes de finalizar o inventário ROTATIVO."

def read(p):
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="latin-1")

def parse(t): return ast.parse(t, str(SERVICE))

def name(expr):
    if isinstance(expr, ast.Name): return expr.id
    if isinstance(expr, ast.Attribute): return expr.attr
    if isinstance(expr, ast.Call): return name(expr.func)
    return None

def funcs(t):
    return {n.name:n for n in parse(t).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}

def fn(t,n):
    f=funcs(t).get(n)
    if f is None: raise RuntimeError(f"Função ausente: {n}")
    return f

def raises(t, fn_name=None, kind=None):
    root=fn(t,fn_name) if fn_name else parse(t)
    out=[]
    for n in ast.walk(root):
        if not isinstance(n,ast.Raise) or n.exc is None: continue
        k=name(n.exc)
        if kind and k!=kind: continue
        if not kind and k!="HTTPException": continue
        status=detail=dsrc=None
        if isinstance(n.exc,ast.Call):
            for kw in n.exc.keywords:
                if kw.arg=="status_code": status=kw.value
                elif kw.arg=="detail": detail=kw.value
            if detail is None and n.exc.args: detail=n.exc.args[0]
        try: dval=ast.literal_eval(detail) if detail is not None else None
        except Exception: dval=None
        out.append((n,status,ast.get_source_segment(t,detail) if detail is not None else None,dval))
    return sorted(out,key=lambda x:x[0].lineno)

def http400(t, fn_name):
    return [x for x in raises(t,fn_name) if isinstance(x[1],ast.Constant) and x[1].value==400]

def brv(t, fn_name):
    return [x for x in raises(t,fn_name,"BusinessRuleViolation")]

def by_detail(t, fn_name, detail, typ):
    data=http400(t,fn_name) if typ=="http" else brv(t,fn_name)
    return [x for x in data if x[3]==detail]

def has_import(t,module,symbol):
    return any(isinstance(n,ast.ImportFrom) and (n.module or "")==module and symbol in [a.name for a in n.names] for n in parse(t).body)

def remove_http_import(t):
    if http_total(t)>0: return t
    nodes=[n for n in parse(t).body if isinstance(n,ast.ImportFrom) and (n.module or "")=="fastapi" and "HTTPException" in [a.name for a in n.names]]
    if len(nodes)!=1: raise RuntimeError("Import FastAPI/HTTPException não encontrado de forma única.")
    n=nodes[0]
    rem=[a for a in n.names if a.name!="HTTPException"]
    lines=t.splitlines()
    if rem:
        lines[n.lineno-1:n.end_lineno]=["from fastapi import "+", ".join(a.name if not a.asname else f"{a.name} as {a.asname}" for a in rem)]
    else:
        lines[n.lineno-1:n.end_lineno]=[]
    r="\n".join(lines)
    return r+("\n" if t.endswith("\n") else "")

def http_total(t):
    return sum(1 for x in raises(t) if isinstance(x[1],ast.Constant) and isinstance(x[1].value,int))

def state(t):
    # 10V-A/B/C must already be converted in R2.
    for k in ("A","B","C"):
        if len(by_detail(t,R2,PREREQS[k],"http"))!=0 or len(by_detail(t,R2,PREREQS[k],"brv"))!=1:
            return f"PREREQUISITO_10V_{k}_AUSENTE"
    if len(by_detail(t,R1,PREREQS["D"],"http"))!=0 or len(by_detail(t,R1,PREREQS["D"],"brv"))!=1:
        return "PREREQUISITO_10V_D_AUSENTE"
    th=by_detail(t,R1,TARGET,"http")
    tb=by_detail(t,R1,TARGET,"brv")
    if len(th)==1 and len(tb)==0: return "LEGADO_10V_E_V2"
    if len(th)==0 and len(tb)==1: return "MIGRADO_10V_E_V2"
    return "DESCONHECIDO"

if not SERVICE.exists() or not DOMAIN.exists():
    raise SystemExit("[ERRO] Arquivo necessário ausente.")

if "class BusinessRuleViolation" not in read(DOMAIN):
    raise SystemExit("[ERRO] BusinessRuleViolation ausente.")

criacao=read(ROOT/"services"/"rodadas"/"criacao.py")
if "HTTPException" in criacao or "fastapi" in criacao.lower() or "starlette" in criacao.lower():
    raise SystemExit("[ERRO] 10U-H não reconhecida.")

cur=read(SERVICE)
st=state(cur)
print(f"[0/8] Estado: {st}")
if st=="MIGRADO_10V_E_V2":
    print("[OK] Fase 10V-E v2 já aplicada.")
    raise SystemExit(0)
if st!="LEGADO_10V_E_V2":
    raise SystemExit("[ERRO] Baseline 10V-E v2 não reconhecido.")

target=by_detail(cur,R1,TARGET,"http")
if len(target)!=1:
    raise SystemExit("[ERRO] Alvo não encontrado de forma única.")
x=target[0]
before=http_total(cur)

backup=SERVICE.parent/(SERVICE.stem+"_backup_fase10v_e_v2_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".py")
shutil.copy2(SERVICE,backup)
print(f"[1/8] Backup: {backup.name}")

try:
    lines=cur.splitlines()
    indent=" "*x[0].col_offset
    repl=[f"{indent}raise BusinessRuleViolation(",f"{indent}    {x[2]}",f"{indent})"]
    lines[x[0].lineno-1:x[0].end_lineno]=repl
    patched="\n".join(lines)+("\n" if cur.endswith("\n") else "")
    patched=remove_http_import(patched)

    SERVICE.write_text(patched,encoding="utf-8")
    py_compile.compile(str(SERVICE),doraise=True)

    after=http_total(patched)
    if after!=before-1:
        raise RuntimeError(f"HTTPException não caiu exatamente 1: {before}->{after}")
    if len(by_detail(patched,R1,TARGET,"http"))!=0:
        raise RuntimeError("HTTPException alvo ainda presente.")
    if len(by_detail(patched,R1,TARGET,"brv"))!=1:
        raise RuntimeError("BusinessRuleViolation alvo não encontrado.")

    print("[2/8] [OK] 400 -> BusinessRuleViolation")
    print(f"[3/8] [OK] HTTPException: {before} -> {after}")
    print("[4/8] [OK] 10V-D preservada")
    print("[5/8] [OK] 10V-A/B/C preservadas")
    print("[6/8] [OK] sintaxe")
    print("[7/8] [OK] somente 1 alvo alterado")
    print("[8/8] [OK] Fase 10V-E v2 aplicada.")
except Exception:
    shutil.copy2(backup,SERVICE)
    print("[ERRO] Falha; baseline restaurado.")
    raise
