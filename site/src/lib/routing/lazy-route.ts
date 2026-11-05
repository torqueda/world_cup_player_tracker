// Pages that load on first visit live in their own files, named by a hash of
// their contents. Each deploy removes the previous deploy's files, so a tab
// opened before a deploy asks for a file that no longer exists, and the
// import fails. Loading the page afresh fetches the new file list, so do that
// once; if the import still fails after that, let the error through to the
// route's error message instead of trying again.

const RELOAD_KEY = "lazy-route-reload";

// Browsers word this failure differently: Chrome "Failed to fetch dynamically
// imported module", Firefox "error loading dynamically imported module",
// Safari "Importing a module script failed".
const STALE_FILE_PATTERN = /dynamically imported module|importing a module script failed/i;

export function isStaleFileError(error: unknown): boolean {
  return error instanceof Error && STALE_FILE_PATTERN.test(error.message);
}

function readFlag(): string | null {
  try {
    return window.sessionStorage.getItem(RELOAD_KEY);
  } catch {
    return null;
  }
}

function writeFlag(value: string | null): boolean {
  try {
    if (value === null) {
      window.sessionStorage.removeItem(RELOAD_KEY);
    } else {
      window.sessionStorage.setItem(RELOAD_KEY, value);
    }
    return true;
  } catch {
    return false;
  }
}

export async function loadRoute<T>(
  importer: () => Promise<T>,
  // The address being opened, when the import runs during a navigation and
  // the browser still shows the previous page.
  pendingAddress?: () => string | undefined,
): Promise<T> {
  try {
    const loaded = await importer();
    writeFlag(null);
    return loaded;
  } catch (error) {
    const here = window.location.pathname + window.location.search;
    const target = pendingAddress?.() ?? here;
    const [targetPage] = target.split("#");
    // Reload only for this failure, only once per address, and only when the
    // flag can be stored, so a lasting failure cannot loop.
    if (isStaleFileError(error) && readFlag() !== targetPage && writeFlag(targetPage)) {
      // Load the page that was asked for, so the reader does not land back on
      // the one they clicked from.
      if (targetPage === here) {
        window.location.reload();
      } else {
        window.location.assign(target);
      }
      // Keep the current screen until the new page replaces it.
      return new Promise<T>(() => {});
    }
    writeFlag(null);
    throw error;
  }
}
