export async function ensureActiveTabPermission(): Promise<boolean> {
  try {
    const granted = await chrome.permissions.contains({ permissions: ["activeTab"] });
    return granted;
  } catch {
    return false;
  }
}

export async function requestHostPermission(origin: string): Promise<boolean> {
  try {
    return await chrome.permissions.request({ origins: [origin] });
  } catch {
    return false;
  }
}
