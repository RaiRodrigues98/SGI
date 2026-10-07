from pathlib import Path
from datetime import datetime
import hashlib
import re
import shutil

ROOT = Path.cwd()

EXPECTED = {
    "frontend/src/services/indicadoresService.ts":
        "490D2A29FE16DF3306B2BCCDDD06D9A24ED75A3595699170ABB04865AE893200",
    "frontend/src/services/rotativoService.ts":
        "D88AA146011A150822406791571C50010445539C478BC8DAF30DDC9C68E4C820",
    "frontend/src/routes/analise-ciclica.tsx":
        "0569579EA186B16EC554661B271FD1D9DCCC17AB4DECE92AC22299EB6B08C61D",
    "frontend/src/routes/recontagem.tsx":
        "E994300DB8E8A18EB1676D21D2BAC7896D7B983F566D92EF8D52FE3A1969E23B",
    "frontend/src/routes/analise-estoque.tsx":
        "E4883BD79B2ECC2ED753CF8687C2D163060C2AC1A1070E9E4C5119F0C8BB3437",
    "frontend/src/routes/acompanhamento-contagem.tsx":
        "74C33A475CDBBBDF9479C1943C5CB1F462D20BCD4370CF71A7E1FA0B8F1F3C9C",
    "frontend/src/routes/indicadores.tsx":
        "D14444841A50C6F148CBD263DCA505F5551363D3D4C6CC18CB1F3DA481B8D1DA",
    "frontend/src/routes/auditoria.tsx":
        "F9FEB0332D06191497B925AB106BDF27479F9E670416701E919DAC3DFBF107A2",
}

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()

def replace_once(text: str, old: str, new: str, nome: str) -> str:
    quantidade = text.count(old)

    if quantidade != 1:
        raise RuntimeError(
            f"[ERRO] {nome}: esperado 1 bloco, encontrado {quantidade}."
        )

    return text.replace(old, new, 1)

def remover_trava_sem_id(text: str, nome: str) -> str:
    # Remove somente o bloco inicial:
    #
    # if (!idInventario) {
    #   throw new Error(...);
    # }
    #
    # A tela passará primeiro a consultar os inventários ABERTOS.

    pattern = re.compile(
        r"\n(?P<i>[ \t]+)if \(!idInventario\) \{\n"
        r"(?P=i)  throw new Error\(\n"
        r"(?:[^\n]*\n){1,6}?"
        r"(?P=i)  \);\n"
        r"(?P=i)\}\n"
    )

    encontrados = list(pattern.finditer(text))

    if len(encontrados) != 1:
        raise RuntimeError(
            f"[ERRO] {nome}: bloco !idInventario esperado 1 vez; "
            f"encontrado {len(encontrados)}."
        )

    return pattern.sub("\n", text, count=1)

# ============================================================
# 1. PRE-CHECK
# ============================================================

print("============================================================")
print("PRE-CHECK DOS ARQUIVOS")
print("============================================================")

originais = {}

for relativo, hash_esperado in EXPECTED.items():
    path = ROOT / relativo

    if not path.exists():
        raise RuntimeError(f"[ERRO] Arquivo não encontrado: {relativo}")

    hash_atual = sha256(path)

    if hash_atual != hash_esperado:
        raise RuntimeError(
            f"[ERRO] Hash diferente em {relativo}\n"
            f"Esperado: {hash_esperado}\n"
            f"Atual:    {hash_atual}\n"
            "PATCH NÃO APLICADO."
        )

    originais[relativo] = path.read_text(
        encoding="utf-8"
    )

    print(f"[OK] {relativo}")

# Trabalha totalmente em memória.
novos = dict(originais)

# ============================================================
# 2. SERVIÇOS — SOMENTE INVENTÁRIOS ABERTOS
# ============================================================

rel = "frontend/src/services/indicadoresService.ts"

novos[rel] = replace_once(
    novos[rel],
    'return apiRequest<InventarioIndicadores[]>("/inventarios");',
    'return apiRequest<InventarioIndicadores[]>("/inventarios?status=ABERTO");',
    rel,
)

rel = "frontend/src/services/rotativoService.ts"

novos[rel] = replace_once(
    novos[rel],
    'return apiRequest<InventarioRotativo[]>("/inventarios?tipo=ROTATIVO");',
    'return apiRequest<InventarioRotativo[]>("/inventarios?tipo=ROTATIVO&status=ABERTO");',
    rel,
)

# ============================================================
# 3. IMPORTAR limparInventarioAtual NAS TELAS OPERACIONAIS
# ============================================================

IMPORT_ANTIGO = '''import {
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";'''

IMPORT_NOVO = '''import {
  limparInventarioAtual,
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";'''

rotas_import = [
    "frontend/src/routes/analise-ciclica.tsx",
    "frontend/src/routes/recontagem.tsx",
    "frontend/src/routes/analise-estoque.tsx",
    "frontend/src/routes/acompanhamento-contagem.tsx",
    "frontend/src/routes/indicadores.tsx",
]

