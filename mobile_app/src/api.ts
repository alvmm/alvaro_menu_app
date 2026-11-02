import AsyncStorage from '@react-native-async-storage/async-storage';

export const DEFAULT_API_URL = 'https://alvaro-menu-app.onrender.com';
const STORAGE_KEY_API_URL = '@menu_aya_api_url_v1';
const STORAGE_KEY_CACHED_STATE = '@menu_aya_cached_state_v1';

export interface MealData {
  id: string;
  name: string;
  type: string;
  ingredients: string;
  in_freezer: boolean;
  gcal_url: string;
}

export interface DayMenuEntry {
  day: string;
  date: string;
  date_str: string;
  is_holiday: boolean;
  holiday_name: string | null;
  is_festive: boolean;
  events: string;
  comida: MealData;
  cena: MealData;
}

export interface VetoHistoryEntry {
  user: string;
  day: string;
  meal_type: string;
  old_dish: string;
  new_dish: string;
  timestamp: string;
}

export interface FreezerItem {
  name: string;
  available: boolean;
  matched_dishes: string[];
}

export interface CouponItem {
  id: string;
  user: string;
  title: string;
  restaurant: string;
  expiration_date: string;
  notes: string;
  status: 'pendiente' | 'usado' | string;
  created_at?: string;
  exp_code: string;
  exp_msg: string;
  exp_color: string;
}

export interface DishItem {
  id: string;
  name: string;
  type: 'comida' | 'cena' | 'ambas' | string;
  ingredients: string;
}

export interface AppState {
  cycle_desc: string;
  auto_generated_now: boolean;
  metrics: {
    alvaro_vetos_left: number;
    ana_vetos_left: number;
    veto_limit: number;
    manual_regens_left: number;
    frozen_available: number;
    frozen_total: number;
    pending_coupons: number;
    expiring_coupons: number;
  };
  veto_window: {
    is_open: boolean;
    message: string;
    alvaro_used: number;
    ana_used: number;
    history: VetoHistoryEntry[];
  };
  menu: DayMenuEntry[];
  freezer: {
    items: FreezerItem[];
    enabled_count: number;
    disabled_count: number;
  };
  coupons: CouponItem[];
  shopping: {
    ingredients: string[];
    checked: string[];
    breakdown: Array<{
      day: string;
      dish: string;
      ingredients: string;
    }>;
  };
  dishes: DishItem[];
  settings: {
    saved: {
      sheet_url: string;
      sheet_gid_dishes: string;
      sheet_gid_freezer: string;
      calendar_ics_url: string;
      smtp_host: string;
      smtp_port: number;
      smtp_user: string;
      smtp_use_tls: boolean;
      recipients: string;
      has_saved_password: boolean;
    };
    secrets_active: {
      sheet_url: boolean;
      calendar_ics_url: boolean;
      smtp_user: boolean;
      smtp_password: boolean;
      recipients: boolean;
    };
  };
}

export async function getApiBaseUrl(): Promise<string> {
  try {
    const saved = await AsyncStorage.getItem(STORAGE_KEY_API_URL);
    if (saved && saved.trim()) {
      return saved.trim().replace(/\/+$/, '');
    }
  } catch {
    // Ignore storage read error
  }
  return DEFAULT_API_URL;
}

export async function setApiBaseUrl(url: string): Promise<string> {
  const clean = (url || DEFAULT_API_URL).trim().replace(/\/+$/, '');
  await AsyncStorage.setItem(STORAGE_KEY_API_URL, clean);
  return clean;
}

export async function getCachedState(): Promise<AppState | null> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY_CACHED_STATE);
    if (raw) {
      return JSON.parse(raw) as AppState;
    }
  } catch {
    // Ignore cache parse error
  }
  return null;
}

export async function saveCachedState(state: AppState): Promise<void> {
  try {
    await AsyncStorage.setItem(STORAGE_KEY_CACHED_STATE, JSON.stringify(state));
  } catch {
    // Ignore cache write error
  }
}

