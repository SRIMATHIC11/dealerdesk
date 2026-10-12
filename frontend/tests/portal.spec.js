import { test, expect } from "@playwright/test";

test("catalogue loads, filters, and opens product details", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "The right part. Ready to go." }),
  ).toBeVisible();
  await expect(page.locator(".product-card").first()).toBeVisible();
  await page.getByLabel("Search catalogue").fill("BRK-");
  await expect(
    page.locator(".product-card").first().locator("code"),
  ).toContainText("BRK-");
  await page.locator(".product-title").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.screenshot({
    path: "../.local/catalogue-desktop.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("basket creates a draft, confirms and restores stock on cancellation", async ({
  page,
  request,
}) => {
  const sku = `E2E-${Date.now()}`;
  expect(
    (
      await request.post("/api/products/", {
        data: {
          sku,
          name: "Browser test brake pad",
          brand: "Test",
          category: "Brakes",
          vehicle_fitment: "Test Bike",
          price: "25.00",
        },
      })
    ).status(),
  ).toBe(201);
  await request.put(`/api/inventory/${sku}/`, {
    data: { quantity: 5, reason: "Browser test" },
  });
  await page.goto("/");
  await page.getByLabel("Search catalogue").fill(sku);
  await page.getByRole("button", { name: `Add ${sku} to cart` }).click();
  await page.getByRole("button", { name: /Basket/ }).click();
  await page.getByRole("button", { name: "Create draft order" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog").locator(".status")).toHaveText("DRAFT");
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByRole("dialog").locator(".status")).toHaveText(
    "CONFIRMED",
  );
  expect(
    (await (await request.get(`/api/products/${sku}/`)).json()).stock,
  ).toBe(4);
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("dialog").locator(".status")).toHaveText(
    "CANCELLED",
  );
  expect(
    (await (await request.get(`/api/products/${sku}/`)).json()).stock,
  ).toBe(5);
});

test("forecast has 40 rows and an accessible weekly detail", async ({
  page,
}) => {
  await page.goto("/#reorder");
  await expect(
    page.getByRole("heading", { name: "Stay ahead of demand." }),
  ).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(40);
  await page.locator("tbody .text-button").first().click();
  await expect(page.getByRole("dialog").locator(".forecast-bar")).toHaveCount(
    4,
  );
});

test("assistant UI renders grounded API output safely", async ({ page }) => {
  // Browser test isolates presentation; Python tests cover the real tool loop.
  await page.route("**/api/assistant/chat/", (route) =>
    route.fulfill({
      json: {
        reply: "Live stock checked for BRK-TEST. <script>alert(1)</script>",
        cited_skus: ["BRK-TEST"],
        tool_calls: [],
        actions: [],
      },
    }),
  );
  await page.goto("/#assistant");
  await page.getByLabel("Message the assistant").fill("Find brake pads");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator(".message.assistant")).toContainText(
    "<script>alert(1)</script>",
  );
  await expect(page.locator(".citations")).toContainText("BRK-TEST");
});

test("mobile catalogue has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.locator(".product-card").first()).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("navigation")).toBeVisible();
  await page.screenshot({
    path: "../.local/catalogue-mobile.png",
    fullPage: true,
  });
});
