'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';

// Panel shell that can collapse to just its head. `defaultOpen=false` keeps
// healthy/empty panels quiet until the chevron expands them.
export default function Collapsible({ title, meta, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className={`panel collapsible ${open ? 'is-open' : 'is-collapsed'}`}>
      <div className="panel-head">
        <h2>{title}</h2>
        {meta && <span>{meta}</span>}
        <button
          type="button"
          className="collapse-btn"
          aria-expanded={open}
          aria-label={open ? `Recolher: ${title}` : `Expandir: ${title}`}
          onClick={() => setOpen(v => !v)}
        >
          <ChevronDown className="ico" aria-hidden="true" />
        </button>
      </div>
      {open && children}
    </section>
  );
}
