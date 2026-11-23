import { IBM_Plex_Mono, Manrope } from 'next/font/google';
import './globals.css';

const manrope = Manrope({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700', '800'],
  display: 'swap',
  variable: '--font-manrope'
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  display: 'swap',
  variable: '--font-ibm-mono'
});

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
    { media: '(prefers-color-scheme: dark)', color: '#0d1420' },
    { media: '(prefers-color-scheme: light)', color: '#f7f7f2' }
  ]
};

// Pre-paint: set data-theme before first paint to avoid flashing.
// Priority: saved choice > OS preference > dark. Fallback -> dark.
const bootTema = `(function(){try{var t=localStorage.getItem('monitor:tema');if(t!=='light'&&t!=='dark'){t=(window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches)?'light':'dark';}document.documentElement.dataset.theme=t;}catch(e){document.documentElement.dataset.theme='dark';}})();`;

export default function RootLayout({ children }) {
  return (
    <html lang="pt-BR" className={`${manrope.variable} ${ibmPlexMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: bootTema }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