async function apiRequest<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const baseUrl = await getApiBaseUrl();
  const url = `${baseUrl}${path}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(options.headers || {}),
    },
  });

  let data: any = null;
  const text = await response.text();
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(
      `Respuesta inesperada del servidor (${response.status}). Verifica que ${baseUrl} esté activo.`
    );
  }

  if (!response.ok) {
    throw new Error(data?.detail || data?.message || `Error HTTP ${response.status}`);
  }

  if (data?.state) {
    await saveCachedState(data.state);
  }

  return data as T;
}

export const MenuApi = {
  async fetchState(): Promise<AppState> {
    const state = await apiRequest<AppState>('/api/state', { method: 'GET' });
    await saveCachedState(state);
    return state;
  },

  async syncSheets(): Promise<{ ok: boolean; message: string; state: AppState }> {
    return apiRequest('/api/sync', { method: 'POST' });
  },

  async regenerateMenu(): Promise<{ ok: boolean; message: string; state: AppState }> {
    return apiRequest('/api/menu/regenerate', { method: 'POST' });
  },

  async applyVeto(payload: {
    user: 'Álvaro' | 'Ana';
    day: string;
    meal_type: 'Comida' | 'Cena';
    override_window: boolean;
  }): Promise<{ ok: boolean; message: string; new_dish: DishItem; state: AppState }> {
    return apiRequest('/api/menu/veto', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async resetVetos(): Promise<{ ok: boolean; message: string; state: AppState }> {
    return apiRequest('/api/vetos/reset', { method: 'POST' });
  },

  async toggleFreezerItem(
    item_name: string
  ): Promise<{ ok: boolean; message: string; state: AppState }> {
    return apiRequest('/api/freezer/toggle', {
      method: 'POST',
      body: JSON.stringify({ item_name }),
    });
  },

  async createCoupon(payload: {
    user: 'Álvaro' | 'Ana';
    title: string;
    restaurant: string;
    expiration_date: string;
    notes: string;
  }): Promise<{ ok: boolean; message: string; state: AppState }> {
    return apiRequest('/api/coupons', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async toggleCoupon(
    couponId: string
  ): Promise<{ ok: boolean; message: string; state: AppState }> {
    return apiRequest(`/api/coupons/${encodeURIComponent(couponId)}/toggle`, {
      method: 'PATCH',
    });
  },

  async deleteCoupon(
    couponId: string
  ): Promise<{ ok: boolean; message: string; state: AppState }> {
    return apiRequest(`/api/coupons/${encodeURIComponent(couponId)}`, {
      method: 'DELETE',
    });
  },

  async updateShoppingChecked(
    checked: string[]
  ): Promise<{ ok: boolean; state: AppState }> {
    return apiRequest('/api/shopping/checked', {
      method: 'PUT',
      body: JSON.stringify({ checked }),
    });
  },

  async addDish(payload: {
    name: string;
    type: string;
    ingredients: string;
  }): Promise<{ ok: boolean; message: string; state: AppState }> {
    return apiRequest('/api/dishes', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async updateDish(
    dishId: string,
    payload: {
      name: string;
      type: string;
      ingredients: string;
    }
  ): Promise<{ ok: boolean; message: string; state: AppState }> {
    return apiRequest(`/api/dishes/${encodeURIComponent(dishId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },

  async deleteDish(
    dishId: string
  ): Promise<{ ok: boolean; message: string; state: AppState }> {
    return apiRequest(`/api/dishes/${encodeURIComponent(dishId)}`, {
      method: 'DELETE',
    });
  },

  async updateSettings(payload: {
    sheet_url: string;
    sheet_gid_dishes: string;
    sheet_gid_freezer: string;
    calendar_ics_url: string;
    smtp_host: string;
    smtp_port: number;
    smtp_user: string;
    smtp_password: string;
    smtp_use_tls: boolean;
    recipients: string;
  }): Promise<{ ok: boolean; message: string; state: AppState }> {
    return apiRequest('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },

  async sendEmail(is_test: boolean): Promise<{ ok: boolean; message: string }> {
    return apiRequest('/api/email/send', {
      method: 'POST',
      body: JSON.stringify({ is_test }),
    });
  },
};
