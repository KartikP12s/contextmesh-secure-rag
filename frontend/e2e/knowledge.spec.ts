import { test, expect } from "@playwright/test";
test("authorized search returns current citations and another tenant cannot download source", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByLabel("Development bearer credential").fill("local-acme-hr");
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page
    .getByLabel("Ask a question")
    .fill("How are travel expenses reimbursed?");
  await page.getByRole("main").getByRole("button", { name: "Search & ask" }).click();
  await expect(
    page.getByText("GROUNDED RESPONSE", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /acme\/travel-reimbursement/ })
    .first()
    .click();
  await expect(
    page.getByRole("dialog").getByText(/Rail and bus tickets/),
  ).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();
  const docs = await request.get("http://localhost:8010/api/documents", {
    headers: { Authorization: "Bearer local-acme-hr" },
  });
  const id = (await docs.json())[0].id;
  const denied = await request.get(
    `http://localhost:8010/api/documents/${id}/download`,
    { headers: { Authorization: "Bearer local-northstar-admin" } },
  );
  expect(denied.status()).toBe(404);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "../docs/dashboard.png", fullPage: true });
});
