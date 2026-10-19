// MCP wait (opencode 2; copy to ~/.config/opencode/plugins/ — docs/QUICKSTART.md): V2 builds the first model request without waiting for local MCP servers.
// Probed 3/3 runs: the first call went out ~1 s before playwright-chrome-real connected (npx start ~3.5 s), with
// 5 tools instead of 19 — a round would open with no browser at all. opencode 1 waited, so this is V2-only.
// Robot sessions only (OV_RODADA / OV_ROBO): the prompt hook runs before the prompt is admitted, so holding it until
// the browser tools are registered makes the first request carry them. Gives up after OV_ESPERA_MCP_MS (the round
// then runs as before and the prompt's "chrome fora" path applies).
const robo = () => !!(process.env.OV_RODADA || process.env.OV_ROBO);
const PREFIXO = process.env.OV_ESPERA_MCP || "playwright-chrome-real_";
const LIMITE_MS = Number(process.env.OV_ESPERA_MCP_MS || 45000);

async function esperar(listar: () => Promise<readonly { id?: string; name?: string }[]>, limite = LIMITE_MS,
                       passo = 250): Promise<boolean> {
  const fim = Date.now() + limite;
  for (;;) {
    try {
      if ((await listar()).some((t) => String(t.id ?? t.name ?? "").startsWith(PREFIXO))) return true;
    } catch {}
    if (Date.now() >= fim) return false;
    await new Promise((r) => setTimeout(r, passo));
  }
}

// One default export for both majors: opencode 1 calls server() (nothing to do there), opencode 2 reads id + setup().
export default {
  id: "oportunizavaga.espera-mcp",
  async setup(ctx: any) {
    if (!robo()) return;
    let pronto = false;
    await ctx.session.hook("prompt", async () => {
      if (pronto) return;
      pronto = await esperar(() => ctx.tool.list());
      if (!pronto) console.error(`espera-mcp: nenhuma ferramenta ${PREFIXO}* em ${LIMITE_MS} ms`);
      pronto = true;   // wait once per process; a dead MCP must not stall every later prompt
    });
  },
  async server() {
    return {};
  },
  esperar,
};
