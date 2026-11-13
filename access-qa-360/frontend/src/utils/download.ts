import api from "../api/client";

/**
 * Download a file from an API path that needs the sign-in token.
 * A plain link cannot send the token, so fetch the file and hand it to the browser.
 */
export async function downloadFromApi(path: string, fallbackName: string): Promise<void> {
  const res = await api.get<Blob>(path, { responseType: "blob" });
  const header = String(res.headers["content-disposition"] ?? "");
  const name = /filename="?([^";]+)"?/.exec(header)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(res.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
