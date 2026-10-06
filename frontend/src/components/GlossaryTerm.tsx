import { Tooltip } from "@mui/material";
import type { ReactNode } from "react";

import { useApi } from "../api";
import type { GlossaryTermItem } from "../types";

interface GlossaryTermProps {
  termKey: string;
  children?: ReactNode;
}

export function GlossaryTerm({ termKey, children }: GlossaryTermProps) {
  const { data } = useApi<GlossaryTermItem>(`/glossary/${encodeURIComponent(termKey)}`);
  const label = children ?? data?.label ?? termKey.replace(/_/g, " ");
  const title = data
    ? `${data.plain_definition}${data.formula_text ? ` Formula: ${data.formula_text}` : ""}`
    : "Definition unavailable";
  return <Tooltip title={title} arrow><span tabIndex={0}>{label}</span></Tooltip>;
}
