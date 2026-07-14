// Reusable country flag. Renders an emoji flag today, but every call site passes
// only the country name, so the internal renderer can later be swapped for SVG
// assets (e.g. flagpedia.net) without touching any route markup.
//
// A written country/team name is always shown NEXT TO this component at the call
// site (or via `showName`), so the emoji itself is decorative (aria-hidden) and
// the visible name carries the accessible label — this avoids screen readers
// announcing "Argentina flag Argentina". Unmapped names fall back to a short
// letter code badge instead of breaking the layout.

// Country name (in every spelling that appears in the dataset — team names,
// birthplaces, club/coach/referee nations) → ISO 3166-1 alpha-2 code. UK home
// nations and the Isle of Man are handled separately below.
const COUNTRY_ISO: Record<string, string> = {
  Algeria: "DZ",
  Angola: "AO",
  Argentina: "AR",
  Armenia: "AM",
  Australia: "AU",
  Austria: "AT",
  Azerbaijan: "AZ",
  Belgium: "BE",
  "Bosnia and Herzegovina": "BA",
  "Bosnia-Herzegovina": "BA",
  Brazil: "BR",
  Bulgaria: "BG",
  "Burkina Faso": "BF",
  Cameroon: "CM",
  Canada: "CA",
  "Cape Verde": "CV",
  Chile: "CL",
  China: "CN",
  "People's Republic of China": "CN",
  Colombia: "CO",
  "Congo DR": "CD",
  "DR Congo": "CD",
  "Republic of the Congo": "CG",
  "Costa Rica": "CR",
  Croatia: "HR",
  Curacao: "CW",
  "Curaçao": "CW",
  Cyprus: "CY",
  "Czech Republic": "CZ",
  Czechia: "CZ",
  Denmark: "DK",
  Ecuador: "EC",
  Egypt: "EG",
  "El Salvador": "SV",
  Finland: "FI",
  France: "FR",
  Gabon: "GA",
  Germany: "DE",
  Ghana: "GH",
  Greece: "GR",
  Guinea: "GN",
  Haiti: "HT",
  Honduras: "HN",
  Hungary: "HU",
  Iran: "IR",
  Iraq: "IQ",
  Ireland: "IE",
  Israel: "IL",
  Italy: "IT",
  "Ivory Coast": "CI",
  Jamaica: "JM",
  Japan: "JP",
  Jordan: "JO",
  Kazakhstan: "KZ",
  Kenya: "KE",
  Malaysia: "MY",
  Mauritania: "MR",
  Mexico: "MX",
  Monaco: "MC",
  Morocco: "MA",
  Netherlands: "NL",
  "New Zealand": "NZ",
  Nicaragua: "NI",
  Nigeria: "NG",
  Norway: "NO",
  Panama: "PA",
  Paraguay: "PY",
  Peru: "PE",
  Poland: "PL",
  Portugal: "PT",
  Qatar: "QA",
  Romania: "RO",
  Russia: "RU",
  "Saudi Arabia": "SA",
  Senegal: "SN",
  Serbia: "RS",
  "Sierra Leone": "SL",
  Slovakia: "SK",
  Slovenia: "SI",
  "South Africa": "ZA",
  "South Korea": "KR",
  Spain: "ES",
  Sudan: "SD",
  Sweden: "SE",
  Switzerland: "CH",
  Syria: "SY",
  Tanzania: "TZ",
  Thailand: "TH",
  "Trinidad and Tobago": "TT",
  Tunisia: "TN",
  Turkey: "TR",
  "Türkiye": "TR",
  "United Arab Emirates": "AE",
  "United States": "US",
  Uruguay: "UY",
  Uzbekistan: "UZ",
  Venezuela: "VE",
  Zambia: "ZM",
  "Isle of Man": "IM",
};

// Emoji flags for the UK home nations (regional-indicator pairs don't exist for
// them; these are Unicode tag sequences).
const SUBDIVISION_EMOJI: Record<string, string> = {
  England: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}",
  Scotland: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}",
  Wales: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0077}\u{E006C}\u{E0073}\u{E007F}",
};

function isoToEmoji(iso: string): string {
  const base = 0x1f1e6;
  return String.fromCodePoint(
    ...iso
      .toUpperCase()
      .split("")
      .map((char) => base + (char.charCodeAt(0) - 65)),
  );
}

/** Short uppercase code shown when a country has no flag mapping. */
function fallbackCode(country: string): string {
  const letters = country.replace(/[^A-Za-z]/g, "");
  return (letters.slice(0, 3) || country.slice(0, 3)).toUpperCase();
}

interface FlagContent {
  glyph: string | null;
  code: string;
}

// Single point of truth for how a country renders. Swap the emoji here for an
// <img>/SVG later and every call site updates automatically.
function flagContent(country: string): FlagContent {
  const trimmed = country.trim();
  if (SUBDIVISION_EMOJI[trimmed]) {
    return { glyph: SUBDIVISION_EMOJI[trimmed], code: fallbackCode(trimmed) };
  }
  const iso = COUNTRY_ISO[trimmed];
  return { glyph: iso ? isoToEmoji(iso) : null, code: iso ?? fallbackCode(trimmed) };
}

interface CountryFlagProps {
  country: string | null | undefined;
  /** Also render the written country name after the flag. */
  showName?: boolean;
  className?: string;
}

export function CountryFlag({ country, showName = false, className }: CountryFlagProps) {
  if (!country) {
    return null;
  }
  const { glyph, code } = flagContent(country);
  const wrapperClass = className ? `country-flag ${className}` : "country-flag";
  return (
    <span className={wrapperClass} title={country}>
      {glyph ? (
        <span className="country-flag-glyph" aria-hidden="true">
          {glyph}
        </span>
      ) : (
        <span className="country-flag-fallback" aria-hidden="true">
          {code}
        </span>
      )}
      {showName ? <span className="country-flag-name">{country}</span> : null}
    </span>
  );
}
