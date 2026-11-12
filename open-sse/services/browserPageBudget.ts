/** Resource leases for automation-owned pages; never touches personal browser tabs. */
interface LeasePage {
  once(event: "close", listener: () => void): unknown;
  close(): Promise<void>;
}

export class BrowserPageBudget {
  private active = 0;
  private waiters: Array<{ ready: () => void; timer: ReturnType<typeof setTimeout> }> = [];

  constructor(
    readonly limit = 2,
    readonly maxPending = 32,
    readonly waitMs = 30_000,
    readonly lifetimeMs = 120_000
  ) {
    if (![limit, maxPending, waitMs, lifetimeMs].every((n) => Number.isInteger(n) && n > 0)) {
      throw new Error("Browser page budgets must be positive integers");
    }
  }

  status() {
    return { active: this.active, pending: this.waiters.length, limit: this.limit };
  }

  private reserve(): Promise<void> {
    if (this.active < this.limit) {
      this.active++;
      return Promise.resolve();
    }
    if (this.waiters.length >= this.maxPending) {
      return Promise.reject(
        new Error("Browser onboarding queue is full; HTTP provider workers remain independent")
      );
    }
    return new Promise((resolve, reject) => {
      const waiter = {
        ready: resolve,
        timer: setTimeout(() => {
          this.waiters = this.waiters.filter((entry) => entry !== waiter);
          reject(new Error("Browser page lease wait expired"));
        }, this.waitMs),
      };
      this.waiters.push(waiter);
    });
  }

  private release(): void {
    const next = this.waiters.shift();
    if (next) {
      clearTimeout(next.timer);
      next.ready();
    } else {
      this.active--;
    }
  }

  async open<T extends LeasePage>(create: () => Promise<T>): Promise<T> {
    await this.reserve();
    let released = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const release = () => {
      if (released) return;
      released = true;
      clearTimeout(timer);
      this.release();
    };
    try {
      const page = await create();
      page.once("close", release);
      timer = setTimeout(() => {
        void page.close().catch(() => {});
      }, this.lifetimeMs);
      timer.unref?.();
      return page;
    } catch (error) {
      release();
      throw error;
    }
  }
}

const budgetKey = Symbol.for("omniroute.automationPageBudget");
const holder = globalThis as typeof globalThis & { [budgetKey]?: BrowserPageBudget };
export const automationPageBudget = (holder[budgetKey] ??= new BrowserPageBudget());
