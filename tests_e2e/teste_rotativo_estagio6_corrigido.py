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
# ESTÁGIO 6 - ISOLAMENTO ENTRE LOCALIZAÇÕES E CASOS ESPECIAIS
# ============================================================

def add_scope_location(iid: int, location: str):
    """
    Adiciona uma localização ao escopo usando o contrato atual da API.

    O endpoint espera:
        {"localizacoes": ["LOCAL"]}
    """
    return api.request(
        "POST",
        f"/inventarios/{iid}/escopo/localizacoes",
        {"localizacoes": [location]},
    )


def inventory_analysis(iid: int):
    return api.request("GET", f"/inventarios/{iid}/analise-rotativo")


def session_analysis(sid: int):
    return api.request("GET", f"/sessoes/{sid}/analise")


def norm(v):
    return "" if v is None else str(v).strip().upper()


def item_key(it):
    return (
        norm(it.get("localizacao")),
        norm(it.get("codigo")),
        norm(it.get("lote")),
    )


def choose_positive(items):
    for it in items:
        if qty_stock(it) > 0:
            return it
    raise AssertionError("Nenhum item com saldo positivo encontrado.")


def get_snapshot_location_items(iid: int, location: str):
    a = inventory_analysis(iid)
    result = []
    for it in a.get("itens", []):
        if norm(it.get("localizacao")) == norm(location):
            result.append(it)
    return result


def second_location_candidates():
    """
    Monta candidatos para a segunda localização.

    Prioridade:
    1. SGI_LOCALIZACAO_2, quando realmente configurada;
    2. localizações conhecidas do ambiente de teste ML007.

    Placeholders são ignorados automaticamente.
    """
    configured = os.getenv(
        "SGI_LOCALIZACAO_2",
        ""
    ).strip().upper()

    placeholders = {
        "",
        "OUTRA_LOCALIZACAO",
        "COLOQUE_AQUI_UMA_SEGUNDA_LOCALIZACAO",
        "SEGUNDA_LOCALIZACAO",
        "LOCALIZACAO_2",
    }

    candidates = []

    if (
        configured not in placeholders
        and norm(configured) != norm(LOCALIZACAO)
    ):
        candidates.append(configured)

    # Localizações já utilizadas no ambiente E2E do cliente 53 / ML007.
    for candidate in (
        "01REIT00101",
        "01RETN00101",
    ):
        if (
            norm(candidate) != norm(LOCALIZACAO)
            and candidate not in candidates
        ):
            candidates.append(candidate)

    return candidates


def add_first_valid_second_location(iid: int) -> str:
    """
    Testa os candidatos contra a própria API.

    Uma localização somente é escolhida quando o endpoint de escopo
    confirma que ela é válida para cliente/armazém e possui estoque
    elegível no ambiente atual.
    """
    errors = []

    for candidate in second_location_candidates():
        try:
            add_scope_location(
                iid,
                candidate
            )
            return candidate

        except ApiError as exc:
            if exc.status in (400, 404, 409, 422):
                errors.append(
                    f"{candidate}: HTTP {exc.status} - {exc.data}"
                )
                continue

            raise

    detail = (
        " | ".join(errors)
        if errors
        else
        "nenhum candidato disponível"
    )

    raise AssertionError(
        "Não foi encontrada uma segunda localização válida "
        f"para o Estágio 6. Tentativas: {detail}. "
        "Se o estoque do ambiente mudar, defina "
        "SGI_LOCALIZACAO_2 com uma localização válida diferente "
        f"de {LOCALIZACAO}."
    )


def prepare_two_locations(tag: str):
    iid, r1 = create_inventory(tag)

    # Primeira localização padrão do E2E.
    add_scope_location(
        iid,
        LOCALIZACAO
    )

    # Segunda localização é validada dinamicamente pela API.
    loc2 = add_first_valid_second_location(
        iid
    )

    snap = api.request("POST", f"/inventarios/{iid}/snapshot", {})
    total = (
        snap.get("total_registros")
        or snap.get("registros_snapshot")
        or snap.get("quantidade_registros")
        or 0
    )
    assert_true(int(total) > 0, f"snapshot vazio: {snap}")

    items1 = get_snapshot_location_items(iid, LOCALIZACAO)
    items2 = get_snapshot_location_items(iid, loc2)

    assert_true(len(items1) > 0, f"sem snapshot em {LOCALIZACAO}")
    assert_true(len(items2) > 0, f"sem snapshot em {loc2}")

    return iid, r1, loc2, items1, items2


def count_location(iid, r1, location, items, divergent_target=None):
    s = api.request("POST", "/localizacoes/iniciar", {
        "id_inventario": iid,
        "id_rodada": r1,
        "localizacao": location,
    })
    sid = s["id_sessao"]

    for it in items:
        q = qty_stock(it)
        if q <= 0:
            continue
        api.request("POST", "/contagens", {
            "id_sessao": sid,
            "codigo": str(it["codigo"]),
            "lote": it.get("lote") or "",
            "quantidade": q + 1 if it is divergent_target else q,
        })

    api.request("POST", "/localizacoes/encerrar", {
        "id_sessao": sid,
        "localizacao_vazia": False,
    })
    return sid


