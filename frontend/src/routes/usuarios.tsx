import { Link, createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import {
  Search,
  UserRoundCheck,
  UserRoundX,
  Users,
} from "lucide-react";

import {
  listarUsuarios,
  type Usuario,
} from "@/services/usuariosService";

export const Route = createFileRoute("/usuarios")({
  head: () => ({
    meta: [
      {
        title: "Usu\u00e1rios \u2014 SGI",
      },
    ],
  }),
  component: UsuariosPage,
});

type FiltroStatus =
  | "TODOS"
  | "ATIVOS"
  | "INATIVOS";

function UsuariosPage() {
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [busca, setBusca] = useState("");
  const [filtroStatus, setFiltroStatus] =
    useState<FiltroStatus>("TODOS");

  const [carregando, setCarregando] =
    useState(true);

  const [erro, setErro] =
    useState<string | null>(null);


  useEffect(() => {
    void carregarUsuarios();
  }, []);

  async function carregarUsuarios() {
    try {
      setCarregando(true);
      setErro(null);

      const dados = await listarUsuarios();

      setUsuarios(dados);
    } catch (error) {
      setErro(
        error instanceof Error
          ? error.message
          : "Erro ao carregar usuários.",
      );
    } finally {
      setCarregando(false);
    }
  }

  const usuariosFiltrados = useMemo(() => {
    const termo =
      busca.trim().toLowerCase();

    return usuarios.filter((usuario) => {
      if (
        filtroStatus === "ATIVOS" &&
        !usuario.ativo
      ) {
        return false;
      }

      if (
        filtroStatus === "INATIVOS" &&
        usuario.ativo
      ) {
        return false;
      }

      if (!termo) {
        return true;
      }

      return [
        usuario.nome,
        usuario.login,
        usuario.email ?? "",
      ].some((valor) =>
        valor.toLowerCase().includes(termo),
      );
    });
  }, [
    usuarios,
    busca,
    filtroStatus,
  ]);

  const totalAtivos = useMemo(
    () =>
      usuarios.filter(
        (usuario) => usuario.ativo,
      ).length,
    [usuarios],
  );

  const totalInativos =
    usuarios.length - totalAtivos;

  return (
    <main className="space-y-6 p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">
            Usuários
          </h1>

          <p className="mt-1 text-sm text-muted-foreground">
            Gerencie os usuários, perfis e permissões
            de acesso ao SGI.
          </p>
        </div>

        <Link
          to="/usuarios/novo"
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Novo usuário
        </Link>
      </div>

      {erro && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {erro}
        </div>
      )}

      <section className="grid gap-3 sm:grid-cols-3">
        <Resumo
          titulo="Usuários"
          valor={usuarios.length}
          icone={<Users className="size-5" />}
        />

        <Resumo
          titulo="Ativos"
          valor={totalAtivos}
          icone={
            <UserRoundCheck className="size-5" />
          }
        />

        <Resumo
          titulo="Inativos"
          valor={totalInativos}
          icone={
            <UserRoundX className="size-5" />
          }
        />
      </section>

      <section className="space-y-4 rounded-lg border bg-card p-5 shadow-xs">
        <div className="flex flex-wrap gap-3">
          <div className="relative min-w-[260px] flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />

            <input
              value={busca}
              onChange={(event) =>
                setBusca(event.target.value)
              }
              placeholder="Buscar por nome, login ou e-mail..."
              className="h-10 w-full rounded-md border bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <select
            value={filtroStatus}
            onChange={(event) =>
              setFiltroStatus(
                event.target.value as FiltroStatus,
              )
            }
            className="h-10 rounded-md border bg-background px-3 text-sm"
          >
            <option value="TODOS">
              Todos
            </option>
            <option value="ATIVOS">
              Ativos
            </option>
            <option value="INATIVOS">
              Inativos
            </option>
          </select>
        </div>

        <div className="overflow-hidden rounded-lg border">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[850px] text-sm">
              <thead className="border-b bg-muted/40">
                <tr>
                  <Th>Usuário</Th>
                  <Th>Login</Th>
                  <Th>E-mail</Th>
                  <Th>Status</Th>
                  <Th>Último acesso</Th>
                  <Th>Ações</Th>
                </tr>
              </thead>

              <tbody>
                {usuariosFiltrados.map(
                  (usuario) => (
                    <tr
                      key={usuario.id_usuario}
                      className="border-b last:border-0"
                    >
                      <Td>
                        <div className="font-medium">
                          {usuario.nome}
                        </div>
                      </Td>

                      <Td>{usuario.login}</Td>

                      <Td>
                        {usuario.email || "-"}
                      </Td>

                      <Td>
                        <StatusUsuario
                          ativo={usuario.ativo}
                        />
                      </Td>

                      <Td>
                        {formatarDataHora(
                          usuario.ultimo_login,
                        )}
                      </Td>

                      <Td>
                        <Link
                          to="/usuarios/$idUsuario"
                          params={{
                            idUsuario: String(
                              usuario.id_usuario,
                            ),
                          }}
                          className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-muted"
                        >
                          Gerenciar
                        </Link>
                      </Td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>

          {!carregando &&
            usuariosFiltrados.length === 0 && (
              <div className="p-8 text-center text-sm text-muted-foreground">
                Nenhum usuário encontrado.
              </div>
            )}

          {carregando && (
            <div className="p-8 text-center text-sm text-muted-foreground">
              Carregando usuários...
            </div>
          )}
        </div>
      </section>

    </main>
  );
}

function Resumo({
  titulo,
  valor,
  icone,
}: {
  titulo: string;
  valor: number;
  icone: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border bg-card p-4 shadow-xs">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm text-muted-foreground">
            {titulo}
          </div>

          <div className="mt-1 text-2xl font-semibold">
            {valor}
          </div>
        </div>

        <div className="text-muted-foreground">
          {icone}
        </div>
      </div>
    </div>
  );
}

function StatusUsuario({
  ativo,
}: {
  ativo: boolean;
}) {
  return (
    <span
      className={
        ativo
          ? "inline-flex rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700"
          : "inline-flex rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground"
      }
    >
      {ativo ? "Ativo" : "Inativo"}
    </span>
  );
}

function Linha({
  titulo,
  valor,
}: {
  titulo: string;
  valor: string;
}) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground">
        {titulo}
      </dt>

      <dd className="text-right font-medium">
        {valor}
      </dd>
    </div>
  );
}

function Th({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <th className="px-4 py-3 text-left font-medium text-muted-foreground">
      {children}
    </th>
  );
}

function Td({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <td className="px-4 py-3 align-middle">
      {children}
    </td>
  );
}

function formatarDataHora(
  valor: string | null,
) {
  if (!valor) {
    return "-";
  }

  const data = new Date(valor);

  if (Number.isNaN(data.getTime())) {
    return valor;
  }

  return new Intl.DateTimeFormat(
    "pt-BR",
    {
      dateStyle: "short",
      timeStyle: "short",
    },
  ).format(data);
}
