import AsyncStorage from '@react-native-async-storage/async-storage';

/**
 * Thin typed wrapper around AsyncStorage. All app persistence goes through
 * here so tests can mock a single seam.
 */

export async function readJson<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(key);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export async function writeJson<T>(key: string, value: T): Promise<void> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Best-effort persistence; never crash the UI on a storage error.
  }
}

export async function removeKey(key: string): Promise<void> {
  try {
    await AsyncStorage.removeItem(key);
  } catch {
    // best-effort
  }
}