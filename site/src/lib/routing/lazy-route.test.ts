import assert from "node:assert/strict";
import test from "node:test";
import { isStaleFileError, loadRoute } from "./lazy-route.js";

// A stand-in for the browser window: an address, session storage, and a
// record of reloads and of addresses opened.
function fakeWindow(pathname: string) {
  const store = new Map<string, string>();
  const fake = {
    reloads: 0,
    opened: [] as string[],
    location: {
      pathname,
      search: "",
      reload() {
        fake.reloads += 1;
      },
      assign(address: string) {
        fake.opened.push(address);
      },
    },
    sessionStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
      removeItem: (key: string) => void store.delete(key),
    },
  };
  (globalThis as unknown as { window: unknown }).window = fake;
  return fake;
}

const staleError = () =>
  new TypeError(
    "error loading dynamically imported module: https://example.org/assets/photos-route-H-otl3YG.js",
  );

// Resolves to "pending" if the promise has not settled by the next turn.
async function settled<T>(
  promise: Promise<T>,
): Promise<"pending" | { value: T } | { error: unknown }> {
  return Promise.race([
    promise.then(
      (value) => ({ value }),
      (error: unknown) => ({ error }),
    ),
    new Promise<"pending">((resolve) => setTimeout(() => resolve("pending"), 0)),
  ]);
}

test("isStaleFileError recognises each browser's wording", () => {
  assert.equal(
    isStaleFileError(new TypeError("Failed to fetch dynamically imported module: x.js")),
    true,
  );
  assert.equal(
    isStaleFileError(new TypeError("error loading dynamically imported module: x.js")),
    true,
  );
  assert.equal(isStaleFileError(new TypeError("Importing a module script failed.")), true);
  assert.equal(isStaleFileError(new Error("x is not defined")), false);
  assert.equal(isStaleFileError("error loading dynamically imported module"), false);
});

test("a stale file reloads the page once, then shows the error", async () => {
  const win = fakeWindow("/insights/photos");

  const first = await settled(loadRoute(() => Promise.reject(staleError())));
  assert.equal(first, "pending");
  assert.equal(win.reloads, 1);

  // After the reload the same address fails again: no second reload.
  const second = await settled(loadRoute(() => Promise.reject(staleError())));
  assert.notEqual(second, "pending");
  assert.ok(typeof second === "object" && "error" in second);
  assert.equal(win.reloads, 1);
});

test("a successful load clears the flag so a later deploy can reload again", async () => {
  const win = fakeWindow("/insights/what-wins");
  await settled(loadRoute(() => Promise.reject(staleError())));
  assert.equal(win.reloads, 1);

  const ok = await settled(loadRoute(() => Promise.resolve("page")));
  assert.deepEqual(ok, { value: "page" });

  await settled(loadRoute(() => Promise.reject(staleError())));
  assert.equal(win.reloads, 2);
});

test("during a navigation, the page that was asked for is opened, not the current one", async () => {
  const win = fakeWindow("/insights");
  const result = await settled(
    loadRoute(
      () => Promise.reject(staleError()),
      () => "/insights/photos#method",
    ),
  );
  assert.equal(result, "pending");
  assert.deepEqual(win.opened, ["/insights/photos#method"]);
  assert.equal(win.reloads, 0);

  // If the new page's file still fails, the error shows instead.
  win.location.pathname = "/insights/photos";
  const again = await settled(
    loadRoute(
      () => Promise.reject(staleError()),
      () => undefined,
    ),
  );
  assert.ok(typeof again === "object" && "error" in again);
  assert.deepEqual(win.opened, ["/insights/photos#method"]);
});

test("other errors are not retried", async () => {
  const win = fakeWindow("/insights/photos");
  const result = await settled(loadRoute(() => Promise.reject(new Error("x is not defined"))));
  assert.ok(typeof result === "object" && "error" in result);
  assert.equal(win.reloads, 0);
});
