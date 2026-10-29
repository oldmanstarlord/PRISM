import source from "./terminal.css?raw";
const tokens = new Map(
  [...source.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)].map((match) => [
    match[1],
    match[2].trim(),
  ]),
);
/** Canvas renderers resolve the same CSS tokens; there is no second palette. */
export function terminalToken(name: string): string {
  return tokens.get(name) ?? "";
}
export function resolveTerminalColor(value: string): string {
  return value.replace(/var\((--[a-z0-9-]+)\)/g, (_, name: string) =>
    terminalToken(name),
  );
}
export const SERIES = [
  "var(--amber)",
  "var(--cyan)",
  "var(--white)",
  "var(--up)",
  "var(--down)",
];
export function resolveTerminalStyles<T>(value: T): T {
  if (typeof value === "string") return resolveTerminalColor(value) as T;
  if (Array.isArray(value))
    return value.map((item) => resolveTerminalStyles(item)) as T;
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        resolveTerminalStyles(item),
      ]),
    ) as T;
  return value;
}
