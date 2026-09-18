// monitor/funnel.mjs — logica minima do funil vistas -> aplicadas -> respostas.
// DUPLICACAO deliberada de scripts/funnel.sh (que continua intacto, sem refator):
// este modulo existe para o teste node:test importar sem depender de shell.
// Espelha o calculo do funnel.sh: vistas = descartes + aplicadas + bloqueadas;
// resposta = aplicada com status diferente de 'enviada' ou com respondida_em/desfecho.
//
// @param {object} ap - conteudo parseado de aplicadas.json
// @returns {{vistas:number, aplicadas:number, respostas:number,
//            taxas:{vistasParaAplicadas:number, aplicadasParaRespostas:number}}}
export function computaFunil(ap) {
  const doc = ap && typeof ap === 'object' ? ap : {};
  const apl = Array.isArray(doc.aplicadas) ? doc.aplicadas : [];
  const bloq = doc.bloqueados && typeof doc.bloqueados === 'object' ? doc.bloqueados : {};
  const desc = doc.descartes_listagem && typeof doc.descartes_listagem === 'object' ? doc.descartes_listagem : {};

  let descTotal = 0;
  if (typeof desc.total === 'number' && Number.isFinite(desc.total)) {
    descTotal = desc.total;
  } else {
    for (const [k, v] of Object.entries(desc)) {
      if (k !== 'total' && typeof v === 'number' && Number.isFinite(v)) descTotal += v;
    }
  }

  const nBloq = Array.isArray(bloq) ? bloq.length : Object.keys(bloq).length;
  const vistas = Math.trunc(descTotal || 0) + apl.length + nBloq;
  const aplicadas = apl.length;
  const respostas = apl.filter(
    (a) => (a && a.status !== undefined && a.status !== null && a.status !== '' && a.status !== 'enviada') ||
      (a && (a.respondida_em || a.desfecho))
  ).length;
  const taxas = {
    vistasParaAplicadas: vistas ? (aplicadas / vistas) * 100 : 0,
    aplicadasParaRespostas: aplicadas ? (respostas / aplicadas) * 100 : 0,
  };
  return { vistas, aplicadas, respostas, taxas };
}
