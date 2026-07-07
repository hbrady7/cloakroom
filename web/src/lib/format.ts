export function money(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(n % 1_000_000 === 0 ? 0 : 1)}M`;
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n)}`;
}

export function band(low: number, high: number): string {
  if (low === high) return money(low);
  return `${money(low)}–${money(high)}`;
}

export function pct(x: number, digits = 1): string {
  const v = (x * 100).toFixed(digits);
  return `${x > 0 ? "+" : ""}${v}%`;
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00Z" : ""));
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function partyAbbr(party: string): string {
  if (/^rep/i.test(party)) return "R";
  if (/^dem/i.test(party)) return "D";
  if (/^ind/i.test(party)) return "I";
  return party ? party[0].toUpperCase() : "–";
}

export function lagLabel(days: number): string {
  return days === 0 ? "same day" : days === 1 ? "1 day" : `${days} days`;
}
