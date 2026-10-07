import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  useRouterState,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";

import { AppShell } from "../components/layout/AppShell";
import { Toaster } from "../components/ui/sonner";
import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { ApiError } from "@/services/apiClient";
import {
  consultarMeuUsuario,
  logout,
  obterToken,
} from "@/services/authService";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">
          Page not found
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          This page didn't load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something went wrong on our end. You can try refreshing or head back
          home.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()(
  {
    head: () => ({
      meta: [
        { charSet: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        { title: "SGI \u2014 Sistema de Gest\u00e3o de Invent\u00e1rios" },
        {
          name: "description",
          content:
            "Sistema operacional de contagem de inventário logístico da Alzarsilog para coletores, celulares e tablets.",
        },
        { name: "author", content: "Alzarsilog" },
        {
          property: "og:title",
          content: "SGI \u2014 Sistema de Gest\u00e3o de Invent\u00e1rios",
        },
        {
          property: "og:description",
          content:
            "Sistema operacional de contagem de inventário logístico da Alzarsilog para coletores, celulares e tablets.",
        },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
        { name: "twitter:site", content: "@Lovable" },
        {
          name: "twitter:title",
          content: "SGI \u2014 Sistema de Gest\u00e3o de Invent\u00e1rios",
        },
        {
          name: "twitter:description",
          content:
            "Sistema operacional de contagem de inventário logístico da Alzarsilog para coletores, celulares e tablets.",
        },
        {
          property: "og:image",
          content:
            "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/3bb6d9ccb6acd346b83883b7398a70ef/id-preview-d71654d8--3e5b180e-4aaa-44c4-ba74-2d5f1194df34.lovable.app-1786706381178.png",
        },
        {
          name: "twitter:image",
          content:
            "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/3bb6d9ccb6acd346b83883b7398a70ef/id-preview-d71654d8--3e5b180e-4aaa-44c4-ba74-2d5f1194df34.lovable.app-1786706381178.png",
        },
      ],
      links: [
        {
          rel: "stylesheet",
          href: appCss,
        },
        { rel: "icon", href: "/favicon.ico", type: "image/x-icon" },
      ],
    }),
    shellComponent: RootShell,
    component: RootComponent,
    notFoundComponent: NotFoundComponent,
    errorComponent: ErrorComponent,
  },
);

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  const router = useRouter();
  const [validandoSessao, setValidandoSessao] = useState(true);
  const [erroSessao, setErroSessao] = useState<string | null>(null);
  const [tentativaSessao, setTentativaSessao] = useState(0);

  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });

  const rotaPublica =
    pathname === "/login" ||
    pathname === "/cadastro" ||
    pathname === "/esqueci-senha" ||
    pathname === "/reset-senha";

  useEffect(() => {
    if (rotaPublica) {
      setValidandoSessao(false);
      setErroSessao(null);
      return;
    }

    if (!obterToken()) {
      setValidandoSessao(true);
      void router.navigate({ to: "/login", replace: true });
      return;
    }

    const controller = new AbortController();
    setValidandoSessao(true);
    setErroSessao(null);

    void consultarMeuUsuario(controller.signal)
      .then(() => {
        if (!controller.signal.aborted) setValidandoSessao(false);
      })
      .catch((erro: unknown) => {
        if (controller.signal.aborted) return;

        if (
          erro instanceof ApiError &&
          (erro.status === 401 || erro.status === 403)
        ) {
          logout();
          void router.navigate({ to: "/login", replace: true });
          return;
        }

        setValidandoSessao(false);
        setErroSessao(
          erro instanceof Error
            ? erro.message
            : "Não foi possível validar sua sessão.",
        );
      });

    return () => controller.abort();
  }, [rotaPublica, router, tentativaSessao]);

  let conteudo: ReactNode;

  if (rotaPublica) {
    conteudo = <Outlet />;
  } else if (validandoSessao) {
    conteudo = (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <p className="text-sm text-muted-foreground">Validando sessão...</p>
      </div>
    );
  } else if (erroSessao) {
    conteudo = (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <div className="w-full max-w-md rounded-lg border bg-card p-5 text-center shadow-sm">
          <h1 className="text-lg font-semibold">Falha ao validar a sessão</h1>
          <p className="mt-2 text-sm text-muted-foreground">{erroSessao}</p>
          <button
            type="button"
            className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
            onClick={() => setTentativaSessao((valor) => valor + 1)}
          >
            Tentar novamente
          </button>
        </div>
      </div>
    );
  } else {
    conteudo = (
      <AppShell>
        <Outlet />
      </AppShell>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      {conteudo}

      <Toaster position="top-right" richColors closeButton />
    </QueryClientProvider>
  );
}