def test_divergencia_de_uma_localizacao_nao_contamina_outra():
    iid, r1, loc2, items1, items2 = prepare_two_locations("LOCISO")
    target = choose_positive(items1)

    sid1 = count_location(iid, r1, LOCALIZACAO, items1, target)
    sid2 = count_location(iid, r1, loc2, items2)

    a1 = session_analysis(sid1)
    a2 = session_analysis(sid2)

    div1 = [x for x in a1.get("itens", []) if norm(x.get("status")) not in ("OK", "")]
    div2 = [x for x in a2.get("itens", []) if norm(x.get("status")) not in ("OK", "")]

    assert_true(len(div1) >= 1, f"divergência não apareceu em {LOCALIZACAO}: {a1}")
    assert_true(len(div2) == 0, f"divergência contaminou {loc2}: {div2}")


def test_r2_contem_somente_localizacao_decidida():
    iid, r1, loc2, items1, items2 = prepare_two_locations("R2LOC")
    target = choose_positive(items1)

    count_location(iid, r1, LOCALIZACAO, items1, target)
    count_location(iid, r1, loc2, items2)

    decision(iid, r1, target, "RECONTAR")

    pv = preview(iid)
    cand = pv.get("preview", {}).get("itens_candidatos", [])

    assert_true(len(cand) == 1, f"R2 deveria ter exatamente 1 candidato: {cand}")
    localizacoes_candidato = cand[0].get("localizacoes", [])

    if isinstance(localizacoes_candidato, str):
        localizacoes_candidato = [localizacoes_candidato]

    localizacoes_candidato = {
        norm(x)
        for x in localizacoes_candidato
        if norm(x)
    }

    assert_true(
        localizacoes_candidato == {norm(LOCALIZACAO)},
        (
            "R2 deveria conter somente a localização decidida "
            f"{LOCALIZACAO}, mas retornou: {cand}"
        )
    )

    nr = next_round(iid)
    r2 = nr["proxima_rodada"]["id_rodada"]

    # A localização sem divergência não pode ser aberta na R2.
    expect_error(
        lambda: api.request("POST", "/localizacoes/iniciar", {
            "id_inventario": iid,
            "id_rodada": r2,
            "localizacao": loc2,
        }),
        statuses=(400, 409)
    )

    s2 = start(iid, r2)
    sid2 = s2["id_sessao"]
    count(sid2, target, qty_stock(target))
    close(sid2)

    fin = next_round(iid)
    assert_true(
        fin["proxima_rodada"].get("status_inventario") == "FINALIZADO",
        f"R2 isolada não finalizou: {fin}"
    )


def test_decisao_com_localizacao_errada_e_bloqueada():
    iid, r1, loc2, items1, items2 = prepare_two_locations("BADDECLOC")
    target = choose_positive(items1)

    count_location(iid, r1, LOCALIZACAO, items1, target)
    count_location(iid, r1, loc2, items2)

    payload = {
        "id_rodada": r1,
        "localizacao": loc2,
        "codigo": str(target["codigo"]),
        "lote": target.get("lote") or "",
        "decisao": "RECONTAR",
    }

    expect_error(
        lambda: api.request("POST", f"/inventarios/{iid}/decisoes-rotativo", payload),
        statuses=(400, 409, 422)
    )


def test_duas_localizacoes_corretas_finalizam_sem_r2():
    iid, r1, loc2, items1, items2 = prepare_two_locations("TWOOK")

    count_location(iid, r1, LOCALIZACAO, items1)
    count_location(iid, r1, loc2, items2)

    fin = next_round(iid)
    pr = fin["proxima_rodada"]

    assert_true(pr.get("status_inventario") == "FINALIZADO", f"duas localizações OK não finalizaram: {fin}")
    assert_true(pr.get("criada") is False, f"R2 foi criada sem divergência: {fin}")


def test_resultado_final_preserva_localizacoes():
    iid, r1, loc2, items1, items2 = prepare_two_locations("FINLOC")

    count_location(iid, r1, LOCALIZACAO, items1)
    count_location(iid, r1, loc2, items2)

    next_round(iid)
    rf = final_result(iid)
    finais = rf.get("itens", [])

    locs = {norm(x.get("localizacao")) for x in finais}

    assert_true(norm(LOCALIZACAO) in locs, f"resultado final perdeu {LOCALIZACAO}: {locs}")
    assert_true(norm(loc2) in locs, f"resultado final perdeu {loc2}: {locs}")


def main():
    print("=" * 72)
    print("SGI - ESTÁGIO 6 | ISOLAMENTO ENTRE LOCALIZAÇÕES")
    print(f"API: {BASE} | Cliente: {CLIENTE_ID} | Armazém: {ARMAZEM}")
    print("=" * 72)

    api.login()
    R.ok("Autenticação")

    run("Divergência não contamina outra localização", test_divergencia_de_uma_localizacao_nao_contamina_outra)
    run("R2 contém somente a localização decidida", test_r2_contem_somente_localizacao_decidida)
    run("Decisão com localização incorreta é bloqueada", test_decisao_com_localizacao_errada_e_bloqueada)
    run("Duas localizações corretas finalizam sem R2", test_duas_localizacoes_corretas_finalizam_sem_r2)
    run("Resultado final preserva as duas localizações", test_resultado_final_preserva_localizacoes)

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
