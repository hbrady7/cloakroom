import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Libre_Caslon_Text } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { getBrief, getStatus, getTrades } from "@/lib/data";
import { shortDate } from "@/lib/format";

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  weight: ["400", "500", "600"],
  subsets: ["latin"],
});

const caslon = Libre_Caslon_Text({
  variable: "--font-caslon",
  weight: ["400", "700"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CLOAKROOM — politician & insider trade intelligence",
  description:
    "Congressional STOCK Act disclosures and SEC Form 4 insider filings, scored by a deterministic signal engine and briefed daily. Research only.",
};

const NAV = [
  { href: "/", label: "Brief" },
  { href: "/feed", label: "Feed" },
  { href: "/clusters", label: "Clusters" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/methodology", label: "Methodology" },
];

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const trades = getTrades();
  const brief = getBrief();
  const status = getStatus();
  const sources = Object.values(status.sources);
  const sourcesOk = sources.length > 0 && sources.every((s) => s.ok);

  return (
    <html lang="en">
      <body
        className={`${plexSans.variable} ${plexMono.variable} ${caslon.variable} flex min-h-screen flex-col antialiased`}
      >
        <header className="sticky top-0 z-40 border-b border-border bg-card/70 backdrop-blur">
          <div className="mx-auto flex h-14 w-full max-w-[1400px] items-center gap-6 px-4 sm:px-6">
            <Link href="/" className="flex shrink-0 items-baseline gap-2.5">
              <span className="display text-lg font-bold tracking-wide text-foreground">
                CLOAKROOM
              </span>
              <span className="form-plate hidden lg:inline">
                filed under the stock act
              </span>
            </Link>
            <nav className="mono flex flex-1 items-center gap-1 overflow-x-auto text-[11px] uppercase tracking-[0.12em]">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="rounded-sm px-2.5 py-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
                >
                  {n.label}
                </Link>
              ))}
            </nav>
            <div className="mono hidden items-center gap-2 text-[11px] text-muted-foreground md:flex">
              <span
                className={`inline-block size-1.5 rounded-full ${sourcesOk ? "bg-buy" : "bg-caution"}`}
                aria-hidden
              />
              <span>data {shortDate(trades.generated_at?.slice(0, 10) ?? brief.as_of ?? null)}</span>
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-8 sm:px-6">
          {children}
        </main>

        <footer className="border-t border-border">
          <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6">
            <p className="max-w-3xl text-xs leading-relaxed text-muted-foreground">
              Informational research derived from public STOCK Act and SEC EDGAR
              filings. Disclosures lag reality by up to 45 days; congressional
              amounts are reported in bands. Nothing here is investment advice,
              and nothing here executes trades.{" "}
              <Link href="/methodology" className="text-brass hover:underline">
                Methodology &amp; sources
              </Link>
            </p>
            <p className="form-plate mt-3">
              cloakroom · $0 infrastructure · house clerk · senate efd · sec edgar
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
