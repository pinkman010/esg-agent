export function reportIdFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/reports\/([^/]+)(?:\/|$)/);
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}
