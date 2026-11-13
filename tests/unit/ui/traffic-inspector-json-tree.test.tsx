// @vitest-environment jsdom
//
// The Traffic Inspector reads bodies through the kit JsonTree. The body may hold live credentials,
// and must preserve them in the owner-facing display and copied values.
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { InterceptedRequest } from "@/mitm/inspector/types";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

const { RequestBodyTab } =
  await import("@/app/(dashboard)/dashboard/tools/traffic-inspector/components/tabs/RequestBodyTab");
const { JsonViewer } =
  await import("@/app/(dashboard)/dashboard/tools/traffic-inspector/components/shared/JsonViewer");

const writeText = vi.fn();

beforeEach(() => {
  writeText.mockReset();
  writeText.mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
});

afterEach(() => cleanup());

function requestWith(requestBody: string) {
  return { requestBody, requestSize: requestBody.length } as InterceptedRequest;
}

describe("RequestBodyTab original capture values on the kit JsonTree", () => {
  it("shows original values on screen", () => {
    const { container } = render(
      <RequestBodyTab
        request={requestWith(
          JSON.stringify({ authorization: "Bearer abc.def", note: "plain", key: "sk-abc123" })
        )}
      />
    );

    expect(screen.getByRole("tree")).not.toBeNull();
    expect(container.textContent).toContain("abc.def");
    expect(container.textContent).toContain("sk-abc123");
    expect(container.textContent).toContain("plain");
    expect(container.querySelectorAll('[data-tone="redacted"]')).toHaveLength(0);
  });

  it("preserves a value represented by a JSON escape", () => {
    const { container } = render(
      <RequestBodyTab request={requestWith('{"token":"sk\\u002dabc123"}')} />
    );

    expect(container.textContent).toContain("sk-abc123");
    expect(container.querySelector('[data-tone="redacted"]')).toBeNull();
  });

  it("preserves original object keys", () => {
    const { container } = render(
      <RequestBodyTab request={requestWith(JSON.stringify({ "sk-abc123": { nested: 1 } }))} />
    );

    expect(container.textContent).toContain("sk-abc123");
    expect(container.textContent).not.toContain("••••");
    expect(container.textContent).toContain("nested");
  });

  it("copies the complete original ancestor, collapsed or not", async () => {
    const { container } = render(
      <RequestBodyTab
        request={requestWith(JSON.stringify({ a: { b: { c: "Bearer deep.secret", d: "safe" } } }))}
      />
    );

    expect(container.textContent).not.toContain("safe");
    fireEvent.click(container.querySelector('[data-action="copy-value"]') as HTMLElement);
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    const copied = writeText.mock.calls[0][0] as string;
    expect(copied).toContain("deep.secret");
    expect(copied).toContain("safe");
    expect(copied).not.toContain("••••");
  });

  it("retains the same values in raw and formatted views", () => {
    const { container } = render(
      <RequestBodyTab request={requestWith(JSON.stringify({ key: "sk-abc123" }))} />
    );

    fireEvent.click(screen.getByRole("button", { name: "raw" }));
    expect(container.querySelector("pre")?.textContent).toBe('{"key":"sk-abc123"}');
    fireEvent.click(screen.getByRole("button", { name: "formatted" }));

    expect(container.textContent).toContain("sk-abc123");
    expect(container.querySelector('[data-tone="redacted"]')).toBeNull();
  });
});

describe("JsonViewer on the kit JsonTree", () => {
  it("opens two levels, like the tree it replaces, and folds a node on click", () => {
    const { container } = render(<JsonViewer data={{ a: { b: { c: "deep" } } }} />);

    const rows = () => screen.getAllByRole("treeitem");
    expect(rows()).toHaveLength(3);
    expect(container.textContent).not.toContain("deep");

    fireEvent.click(rows()[2].querySelector('[data-action="toggle"]') as HTMLElement);
    expect(container.textContent).toContain("deep");
  });

  it("takes its labels from i18n", async () => {
    writeText.mockRejectedValue(new Error("denied"));
    const { container } = render(<JsonViewer data={{ a: 1 }} />);

    expect(screen.getByRole("button", { name: "expandAllLevels" })).not.toBeNull();
    expect(screen.getByRole("button", { name: "collapseAllLevels" })).not.toBeNull();
    const copyValue = container.querySelector('[data-action="copy-value"]') as HTMLElement;
    expect(copyValue.getAttribute("aria-label")).toBe("copyTitle");

    fireEvent.click(copyValue);
    expect((await screen.findByRole("alert")).textContent).toBe("copy: failed");
  });

  it("shows a long string whole, as the tree it replaces did", () => {
    const text = "x".repeat(20_000);
    const { container } = render(<JsonViewer data={{ text }} />);

    expect(container.textContent).toContain(text);
  });

  it("copies a node's value and its path", async () => {
    const { container } = render(<JsonViewer data={{ model: "gpt" }} />);
    const row = screen.getAllByRole("treeitem")[1];

    fireEvent.mouseOver(row);
    fireEvent.click(row.querySelector('[data-action="copy-value"]') as HTMLElement);
    await waitFor(() => expect(writeText).toHaveBeenLastCalledWith("gpt"));
    fireEvent.click(row.querySelector('[data-action="copy-path"]') as HTMLElement);
    await waitFor(() => expect(writeText).toHaveBeenLastCalledWith("$.model"));
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });
});
