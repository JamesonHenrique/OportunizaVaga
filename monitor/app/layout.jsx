import './globals.css';

export const metadata = {
  title: 'OportunizaVaga · Monitor de Candidaturas',
  description: 'Monitor operacional do robô de candidaturas OportunizaVaga',
  icons: {
    icon: '/icon.svg'
  }
};

export const viewport = {
  colorScheme: 'light dark',
  themeColor: [
    { media: '(prefers-color-scheme: dark)', color: '#060e21' },
    { media: '(prefers-color-scheme: light)', color: '#fafbff' }
  ]
};

// Pre-paint: set data-theme before first paint to avoid flashing.
// Priority: saved choice > OS preference > dark. Fallback -> dark.
const bootTema = `(function(){try{var t=localStorage.getItem('monitor:tema');if(t!=='light'&&t!=='dark'){t=(window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches)?'light':'dark';}document.documentElement.dataset.theme=t;}catch(e){document.documentElement.dataset.theme='dark';}})();`;

export default function RootLayout({ children }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: bootTema }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
