'use client';

import { Inbox } from 'lucide-react';
import Collapsible from './Collapsible';
import { Barras } from './Charts';
import { dataHora } from '@/lib/dashboard';

// Aggregates only: total + count per channel. Never job text, links, phone,
// company name from a post — that data never leaves the publisher.
export default function TelegramPanel({ telegram }) {
  const aguardandoLogin = !telegram || telegram.status === 'aguardando login';
  const porCanal = Object.entries(telegram?.porCanal || {}).sort((a, b) => b[1] - a[1]);
  return (
    <Collapsible
      title="Garimpo Telegram"
      meta={aguardandoLogin ? 'aguardando login' : `${telegram.total ?? 0} vaga(s)`}
      defaultOpen={!aguardandoLogin}
    >
      {aguardandoLogin ? (
        <p className="empty"><Inbox className="ico" aria-hidden="true" />Aguardando login no Telegram (sem sessão ativa).</p>
      ) : (
        <div className="panel-body">
          <p className="line-note">Atualizado {dataHora(telegram.atualizado)} · {telegram.total ?? 0} vaga(s) no total</p>
          <div className="bars-block">
            <span className="bars-title">por canal</span>
            <Barras itens={porCanal} tom="info" />
          </div>
        </div>
      )}
    </Collapsible>
  );
}