for rel in rotas_import:
    novos[rel] = replace_once(
        novos[rel],
        IMPORT_ANTIGO,
        IMPORT_NOVO,
        f"{rel} / import",
    )

# ============================================================
# 4. ANÁLISE CÍCLICA
# ============================================================

rel = "frontend/src/routes/analise-ciclica.tsx"

novos[rel] = remover_trava_sem_id(
    novos[rel],
    rel,
)

BLOCO_ANTIGO = '''      const lista =
        await listarInventariosRotativos();

      const inventarioEncontrado =
        lista.find(
          (item) =>
            item.id_inventario ===
            idInventario,
        );'''

BLOCO_NOVO = '''      const lista =
        await listarInventariosRotativos();

      if (lista.length === 0) {
        limparInventarioAtual();
        setAnalise(null);
        setErro(null);
        return;
      }

      const inventarioEncontrado =
        lista.find(
          (item) =>
            item.id_inventario ===
            idInventario,
        ) ??
        (!idInventarioUrl
          ? lista[0] ?? null
          : null);'''

novos[rel] = replace_once(
    novos[rel],
    BLOCO_ANTIGO,
    BLOCO_NOVO,
    rel,
)

# ============================================================
# 5. RECONTAGEM
# ============================================================

rel = "frontend/src/routes/recontagem.tsx"

novos[rel] = remover_trava_sem_id(
    novos[rel],
    rel,
)

BLOCO_ANTIGO = '''      const inventarios = await listarInventariosIndicadores();
      const encontrado = inventarios.find(
        (item) => item.id_inventario === idInventario,
      );'''

BLOCO_NOVO = '''      const inventarios = await listarInventariosIndicadores();

      if (inventarios.length === 0) {
        limparInventarioAtual();
        setInventario(null);
        setRodada(null);
        setDados(null);
        setModo("SEM_RECONTAGEM");
        setErro(null);
        return;
      }

      const encontrado =
        inventarios.find(
          (item) => item.id_inventario === idInventario,
        ) ??
        (!idInventarioUrl
          ? inventarios[0] ?? null
          : null);'''

novos[rel] = replace_once(
    novos[rel],
    BLOCO_ANTIGO,
    BLOCO_NOVO,
    rel,
)

# ============================================================
# 6. ANÁLISE DE ESTOQUE
# ============================================================

rel = "frontend/src/routes/analise-estoque.tsx"

novos[rel] = remover_trava_sem_id(
    novos[rel],
    rel,
)

BLOCO_ANTIGO = '''        const dados =
          await listarInventariosIndicadores();

        const inventarioEncontrado =
          dados.find(
            (item) =>
              item.id_inventario ===
              idInventario,
          );'''

BLOCO_NOVO = '''        const dados =
          await listarInventariosIndicadores();

        if (dados.length === 0) {
          limparInventarioAtual();
          setInventarioSelecionado(null);
          setAnaliseRotativo(null);
          setAnaliseOficial(null);
          setUltimaAtualizacao(null);
          setErro(null);
          return;
        }

        const inventarioEncontrado =
          dados.find(
            (item) =>
              item.id_inventario ===
              idInventario,
          ) ??
          (!idInventarioUrl
            ? dados[0] ?? null
            : null);'''

novos[rel] = replace_once(
    novos[rel],
    BLOCO_ANTIGO,
    BLOCO_NOVO,
    rel,
)

# ============================================================
# 7. INDICADORES
# ============================================================

rel = "frontend/src/routes/indicadores.tsx"

novos[rel] = remover_trava_sem_id(
    novos[rel],
    rel,
)

BLOCO_ANTIGO = '''        const dados =
          await listarInventariosIndicadores();

        const inventarioEncontrado =
          dados.find(
            (item) =>
              item.id_inventario ===
              idInventario,
          );'''

BLOCO_NOVO = '''        const dados =
          await listarInventariosIndicadores();

        if (dados.length === 0) {
          limparInventarioAtual();
          setInventarioSelecionado(null);
          setAcompanhamento(null);
          setProdutividade(null);
          setResultadoFinal(null);
          setRisco(null);
          setPainel(null);
          setTendencias(null);
          setErro(null);
          return;
        }

        const inventarioEncontrado =
          dados.find(
            (item) =>
              item.id_inventario ===
              idInventario,
          ) ??
          (!idInventarioUrl
            ? dados[0] ?? null
            : null);'''

novos[rel] = replace_once(
    novos[rel],
    BLOCO_ANTIGO,
    BLOCO_NOVO,
    rel,
)

# ============================================================
# 8. ACOMPANHAMENTO
# ============================================================

rel = "frontend/src/routes/acompanhamento-contagem.tsx"

MARCADOR = '''    setInventarios(inventariosOrdenados);

    const idInventarioPreferido ='''

