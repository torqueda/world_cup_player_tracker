// Reusable country flag. Every call site passes only the country name.
//
// Flags are SVG files in public/flags, copied from country-flag-icons (MIT,
// see public/flags/LICENSE.txt), whose flags are drawn for small sizes.
// Emoji flags are not used because Windows does not draw them and shows two
// letters instead.
//
// A written country/team name is always shown NEXT TO this component at the
// call site (or via `showName`), so the flag itself is decorative (empty alt,
// aria-hidden) and the visible name carries the accessible label. This avoids
// screen readers announcing "Argentina flag Argentina". Unmapped names fall
// back to a short letter code badge instead of breaking the layout.
import countryCodesJson from "@/lib/flags/country-codes.json";

// Country name, in every spelling that appears in the dataset (team names,
// birthplaces, club, coach and referee nations), to its flag file: the ISO
// 3166-1 alpha-2 code, or the ISO 3166-2 code for England, Scotland and Wales
// (GB-ENG, GB-SCT, GB-WLS). tests/test_site_flags.py checks that every
// country in the data is here and that every file exists. To add a country,
// add its name here and copy its file from country-flag-icons' 3x2 folder.
const COUNTRY_CODES: Record<string, string> = countryCodesJson;

/** Short uppercase code shown when a country has no flag mapping. */
function fallbackCode(country: string): string {
  const letters = country.replace(/[^A-Za-z]/g, "");
  return (letters.slice(0, 3) || country.slice(0, 3)).toUpperCase();
}

function flagSrc(country: string): string | null {
  const code = COUNTRY_CODES[country.trim()];
  return code ? `${import.meta.env.BASE_URL}flags/${code}.svg` : null;
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
  const src = flagSrc(country);
  const wrapperClass = className ? `country-flag ${className}` : "country-flag";
  return (
    <span className={wrapperClass} title={country}>
      {src ? (
        <img
          className="country-flag-img"
          src={src}
          alt=""
          aria-hidden="true"
          width={18}
          height={12}
          loading="lazy"
          decoding="async"
        />
      ) : (
        <span className="country-flag-fallback" aria-hidden="true">
          {fallbackCode(country)}
        </span>
      )}
      {showName ? <span className="country-flag-name">{country}</span> : null}
    </span>
  );
}
