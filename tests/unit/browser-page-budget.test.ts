import test from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { BrowserPageBudget } from "../../open-sse/services/browserPageBudget.ts";

class Page extends EventEmitter {
  closed = false;
  async close() {
    if (!this.closed) {
      this.closed = true;
      this.emit("close");
    }
  }
}

test("concurrent requests never create more than two pages and closing admits next", async () => {
  const budget = new BrowserPageBudget();
  let creates = 0;
  const create = async () => {
    creates++;
    return new Page();
  };
  const a = await budget.open(create);
  const b = await budget.open(create);
  const waiting = budget.open(create);
  assert.equal(creates, 2);
  assert.deepEqual(budget.status(), { active: 2, pending: 1, limit: 2 });
  await a.close();
  const c = await waiting;
  assert.equal(creates, 3);
  assert.equal(budget.status().active, 2);
  await b.close();
  await c.close();
  assert.equal(budget.status().active, 0);
});

test("failed page creation returns the reservation", async () => {
  const budget = new BrowserPageBudget(1);
  await assert.rejects(
    budget.open(async () => {
      throw new Error("create failed");
    })
  );
  assert.equal(budget.status().active, 0);
  const p = await budget.open(async () => new Page());
  await p.close();
});

test("browser backlog is bounded and wait expiry does not release another request", async () => {
  const budget = new BrowserPageBudget(1, 1, 10);
  const p = await budget.open(async () => new Page());
  const waiting = assert.rejects(
    budget.open(async () => new Page()),
    /wait expired/
  );
  await assert.rejects(
    budget.open(async () => new Page()),
    /queue is full/
  );
  await waiting;
  assert.equal(budget.status().active, 1);
  await p.close();
});

test("expired lease closes only its owned page", async () => {
  const budget = new BrowserPageBudget(1, 1, 100, 10);
  const p = await budget.open(async () => new Page());
  await new Promise((resolve) => setTimeout(resolve, 25));
  assert.equal(p.closed, true);
  assert.equal(budget.status().active, 0);
});
