import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.E2E_DEMO_PASSWORD ?? "change-me-demo-password";

async function signIn(page: Page, role: string) {
  await page.goto("about:blank"); // Leave the app first: a page still open would see the session end and redirect
  await page.context().clearCookies();
  await page.goto("/login");
  await page.getByLabel("University Email Address").fill(`${role}@example.test`);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).not.toHaveURL(/login/);
}

async function reportFault(page: Page, description: string): Promise<string> {
  await page.goto("/requests/new");
  await page.getByLabel(/Location in Moroka Hall/).selectOption({ index: 1 });
  await page.getByLabel(/Fault Category/).selectOption({ label: "Plumbing" });
  await page.getByLabel(/Fault Description/).fill(description);
  await page.getByRole("button", { name: /Submit/ }).click();
  await expect(page).toHaveURL(/requests\/\d+/);
  return page.url();
}

test("TC-42: report, approve, assign, complete and verify in the browser", async ({ page }) => {
  await signIn(page, "resident");
  const requestUrl = await reportFault(page, `Journey test: basin tap will not stop running ${Date.now()}.`);
  await expect(page.getByText("Submitted").first()).toBeVisible();

  await signIn(page, "supervisor");
  await page.goto(requestUrl);
  await page.getByRole("button", { name: "Approve Fault" }).click();
  await page.locator("#triage-priority").selectOption("HIGH");
  await page.getByRole("button", { name: /Confirm Appr/ }).click();
  await expect(page.locator(".detail-header-row").getByText("Approved")).toBeVisible();

  await page.getByRole("button", { name: "Assign Technician" }).click();
  const technician = page.locator("#triage-tech option").filter({ hasNotText: "Technician 2" }).last();
  await page.locator("#triage-tech").selectOption((await technician.getAttribute("value")) ?? "");
  await page.getByRole("button", { name: /Confirm Assi/ }).click();
  await expect(page.locator(".detail-header-row").getByText("Assigned")).toBeVisible();

  await signIn(page, "technician");
  await page.goto(requestUrl);
  await page.getByRole("button", { name: /Start Work/ }).click();
  await expect(page.locator(".detail-header-row").getByText("In Progress")).toBeVisible();

  await page.getByRole("button", { name: "Complete Work" }).click();
  await page.locator("#tech-completion-note").fill("Replaced the washer and tested the tap.");
  await page.getByRole("button", { name: /Confirm Wo/ }).click();
  await expect(page.locator(".detail-header-row").getByText("Work Completed")).toBeVisible();

  await signIn(page, "supervisor");
  await page.goto(requestUrl);
  await page.getByRole("button", { name: "Verify & Close Request" }).click();
  await page.getByRole("button", { name: /Confirm & Clo/ }).click();
  await expect(page.locator(".detail-header-row").getByText("Verified Closed")).toBeVisible();

  await signIn(page, "resident");
  await page.goto(requestUrl);
  await expect(page.locator(".detail-header-row").getByText("Verified Closed")).toBeVisible();
});

test("TC-19: clarification loop, ask, answer, approve", async ({ page }) => {
  await signIn(page, "resident");
  const requestUrl = await reportFault(page, `Journey test: something in the bathroom is broken ${Date.now()}.`);

  await signIn(page, "supervisor");
  await page.goto(requestUrl);
  await page.getByRole("button", { name: "Request Clarification" }).click();
  await page.locator("#clarify-note").fill("Which fixture in the bathroom is broken?");
  await page.getByRole("button", { name: /Send/ }).click();
  await expect(page.locator(".detail-header-row").getByText("Needs Clarification")).toBeVisible();

  await signIn(page, "resident");
  await page.goto("/requests");
  await expect(page.getByRole("heading", { name: /Action required/ })).toBeVisible();
  await page.goto(requestUrl);
  await page.locator("#resident-response").fill("The shower head is leaking at the joint.");
  await page.getByRole("button", { name: /Submit/ }).click();
  await expect(page.locator(".detail-header-row").getByText("Submitted")).toBeVisible();

  await signIn(page, "supervisor");
  await page.goto(requestUrl);
  await page.getByRole("button", { name: "Approve Fault" }).click();
  await page.locator("#triage-priority").selectOption("LOW");
  await page.getByRole("button", { name: /Confirm Appr/ }).click();
  await expect(page.locator(".detail-header-row").getByText("Approved")).toBeVisible();
});

test("ST-02: script markup in a description stays inert text", async ({ page }) => {
  const dialogs: string[] = [];
  page.on("dialog", (dialog) => {
    dialogs.push(dialog.message());
    void dialog.dismiss();
  });
  const markup = `<img src=x onerror=alert(1)><script>alert(2)</script> tap ${Date.now()}`;

  await signIn(page, "resident");
  const requestUrl = await reportFault(page, markup);
  await expect(page.getByText(markup).first()).toBeVisible();

  await signIn(page, "supervisor");
  await page.goto(requestUrl);
  await expect(page.getByText(markup).first()).toBeVisible();
  expect(dialogs).toEqual([]);
});

test("AC-05.4: the report form always shows the emergency notice", async ({ page }) => {
  await signIn(page, "resident");
  await page.goto("/requests/new");
  await expect(page.getByText(/must be reported to campus security/)).toBeVisible();
});

test("Section 6.2: an ended session returns to sign-in with a notice", async ({ page }) => {
  await signIn(page, "resident");
  await page.goto("/requests");
  await expect(page.getByRole("link", { name: "Report Fault" })).toBeVisible();
  await page.context().clearCookies({ name: "sessionid" });

  await page.getByRole("link", { name: "Report Fault" }).click();

  await expect(page).toHaveURL(/login\?expired=1/);
  await expect(page.getByText("Your session has ended")).toBeVisible();
});

test("NT-05: Resident and Technician screens fit a 360 px phone", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });

  for (const [role, paths] of [
    ["resident", ["/requests", "/requests/new"]],
    ["technician", ["/work"]],
  ] as const) {
    await signIn(page, role);
    for (const path of paths) {
      await page.goto(path);
      const width = await page.evaluate(() => document.documentElement.scrollWidth);
      expect(width, path).toBeLessThanOrEqual(360);
    }
  }
});
