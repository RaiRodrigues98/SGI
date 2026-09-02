"""Suíte E2E do inventário ROTATIVO do SGI.

Uso (PowerShell):
  $env:SGI_BASE_URL='http://127.0.0.1:8000'
  $env:SGI_LOGIN='dev'
  $env:SGI_PASSWORD='SUA_SENHA'
  python teste_rotativo_e2e.py

A suíte cria inventários TESTE-E2E-* e usa somente a API pública do SGI.
Não apaga dados e não altera código/configurações do sistema.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

BASE = os.getenv("SGI_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
LOGIN = os.getenv("SGI_LOGIN", "")
PASSWORD = os.getenv("SGI_PASSWORD", "")
CLIENTE_ID = int(os.getenv("SGI_CLIENTE_ID", "53"))
CLIENTE = os.getenv("SGI_CLIENTE", "endress")
ARMAZEM = os.getenv("SGI_ARMAZEM", "ML007")
LOCALIZACAO = os.getenv("SGI_LOCALIZACAO", "01PLAQUETA").strip().upper()
TIMEOUT = float(os.getenv("SGI_TIMEOUT", "30"))


class ApiError(RuntimeError):
    def __init__(self, status: int, data: Any, method: str, path: str):
        self.status = status
        self.data = data
        self.method = method
        self.path = path
        super().__init__(f"HTTP {status} {method} {path}: {data}")


class API:
    def __init__(self):
        self.token = ""

    def request(self, method: str, path: str, body: Any = None, expected=(200, 201)) -> Any:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        raw = None
        if body is not None:
            raw = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(BASE + path, data=raw, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = json.loads(r.read().decode("utf-8") or "null")
                if r.status not in expected:
                    raise ApiError(r.status, data, method, path)
                return data
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode("utf-8") or "null")
            except Exception:
                data = str(e)
            if e.code in expected:
                return data
            raise ApiError(e.code, data, method, path)

    def login(self):
        if not LOGIN or not PASSWORD:
            raise RuntimeError("Defina SGI_LOGIN e SGI_PASSWORD antes de executar.")
        r = self.request("POST", "/auth/login", {"login": LOGIN, "senha": PASSWORD})
        self.token = r["access_token"]


api = API()


@dataclass
class Report:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def ok(self, name: str):
        self.passed.append(name)
        print(f"[PASS] {name}")

    def fail(self, name: str, exc: Exception | str):
        msg = f"{name}: {exc}"
        self.failed.append(msg)
        print(f"[FAIL] {msg}")


R = Report()


def assert_true(value, msg):
    if not value:
        raise AssertionError(msg)


def expect_error(fn, statuses=(400, 409, 422), contains: str | None = None):
    try:
        fn()
    except ApiError as e:
        assert_true(e.status in statuses, f"status inesperado: {e.status}; retorno={e.data}")
        if contains:
            text = json.dumps(e.data, ensure_ascii=False).upper()
            assert_true(contains.upper() in text, f"mensagem não contém {contains!r}: {e.data}")
        return e
    raise AssertionError("A operação deveria ter sido bloqueada, mas foi aceita.")


def unique_code(tag: str) -> str:
    # CodigoInventario no banco aceita no máximo 30 caracteres.
    # Mantém o identificador legível e ainda suficientemente único para E2E.
    tag_curta = "".join(ch for ch in tag.upper() if ch.isalnum())[:8]
    sufixo = str(int(time.time() * 1000))[-10:]
    return f"E2E-{tag_curta}-{sufixo}"[:30]


def create_inventory(tag: str):
    r = api.request("POST", "/inventarios", {
        "codigo_inventario": unique_code(tag),
        "tipo": "ROTATIVO",
        "cliente_id": CLIENTE_ID,
        "cliente": CLIENTE,
        "descricao": f"E2E automático ROTATIVO - {tag}",
        "armazem": ARMAZEM,
    })
    return r["id_inventario"], r["id_rodada"]


def add_scope(iid: int):
    return api.request("POST", f"/inventarios/{iid}/escopo/localizacoes", {"localizacoes": [LOCALIZACAO]})


def snapshot(iid: int):
    return api.request("POST", f"/inventarios/{iid}/snapshot", {})


def analysis(iid: int):
    return api.request("GET", f"/inventarios/{iid}/analise-rotativo")


def snapshot_items(iid: int):
    a = analysis(iid)
    items = [x for x in a.get("itens", []) if str(x.get("localizacao", "")).strip().upper() == LOCALIZACAO]
    assert_true(items, f"Nenhum item encontrado na análise para {LOCALIZACAO}")
    return items


def start(iid: int, rid: int):
    return api.request("POST", "/localizacoes/iniciar", {"id_inventario": iid, "id_rodada": rid, "localizacao": LOCALIZACAO})


def count(sid: int, item: dict, qty: float):
    return api.request("POST", "/contagens", {
        "id_sessao": sid,
        "codigo": str(item["codigo"]),
        "lote": item.get("lote") or "",
        "quantidade": qty,
    })


def close(sid: int, empty=False):
    return api.request("POST", "/localizacoes/encerrar", {"id_sessao": sid, "localizacao_vazia": empty})


def next_round(iid: int):
    return api.request("POST", f"/inventarios/{iid}/rodadas/proxima")


def preview(iid: int):
    return api.request("GET", f"/inventarios/{iid}/rodadas/proxima-preview")


def decision(iid: int, rid: int, item: dict, kind: str, justification=None):
    body = {
        "id_rodada": rid,
        "localizacao": LOCALIZACAO,
        "codigo": str(item["codigo"]),
        "lote": item.get("lote") or "",
        "decisao": kind,
    }
    if justification is not None:
        body["justificativa"] = justification
    return api.request("POST", f"/inventarios/{iid}/decisoes-rotativo", body)


def final_result(iid: int):
    return api.request("GET", f"/inventarios/{iid}/resultado-final")


def qty_stock(item: dict) -> float:
    for k in ("qtd_estoque", "quantidade_estoque", "saldo_inventario"):
        if k in item and item[k] is not None:
            return float(item[k])
    raise AssertionError(f"Campo de estoque não localizado no item: {item}")


def count_all_correct(iid: int, rid: int):
    items = snapshot_items(iid)
    s = start(iid, rid)
    sid = s["id_sessao"]
    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid, it, q)
    close(sid, empty=False)
    return items, sid


def prepare(tag: str):
    iid, r1 = create_inventory(tag)
    add_scope(iid)
    s = snapshot(iid)
    assert_true(int(s.get("registros_snapshot", 0)) > 0, "snapshot vazio")
    items = snapshot_items(iid)
    return iid, r1, items



def run(name, fn):
    try:
        fn()
        R.ok(name)
    except Exception as e:
        R.fail(name, str(e))



# ============================================================
# ESTÁGIO 3 - ESTADOS LIMITE E CONSISTÊNCIA
# ============================================================

def test_snapshot_ausente_bloqueia_finalizacao():
    iid, r1 = create_inventory("NOSNAP")
    add_scope(iid)

    # Sem snapshot: não deve ser possível consolidar/finalizar normalmente.
    s = start(iid, r1)
    sid = s["id_sessao"]
    close(sid, empty=True)

    expect_error(
        lambda: next_round(iid),
        statuses=(400, 409),
        contains="SNAPSHOT"
    )


def test_reabertura_substitui_sessao_anterior():
    iid, r1, items = prepare("REOPEN")
    target = items[0]

    s1 = start(iid, r1)
    sid1 = s1["id_sessao"]
    count(sid1, target, qty_stock(target) + 1)

    # Demais itens corretos para isolar o alvo.
    for it in items[1:]:
        q = qty_stock(it)
        if q > 0:
            count(sid1, it, q)
    close(sid1)

    # Reabre a mesma localização. A configuração atual do ambiente de teste
    # já foi validada manualmente como habilitada.
    s2 = start(iid, r1)
    sid2 = s2["id_sessao"]
    assert_true(sid2 != sid1, f"reabertura reutilizou sessão encerrada: {sid1}")

    # Nova sessão corrige o alvo e deve substituir a anterior na consolidação.
    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid2, it, q)
    close(sid2)

    # Se a sessão antiga ainda fosse consolidada, haveria divergência.
    fin = next_round(iid)
    pr = fin["proxima_rodada"]
    assert_true(
        pr.get("status_inventario") == "FINALIZADO",
        f"sessão antiga interferiu na consolidação após reabertura: {fin}"
    )


def test_finalizacao_repetida_nao_duplica_resultado():
    iid, r1, items = prepare("IDEMFIN")
    count_all_correct(iid, r1)

    first = next_round(iid)
    assert_true(
        first["proxima_rodada"].get("status_inventario") == "FINALIZADO",
        f"primeira finalização falhou: {first}"
    )

    before = final_result(iid)
    before_items = before.get("itens", [])
    assert_true(len(before_items) == len(items), f"resultado inicial inesperado: {before}")

    # Repetir a operação pode retornar erro de estado ou resposta idempotente.
    try:
        second = next_round(iid)
        pr = second.get("proxima_rodada", {})
        assert_true(
            pr.get("criada") is not True,
            f"finalização repetida criou nova rodada: {second}"
        )
    except ApiError as e:
        assert_true(e.status in (400, 409), f"status inesperado na finalização repetida: {e.status} - {e.data}")

    after = final_result(iid)
    after_items = after.get("itens", [])
    assert_true(
        len(after_items) == len(before_items),
        f"resultado final foi duplicado: antes={len(before_items)} depois={len(after_items)}"
    )


def test_sessao_encerrada_nao_aceita_contagem():
    iid, r1, items = prepare("CLOSELOCK")
    target = items[0]

    s = start(iid, r1)
    sid = s["id_sessao"]

    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid, it, q)
    close(sid)

    expect_error(
        lambda: count(sid, target, qty_stock(target)),
        statuses=(400, 409)
    )


def test_r2_nao_cria_r3_apos_divergencia_persistente():
    iid, r1, items = prepare("NOR3")
    target = items[0]

    s = start(iid, r1)
    sid = s["id_sessao"]
    for it in items:
        q = qty_stock(it)
        if q <= 0:
            continue
        count(sid, it, q + 1 if it is target else q)
    close(sid)

    decision(iid, r1, target, "RECONTAR")
    nr = next_round(iid)
    r2 = nr["proxima_rodada"]["id_rodada"]

    s2 = start(iid, r2)
    sid2 = s2["id_sessao"]
    # Mantém a mesma divergência na R2.
    count(sid2, target, qty_stock(target) + 1)
    close(sid2)

    fin = next_round(iid)
    pr = fin["proxima_rodada"]
    assert_true(pr.get("status_inventario") == "FINALIZADO", f"R2 persistente não finalizou: {fin}")
    assert_true(pr.get("numero_rodada") == 2, f"fluxo avançou além da R2: {fin}")
    assert_true(pr.get("criada") is False, f"foi criada rodada terminal indevida: {fin}")

    resumo = pr.get("resumo_r2", {})
    assert_true(
        int(resumo.get("divergencias_confirmadas", 0)) == 1,
        f"divergência persistente não foi confirmada: {resumo}"
    )


def main():
    print("=" * 72)
    print("SGI - ESTÁGIO 3 | ESTADOS LIMITE E CONSISTÊNCIA DO ROTATIVO")
    print(f"API: {BASE} | Cliente: {CLIENTE_ID} | Armazém: {ARMAZEM} | Local: {LOCALIZACAO}")
    print("=" * 72)

    api.login()
    R.ok("Autenticação")

    run("Snapshot ausente bloqueia consolidação", test_snapshot_ausente_bloqueia_finalizacao)
    run("Reabertura substitui sessão anterior na consolidação", test_reabertura_substitui_sessao_anterior)
    run("Finalização repetida não duplica resultado", test_finalizacao_repetida_nao_duplica_resultado)
    run("Sessão encerrada não aceita nova contagem", test_sessao_encerrada_nao_aceita_contagem)
    run("R2 persistente finaliza sem criar R3", test_r2_nao_cria_r3_apos_divergencia_persistente)

    print("\n" + "=" * 72)
    print(f"PASS: {len(R.passed)} | FAIL: {len(R.failed)}")
    if R.failed:
        print("RESULTADO: REPROVADO")
        for x in R.failed:
            print(" -", x)
        sys.exit(1)

    print("RESULTADO: APROVADO")
    print("=" * 72)


if __name__ == "__main__":
    main()
