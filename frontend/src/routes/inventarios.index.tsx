import {
  createFileRoute,
  redirect,
} from "@tanstack/react-router";

export const Route = createFileRoute("/inventarios/")({
  beforeLoad: () => {
    throw redirect({
      to: "/controle-inventarios",
      replace: true,
    });
  },
});
