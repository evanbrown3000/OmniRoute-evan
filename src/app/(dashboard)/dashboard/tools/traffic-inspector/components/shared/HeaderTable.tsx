"use client";

import { useTranslations } from "next-intl";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@omniroute/ui-kit/table";

interface HeaderTableProps {
  headers: Record<string, string>;
}

export function HeaderTable({ headers }: HeaderTableProps) {
  const t = useTranslations("trafficInspector");

  return (
    <div>
      <Table className="min-w-0 font-mono text-xs" scrollbarLabel={t("headersTable")}>
        <TableHeader>
          <TableRow>
            <TableHead>{t("name")}</TableHead>
            <TableHead>{t("value")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(headers).map(([name, value]) => {
            return (
              <TableRow key={name}>
                <TableCell className="select-text text-text-muted">{name}</TableCell>
                <TableCell
                  className="whitespace-normal break-all select-text text-text-main"
                >
                  {value}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
