import { ExternalLink } from 'lucide-react';

// Job title that opens the posting in a new tab when the snapshot found a link;
// plain text otherwise (old records without url/id).
export default function VagaLink({ url, children, className = '' }) {
  if (!url || !/^https?:\/\//.test(url)) return <span className={className}>{children}</span>;
  return (
    <a className={`vaga-link ${className}`} href={url} target="_blank" rel="noreferrer noopener" title={url}>
      {children}<ExternalLink className="ico" aria-hidden="true" />
    </a>
  );
}
