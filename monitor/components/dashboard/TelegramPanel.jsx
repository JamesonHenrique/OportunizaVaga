'use client';

import { Send } from 'lucide-react';
import { Barras } from './Charts';
import { Tiles } from './ui';
import { dataHora, desde } from '@/lib/dashboard';

// Aggregates only: total + count per channel. Never job text, links, phone,
// company name from a post — that data never leaves the publisher.
export default function TelegramPanel({ telegram, agora = Date.now() }) {
  const semSessao = !telegram || telegram.status === 'aguardando login';
  const porCanal = Object.entries(telegram?.porCanal || {}).sort((a, b) => b[1] - a[1]);
  const velho = telegram?.atualizado && agora - new Date(telegram.atualizado).getTime() > 3 * 3600000;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2><Send className="ico" aria-hidden="true" /> Garimpo Telegram</h2>
        <span className={`pill ${semSessao ? 'pill-warn' : (velho ? 'pill-warn' : 'pill-ok')}`}>
          {semSessao ? 'aguardando login' : (velho ? 'coleta atrasada' : 'coletando')}
        </span>
      </div>
      <div className="panel-body">
        {semSessao ? (
          <p className="verdict v-warn">Sem sessão do Telegram: faça o login do Telegram no PC do robô para voltar a coletar.</p>
        ) : (
          <>
            <Tiles itens={[
              { rotulo: 'Vagas coletadas', valor: telegram.total ?? 0, sub: 'após o filtro' },
              { rotulo: 'Canais com vaga', valor: porCanal.length, sub: 'dos monitorados' },
              { rotulo: 'Última coleta', valor: desde(telegram.atualizado, agora).replace('há ', ''), sub: dataHora(telegram.atualizado), tom: velho ? 'warn' : undefined },
            ]} />
            <div className="bars-block">
              <span className="bars-title">vagas por canal</span>
              <Barras itens={porCanal} tom="info" />
            </div>
          </>
        )}
        <p className="line-note">A coleta do Telegram roda por cron no PC do robô, filtra vagas JR/remotas e grava em state/telegram_vagas.json. Aqui só aparecem contagens.</p>
      </div>
    </section>
  );
}
