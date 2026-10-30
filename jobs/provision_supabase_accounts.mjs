// Run from the repository root: node --env-file=.env jobs/provision_supabase_accounts.mjs
// Uses the project's existing Supabase SDK; never writes an administrative key to the frontend.
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

const require = createRequire(resolve("frontend/package.json"));
const { createClient } = require("@supabase/supabase-js");
const url = process.env.PRISM_SUPABASE_URL;
const publicKey = process.env.PRISM_SUPABASE_PUBLISHABLE_KEY;
const secretKey = process.env.PRISM_SUPABASE_SECRET_KEY ?? process.env.PRISM_SUPABASE_SERVICE_ROLE_KEY;
const password = process.env.PRISM_PRESENTATION_PASSWORD ?? "Prism@2026";
const profiles = [
  { email: "aarav@prism.com", name: "Aarav" },
  { email: "priya@prism.com", name: "Priya" },
  { email: "rohan@prism.com", name: "Rohan" },
];

function updateEnvironment(path, entries) {
  let source = existsSync(path) ? readFileSync(path, "utf8") : "";
  for (const [name, value] of Object.entries(entries)) {
    const expression = new RegExp(`^${name}=.*$`, "m");
    source = expression.test(source)
      ? source.replace(expression, () => `${name}=${value}`)
      : `${source.trimEnd()}\n${name}=${value}\n`;
  }
  writeFileSync(path, source);
}

async function main() {
  if (!url || !publicKey || !secretKey) {
    throw new Error("Add PRISM_SUPABASE_URL, PRISM_SUPABASE_PUBLISHABLE_KEY and PRISM_SUPABASE_SECRET_KEY to .env first.");
  }
  if (publicKey.startsWith("sb_secret_") || publicKey === secretKey) {
    throw new Error("The browser key must be a publishable/anon key, never an administrative key.");
  }
  if (!publicKey.startsWith("sb_publishable_")) {
    let role;
    try { role = JSON.parse(Buffer.from(publicKey.split(".")[1], "base64url").toString()).role; }
    catch { /* Invalid key is rejected below without logging it. */ }
    if (role !== "anon") throw new Error("PRISM_SUPABASE_PUBLISHABLE_KEY must be a publishable or legacy anon key.");
  }
  const endpoint = new URL(url);
  if (endpoint.protocol !== "https:" || endpoint.username || endpoint.password) {
    throw new Error("Use the HTTPS Supabase project URL without embedded credentials.");
  }
  const options = { auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false } };
  const admin = createClient(url, secretKey, options);
  const users = [];
  for (let page = 1; ; page++) {
    const { data, error } = await admin.auth.admin.listUsers({ page, perPage: 100 });
    if (error) throw new Error(`Cannot read Supabase users: ${error.message}`);
    users.push(...data.users);
    if (data.users.length < 100) break;
  }
  const identities = [];
  for (const profile of profiles) {
    let user = users.find(user => user.email?.toLowerCase() === profile.email);
    if (!user) {
      const { data, error } = await admin.auth.admin.createUser({
        email: profile.email, password, email_confirm: true,
        user_metadata: { name: profile.name },
      });
      if (error || !data.user) throw new Error(`Cannot create ${profile.email}: ${error?.message ?? "No user returned"}`);
      user = data.user;
      console.log(`Supabase account created: ${profile.email}`);
    } else {
      console.log(`Keeping existing Supabase account: ${profile.email}`);
    }
    const client = createClient(url, publicKey, options);
    const { data, error } = await client.auth.signInWithPassword({ email: profile.email, password });
    if (error || data.user?.id !== user.id) {
      throw new Error(`Could not verify login for ${profile.email}. Existing passwords are preserved; set PRISM_PRESENTATION_PASSWORD to their password before retrying.`);
    }
    await client.auth.signOut();
    identities.push({ email: profile.email, id: user.id });
  }
  const python = process.env.PRISM_PYTHON ?? (process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
  const result = spawnSync(python, ["-m", "jobs.link_supabase_accounts"], {
    input: JSON.stringify(identities), encoding: "utf8", stdio: ["pipe", "pipe", "pipe"],
  });
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.status !== 0) {
    // Avoid printing database tracebacks, URLs or environment values.
    if (result.stderr?.startsWith("Account linking error:")) process.stderr.write(result.stderr);
    throw new Error("Portfolio linking failed. Authentication accounts are preserved; check database access and existing account portfolios before retrying.");
  }
  updateEnvironment("frontend/.env", {
    VITE_SUPABASE_URL: url, VITE_SUPABASE_PUBLISHABLE_KEY: publicKey,
    VITE_LOCAL_AUTH_ENABLED: "false",
  });
  updateEnvironment(".env", {
    PRISM_SUPABASE_URL: url, PRISM_SUPABASE_PUBLISHABLE_KEY: publicKey,
    PRISM_LOCAL_AUTH_ENABLED: "false",
  });
  console.log("Supabase login verified for all three accounts. Local configuration now uses Supabase Auth.");
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
