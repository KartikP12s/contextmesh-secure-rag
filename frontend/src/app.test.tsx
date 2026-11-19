import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./main";
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.restoreAllMocks();
});
test("requires credential before exposing any knowledge", () => {
  render(<App />);
  expect(
    screen.getByLabelText("Development bearer credential"),
  ).toHaveAttribute("type", "password");
  expect(screen.queryByText("Source library")).not.toBeInTheDocument();
});
test("member sees only the authorized library metrics", async () => {
  sessionStorage.setItem("contextmesh-token", "test");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.endsWith("/me")
          ? { user: "acme.hr", tenant: "acme", role: "member", groups: ["hr"] }
          : [],
    })),
  );
  render(<App />);
  await screen.findByText("Find answers you can trace");
  expect(screen.queryByText("Evaluations")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Ask a question")).toBeInTheDocument();
});