SUBSTITUTO = '''    setInventarios(inventariosOrdenados);

    if (inventariosOrdenados.length === 0) {
      limparInventarioAtual();
      setIdInventarioContexto(null);
      setAcompanhamento(null);
      setProdutividade(null);
      setErro(null);
      return;
    }

    const idInventarioPreferido ='''

novos[rel] = replace_once(
    novos[rel],
    MARCADOR,
    SUBSTITUTO,
    rel,
)

# ============================================================
# 9. AUDITORIA
#
# URL explícita:
#   /auditoria?inventario=1654
# continua permitindo histórico/finalizado.
#
# Acesso pelo menu:
# resolve somente inventário ABERTO.
# ============================================================

rel = "frontend/src/routes/auditoria.tsx"

novos[rel] = replace_once(
    novos[rel],
    'import { obterInventarioAtual, salvarInventarioAtual } from "@/lib/inventarioAtual";',
    'import { limparInventarioAtual, obterInventarioAtual, salvarInventarioAtual } from "@/lib/inventarioAtual";',
    f"{rel} / import contexto",
)

IMPORT_AUDITORIA = '''} from "../services/auditoriaService";'''

IMPORT_AUDITORIA_NOVO = '''} from "../services/auditoriaService";
import { listarInventariosIndicadores } from "@/services/indicadoresService";'''

novos[rel] = replace_once(
    novos[rel],
    IMPORT_AUDITORIA,
    IMPORT_AUDITORIA_NOVO,
    f"{rel} / import indicadores",
)

novos[rel] = replace_once(
    novos[rel],
    '''  const id = idInventarioUrl ?? obterInventarioAtual();''',
    '''  const [idInventarioContexto, setIdInventarioContexto] =
    useState<number | null>(idInventarioUrl ?? null);

  const id =
    idInventarioUrl ??
    idInventarioContexto;''',
    f"{rel} / id",
)

MARCADOR_ERRO = '''  const [erro, setErro] = useState<string | null>(null);'''

BLOCO_RESOLVER = '''  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (idInventarioUrl) {
      setIdInventarioContexto(idInventarioUrl);
      return;
    }

    let ativo = true;

    void listarInventariosIndicadores()
      .then((inventarios) => {
        if (!ativo) return;

        const idPersistido =
          obterInventarioAtual();

        const inventarioAtivo =
          inventarios.find(
            (item) =>
              item.id_inventario ===
              idPersistido,
          ) ??
          inventarios[0] ??
          null;

        if (!inventarioAtivo) {
          limparInventarioAtual();
          setIdInventarioContexto(null);
          setResultado(null);
          setErro(null);
          return;
        }

        salvarInventarioAtual(
          inventarioAtivo.id_inventario,
          inventarioAtivo.tipo,
        );

        setIdInventarioContexto(
          inventarioAtivo.id_inventario,
        );
      })
      .catch((falha: unknown) => {
        if (!ativo) return;

        setIdInventarioContexto(null);
        setResultado(null);
        setErro(
          falha instanceof Error
            ? falha.message
            : "Erro ao localizar o inventário ativo.",
        );
      });

    return () => {
      ativo = false;
    };
  }, [idInventarioUrl]);'''

novos[rel] = replace_once(
    novos[rel],
    MARCADOR_ERRO,
    BLOCO_RESOLVER,
    f"{rel} / resolver ativo",
)

# Auditoria histórica não deve transformar um FINALIZADO
# em inventário operacional atual.
BLOCO_SALVAR_AUDITORIA = '''      if (data.inventario) {
        salvarInventarioAtual(data.inventario.id_inventario, data.inventario.tipo);
      }
'''

novos[rel] = replace_once(
    novos[rel],
    BLOCO_SALVAR_AUDITORIA,
    "",
    f"{rel} / nao persistir historico",
)

# ============================================================
# 10. VALIDAÇÃO EM MEMÓRIA
# ============================================================

for relativo, conteudo in novos.items():
    if conteudo == originais[relativo]:
        raise RuntimeError(
            f"[ERRO] Nenhuma alteração produzida em {relativo}"
        )

print("")
print("============================================================")
print("PATCH VALIDADO EM MEMORIA")
print("Nenhum arquivo foi gravado até este ponto.")
print("============================================================")

# ============================================================
# 11. BACKUP
# ============================================================

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup_root = (
    ROOT /
    "_backup_contexto_inventario" /
    stamp
)

for relativo in EXPECTED:
    origem = ROOT / relativo
    destino = backup_root / relativo

    destino.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        origem,
        destino,
    )

print(f"[OK] Backup: {backup_root}")

# ============================================================
# 12. GRAVAÇÃO
# ============================================================

for relativo, conteudo in novos.items():
    path = ROOT / relativo

    path.write_text(
        conteudo,
        encoding="utf-8",
        newline="\n",
    )

    print(f"[PATCH] {relativo}")

print("")
print("============================================================")
print("PATCH APLICADO COM SUCESSO")
print("============================================================")
print("Produção NÃO foi alterada.")
print("Backend NÃO foi alterado.")
print(f"Backup: {backup_root}")
