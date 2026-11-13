"use client";

import JsonTree from "@/shared/components/JsonTree";

interface JsonViewerProps {
  data: unknown;
  className?: string;
}

export function JsonViewer({ data, className }: JsonViewerProps) {
  return <JsonTree value={data} expandDepth={2} className={className} />;
}
