import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Modal,
  TextInput,
  Switch,
  Share,
  Linking,
  Alert,
  SafeAreaView,
  Platform,
  StatusBar as RNStatusBar,
  KeyboardAvoidingView,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import {
  AppState,
  DayMenuEntry,
  DishItem,
  MenuApi,
  DEFAULT_API_URL,
  getApiBaseUrl,
  setApiBaseUrl,
  getCachedState,
} from './src/api';

type TabKey = 'menu' | 'shopping' | 'freezer' | 'dishes' | 'settings';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('menu');
  const [state, setState] = useState<AppState | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [toast, setToast] = useState<{ text: string; type: 'ok' | 'err' } | null>(null);

  // Menu & Veto state
  const [overrideWindow, setOverrideWindow] = useState<boolean>(false);
  const [showVetoHistory, setShowVetoHistory] = useState<boolean>(false);
  const [vetoModal, setVetoModal] = useState<{
    visible: boolean;
    day: string;
    mealType: 'Comida' | 'Cena';
    dishName: string;
    selectedUser: 'Álvaro' | 'Ana';
  }>({
    visible: false,
    day: '',
    mealType: 'Comida',
    dishName: '',
    selectedUser: 'Álvaro',
  });

  // Shopping state
  const [showBreakdown, setShowBreakdown] = useState<boolean>(false);

  // Freezer & Coupons state
  const [freezerSection, setFreezerSection] = useState<'tuppers' | 'coupons'>('tuppers');
  const [couponFilter, setCouponFilter] = useState<'pendiente' | 'usado' | 'todos'>('pendiente');
  const [couponModalVisible, setCouponModalVisible] = useState<boolean>(false);
  const [newCoupon, setNewCoupon] = useState<{
    user: 'Álvaro' | 'Ana';
    title: string;
    restaurant: string;
    expiration_date: string;
    notes: string;
  }>({
    user: 'Álvaro',
    title: '',
    restaurant: '',
    expiration_date: new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
    notes: '',
  });

  // Dishes state
  const [dishSearch, setDishSearch] = useState<string>('');
  const [dishTypeFilter, setDishTypeFilter] = useState<'todos' | 'comida' | 'cena' | 'ambas'>('todos');
  const [dishModal, setDishModal] = useState<{
    visible: boolean;
    id: string | null;
    name: string;
    type: 'comida' | 'cena' | 'ambas';
    ingredients: string;
  }>({
    visible: false,
    id: null,
    name: '',
    type: 'comida',
    ingredients: '',
  });

  // Settings state
  const [apiBaseUrlInput, setApiBaseUrlInput] = useState<string>(DEFAULT_API_URL);
  const [settingsForm, setSettingsForm] = useState({
    sheet_url: '',
    sheet_gid_dishes: '83672031',
    sheet_gid_freezer: '797240193',
    calendar_ics_url: '',
    smtp_host: 'smtp.gmail.com',
    smtp_port: '587',
    smtp_user: '',
    smtp_password: '',
    smtp_use_tls: true,
    recipients: '',
  });

  const showToast = useCallback((text: string, type: 'ok' | 'err' = 'ok') => {
    setToast({ text, type });
    setTimeout(() => {
      setToast((prev) => (prev?.text === text ? null : prev));
    }, 4000);
  }, []);

  const populateSettingsForm = useCallback((appState: AppState) => {
    const s = appState.settings?.saved;
    if (!s) return;
    setSettingsForm({
      sheet_url: s.sheet_url || '',
      sheet_gid_dishes: s.sheet_gid_dishes || '83672031',
      sheet_gid_freezer: s.sheet_gid_freezer || '797240193',
      calendar_ics_url: s.calendar_ics_url || '',
      smtp_host: s.smtp_host || 'smtp.gmail.com',
      smtp_port: String(s.smtp_port || 587),
      smtp_user: s.smtp_user || '',
      smtp_password: '',
      smtp_use_tls: s.smtp_use_tls !== false,
      recipients: s.recipients || '',
    });
  }, []);

  const loadData = useCallback(
    async (isRefresh = false) => {
      if (isRefresh) {
        setRefreshing(true);
      }
      try {
        const savedUrl = await getApiBaseUrl();
        setApiBaseUrlInput(savedUrl);

        if (!isRefresh && !state) {
          const cached = await getCachedState();
          if (cached) {
            setState(cached);
            populateSettingsForm(cached);
            setLoading(false);
          }
        }

        const fresh = await MenuApi.fetchState();
        setState(fresh);
        populateSettingsForm(fresh);
      } catch (err: any) {
        showToast(err?.message || 'Error conectando con el servidor', 'err');
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [populateSettingsForm, showToast, state]
  );

  useEffect(() => {
    loadData(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Handlers ---

  const handleSyncSheets = async () => {
    setBusyAction('Sincronizando con Google Sheets...');
    try {
      const res = await MenuApi.syncSheets();
      setState(res.state);
      showToast(res.message, 'ok');
    } catch (err: any) {
      showToast(err.message || 'Error al sincronizar', 'err');
    } finally {
      setBusyAction(null);
    }
  };

  const handleRegenerateMenu = () => {
    Alert.alert(
      '🎲 Regenerar Menú Semanal',
      '¿Quieres generar una combinación nueva de platos para toda la semana? (1 regeneración manual por ciclo)',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Regenerar',
          style: 'default',
          onPress: async () => {
            setBusyAction('Generando nuevo menú semanal...');
            try {
              const res = await MenuApi.regenerateMenu();
              setState(res.state);
              showToast(res.message, 'ok');
            } catch (err: any) {
              showToast(err.message || 'No se pudo regenerar el menú', 'err');
            } finally {
              setBusyAction(null);
            }
          },
        },
      ]
    );
  };

  const openVetoModal = (day: string, mealType: 'Comida' | 'Cena', dishName: string) => {
    const isWindowOpen = state?.veto_window?.is_open ?? false;
    if (!isWindowOpen && !overrideWindow) {
      Alert.alert(
        '⏳ Plazo de vetos cerrado',
        'El plazo para vetar cerró el domingo a las 16:00. ¿Quieres activar "Permitir cambios fuera de plazo" y cambiar este plato igualmente?',
        [
          { text: 'Cancelar', style: 'cancel' },
          {
            text: 'Sí, permitir cambio',
            onPress: () => {
              setOverrideWindow(true);
              setVetoModal({
                visible: true,
                day,
                mealType,
                dishName,
                selectedUser: 'Álvaro',
              });
            },
          },
        ]
      );
      return;
    }

    setVetoModal({
      visible: true,
      day,
      mealType,
      dishName,
      selectedUser: 'Álvaro',
    });
  };

  const handleConfirmVeto = async () => {
    setVetoModal((prev) => ({ ...prev, visible: false }));
    setBusyAction(`Aplicando veto de ${vetoModal.selectedUser}...`);
    try {
      const res = await MenuApi.applyVeto({
        user: vetoModal.selectedUser,
        day: vetoModal.day,
        meal_type: vetoModal.mealType,
        override_window: overrideWindow,
      });
      setState(res.state);
      showToast(res.message, 'ok');
    } catch (err: any) {
      showToast(err.message || 'No se pudo aplicar el veto', 'err');
    } finally {
      setBusyAction(null);
    }
  };

  const handleResetVetos = () => {
    Alert.alert(
      '🔄 Reiniciar Vetos',
      '¿Restablecer el contador a 2 vetos disponibles para Álvaro y 2 para Ana?',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Reiniciar',
          onPress: async () => {
            setBusyAction('Reiniciando vetos...');
            try {
              const res = await MenuApi.resetVetos();
              setState(res.state);
              showToast(res.message, 'ok');
            } catch (err: any) {
              showToast(err.message || 'Error al reiniciar vetos', 'err');
            } finally {
              setBusyAction(null);
            }
          },
        },
      ]
    );
  };

  const handleToggleShoppingItem = async (ingredient: string) => {
    if (!state) return;
    const currentChecked = state.shopping.checked || [];
    const exists = currentChecked.includes(ingredient);
    const updated = exists
      ? currentChecked.filter((i) => i !== ingredient)
      : [...currentChecked, ingredient];

    // Optimistic update
    setState({
      ...state,
      shopping: {
        ...state.shopping,
        checked: updated,
      },
    });

    try {
      const res = await MenuApi.updateShoppingChecked(updated);
      setState(res.state);
    } catch (err: any) {
      showToast(err.message || 'Error guardando lista de compra', 'err');
    }
  };

  const handleClearShoppingChecked = async () => {
    if (!state) return;
    setState({
      ...state,
      shopping: {
        ...state.shopping,
        checked: [],
      },
    });
    try {
      const res = await MenuApi.updateShoppingChecked([]);
      setState(res.state);
      showToast('Lista de la compra desmarcada', 'ok');
    } catch (err: any) {
      showToast(err.message || 'Error limpiando lista', 'err');
    }
  };

  const handleShareShoppingList = async () => {
    if (!state) return;
    const pending = state.shopping.ingredients.filter(
      (i) => !state.shopping.checked.includes(i)
    );
    const bought = state.shopping.checked;

    const lines = [
      `🛒 *Lista de la Compra — Menú AyA*`,
      `📅 ${state.cycle_desc}`,
      '',
      `📌 *Pendientes (${pending.length}):*`,
      ...(pending.length ? pending.map((i) => `⬜ ${i}`) : ['¡Todo comprado! 🎉']),
    ];

    if (bought.length > 0) {
      lines.push('', `✅ *En el carro (${bought.length}):*`, ...bought.map((i) => `☑️ ${i}`));
    }

    try {
      await Share.share({
        message: lines.join('\n'),
      });
    } catch {
      // Share dismissed
    }
  };

  const handleToggleFreezer = async (itemName: string) => {
    setBusyAction(`Actualizando '${itemName}'...`);
    try {
      const res = await MenuApi.toggleFreezerItem(itemName);
      setState(res.state);
      showToast(res.message, 'ok');
    } catch (err: any) {
      showToast(err.message || 'Error al actualizar congelador', 'err');
    } finally {
      setBusyAction(null);
    }
  };

  const handleCreateCoupon = async () => {
    if (!newCoupon.title.trim()) {
      showToast('Escribe el título del vale o cupón', 'err');
      return;
    }
    setCouponModalVisible(false);
    setBusyAction('Guardando vale...');
    try {
      const res = await MenuApi.createCoupon(newCoupon);
      setState(res.state);
      setNewCoupon({
        user: 'Álvaro',
        title: '',
        restaurant: '',
        expiration_date: new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
        notes: '',
      });
      showToast(res.message, 'ok');
    } catch (err: any) {
      showToast(err.message || 'Error al crear vale', 'err');
    } finally {
      setBusyAction(null);
    }
  };

  const handleToggleCoupon = async (id: string) => {
    setBusyAction('Actualizando vale...');
    try {
      const res = await MenuApi.toggleCoupon(id);
      setState(res.state);
      showToast(res.message, 'ok');
    } catch (err: any) {
      showToast(err.message || 'Error al actualizar vale', 'err');
    } finally {
      setBusyAction(null);
    }
  };

  const handleDeleteCoupon = (id: string, title: string) => {
    Alert.alert('🗑️ Eliminar Vale', `¿Seguro que quieres borrar "${title}"?`, [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Eliminar',
        style: 'destructive',
        onPress: async () => {
          setBusyAction('Eliminando vale...');
          try {
            const res = await MenuApi.deleteCoupon(id);
            setState(res.state);
            showToast(res.message, 'ok');
          } catch (err: any) {
            showToast(err.message || 'Error al borrar vale', 'err');
          } finally {
            setBusyAction(null);
          }
        },
      },
    ]);
  };

  const handleSaveDish = async () => {
    if (!dishModal.name.trim()) {
      showToast('El nombre del plato es obligatorio', 'err');
      return;
    }
    const payload = {
      name: dishModal.name.trim(),
      type: dishModal.type,
      ingredients: dishModal.ingredients.trim(),
    };
    const editingId = dishModal.id;
    setDishModal((prev) => ({ ...prev, visible: false }));
    setBusyAction(editingId ? 'Actualizando plato...' : 'Añadiendo plato...');
    try {
      const res = editingId
        ? await MenuApi.updateDish(editingId, payload)
        : await MenuApi.addDish(payload);
      setState(res.state);
      showToast(res.message, 'ok');
    } catch (err: any) {
      showToast(err.message || 'Error guardando plato', 'err');
    } finally {
      setBusyAction(null);
    }
  };

  const handleDeleteDish = (dish: DishItem) => {
    Alert.alert('🗑️ Eliminar Plato', `¿Eliminar "${dish.name}" del catálogo?`, [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Eliminar',
        style: 'destructive',
        onPress: async () => {
          setDishModal((prev) => ({ ...prev, visible: false }));
          setBusyAction('Eliminando plato...');
          try {
            const res = await MenuApi.deleteDish(dish.id);
            setState(res.state);
            showToast(res.message, 'ok');
          } catch (err: any) {
            showToast(err.message || 'Error eliminando plato', 'err');
          } finally {
            setBusyAction(null);
          }
        },
      },
    ]);
  };

  const handleSaveSettings = async () => {
    setBusyAction('Guardando configuración...');
    try {
      const cleanUrl = await setApiBaseUrl(apiBaseUrlInput);
      setApiBaseUrlInput(cleanUrl);
      const res = await MenuApi.updateSettings({
        ...settingsForm,
        smtp_port: parseInt(settingsForm.smtp_port, 10) || 587,
      });
      setState(res.state);
      showToast(res.message, 'ok');
    } catch (err: any) {
      showToast(err.message || 'Error guardando ajustes', 'err');
    } finally {
      setBusyAction(null);
    }
  };

  const handleSendEmail = async (isTest: boolean) => {
    setBusyAction(isTest ? 'Enviando email de prueba...' : 'Enviando menú semanal por email...');
    try {
      const res = await MenuApi.sendEmail(isTest);
      showToast(res.message, 'ok');
    } catch (err: any) {
      showToast(err.message || 'Error enviando correo', 'err');
    } finally {
      setBusyAction(null);
    }
  };

  // Filtered dishes
  const filteredDishes = useMemo(() => {
    if (!state?.dishes) return [];
    const q = dishSearch.trim().toLowerCase();
    return state.dishes.filter((d) => {
      const matchesType =
        dishTypeFilter === 'todos' || (d.type || '').toLowerCase() === dishTypeFilter;
      const matchesQuery =
        !q ||
        d.name.toLowerCase().includes(q) ||
        (d.ingredients || '').toLowerCase().includes(q);
      return matchesType && matchesQuery;
    });
  }, [state?.dishes, dishSearch, dishTypeFilter]);

  // Filtered coupons
  const filteredCoupons = useMemo(() => {
    if (!state?.coupons) return [];
    if (couponFilter === 'todos') return state.coupons;
    return state.coupons.filter((c) => c.status === couponFilter);
  }, [state?.coupons, couponFilter]);

  if (loading && !state) {
    return (
      <SafeAreaView style={styles.loadingScreen}>
        <StatusBar style="light" />
        <ActivityIndicator size="large" color="#FFFFFF" />
        <Text style={styles.loadingTitle}>Menú Semanal · Álvaro & Ana</Text>
        <Text style={styles.loadingSub}>Conectando con el servidor en la nube...</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" backgroundColor="#1E3A8A" />

      {/* Header Superior Nativo */}
      <View style={styles.topHeader}>
        <View style={styles.topHeaderLeft}>
          <Text style={styles.appTitle}>🍽️ Menú Álvaro & Ana</Text>
          <Text style={styles.cycleSubtitle} numberOfLines={1}>
            {state?.cycle_desc || 'Cargando ciclo semanal...'}
          </Text>
        </View>
        <View style={styles.topHeaderActions}>
          <TouchableOpacity
            style={styles.headerIconBtn}
            onPress={handleSyncSheets}
            activeOpacity={0.75}
          >
            <Text style={styles.headerIconText}>🔄 Sheets</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.headerIconBtn, styles.headerPrimaryBtn]}
            onPress={handleRegenerateMenu}
            activeOpacity={0.75}
          >
            <Text style={styles.headerPrimaryBtnText}>🎲 Regenerar</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Banner de estado o Toast */}
      {busyAction && (
        <View style={styles.busyBanner}>
          <ActivityIndicator size="small" color="#1E3A8A" />
          <Text style={styles.busyBannerText}>{busyAction}</Text>
        </View>
      )}
      {toast && (
        <View
          style={[
            styles.toastBanner,
            toast.type === 'err' ? styles.toastErr : styles.toastOk,
          ]}
        >
          <Text style={styles.toastText}>{toast.text}</Text>
        </View>
      )}

      {/* Contenido Principal con Pull-to-Refresh */}
      <ScrollView
        style={styles.contentScroll}
        contentContainerStyle={styles.contentContainer}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => loadData(true)}
            colors={['#1E3A8A']}
            tintColor="#1E3A8A"
          />
        }
      >
        {/* ==================== TAB 1: MENÚ SEMANAL ==================== */}
        {activeTab === 'menu' && state && (
          <View>
            {/* 4 Tarjetas de Métricas */}
            <View style={styles.metricsRow}>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Vetos Álvaro</Text>
                <Text style={styles.metricValue}>
                  {state.metrics.alvaro_vetos_left}/{state.metrics.veto_limit}
                </Text>
              </View>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Vetos Ana</Text>
                <Text style={styles.metricValue}>
                  {state.metrics.ana_vetos_left}/{state.metrics.veto_limit}
                </Text>
              </View>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Congelador</Text>
                <Text style={styles.metricValue}>
                  {state.metrics.frozen_available}/{state.metrics.frozen_total}
                </Text>
              </View>
              <View style={styles.metricCard}>
                <Text style={styles.metricLabel}>Vales</Text>
                <Text style={styles.metricValue}>{state.metrics.pending_coupons}</Text>
              </View>
            </View>

            {/* Barra de Estado de Vetos */}
            <View
              style={[
                styles.vetoBannerCard,
                state.veto_window.is_open ? styles.vetoOpenBg : styles.vetoClosedBg,
              ]}
            >
              <View style={styles.vetoBannerHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.vetoBannerTitle}>
                    {state.veto_window.is_open ? '🟢 Ventana de Vetos Abierta' : '🔒 Menú Confirmado'}
                  </Text>
                  <Text style={styles.vetoBannerSub}>{state.veto_window.message}</Text>
                </View>
                <TouchableOpacity style={styles.smallOutlineBtn} onPress={handleResetVetos}>
                  <Text style={styles.smallOutlineBtnText}>Reiniciar vetos</Text>
                </TouchableOpacity>
              </View>

              <View style={styles.overrideSwitchRow}>
                <Text style={styles.overrideSwitchLabel}>
                  Permitir cambios fuera de plazo (excepción)
                </Text>
                <Switch
                  value={overrideWindow}
                  onValueChange={setOverrideWindow}
                  trackColor={{ false: '#CBD5E1', true: '#93C5FD' }}
                  thumbColor={overrideWindow ? '#1D4ED8' : '#F8FAFC'}
                />
              </View>

              {state.veto_window.history.length > 0 && (
                <View style={styles.historyBox}>
                  <TouchableOpacity
                    onPress={() => setShowVetoHistory(!showVetoHistory)}
                    style={styles.historyToggleBtn}
                  >
                    <Text style={styles.historyToggleText}>
                      {showVetoHistory ? '▲ Ocultar historial de cambios' : `▼ Ver historial de cambios (${state.veto_window.history.length})`}
                    </Text>
                  </TouchableOpacity>
                  {showVetoHistory &&
                    state.veto_window.history.slice(0, 6).map((h, idx) => (
                      <Text key={idx} style={styles.historyItemText}>
                        • <Text style={{ fontWeight: '700' }}>{h.user}</Text> cambió {h.meal_type} del{' '}
                        {h.day}: <Text style={{ textDecorationLine: 'line-through' }}>{h.old_dish}</Text>{' '}
                        → <Text style={{ fontWeight: '700', color: '#1E40AF' }}>{h.new_dish}</Text>
                      </Text>
                    ))}
                </View>
              )}
            </View>

            {/* Tarjetas de los 7 Días */}
            {state.menu.map((dayEntry: DayMenuEntry) => (
              <View
                key={dayEntry.day}
                style={[
                  styles.dayCard,
                  dayEntry.is_festive ? styles.dayCardFestive : null,
                ]}
              >
                <View style={styles.dayCardHeader}>
                  <View style={styles.dayTitleRow}>
                    <Text style={styles.dayNameText}>{dayEntry.day}</Text>
                    <Text style={styles.dayDateBadge}>{dayEntry.date_str}</Text>
                  </View>
                  {dayEntry.is_holiday ? (
                    <View style={[styles.tagPill, styles.tagHoliday]}>
                      <Text style={styles.tagHolidayText}>
                        🎉 {dayEntry.holiday_name || 'Festivo'}
                      </Text>
                    </View>
                  ) : dayEntry.is_festive ? (
                    <View style={[styles.tagPill, styles.tagWeekend]}>
                      <Text style={styles.tagWeekendText}>✨ Fin de semana</Text>
                    </View>
                  ) : null}
                </View>

                {dayEntry.events ? (
                  <View style={styles.calendarEventAlert}>
                    <Text style={styles.calendarEventText}>📅 {dayEntry.events}</Text>
                  </View>
                ) : null}

                {/* Comida y Cena */}
                {(['comida', 'cena'] as const).map((mealKey) => {
                  const meal = dayEntry[mealKey];
                  const isLunch = mealKey === 'comida';
                  const mealLabel = isLunch ? 'Comida' : 'Cena';
                  return (
                    <View key={mealKey} style={styles.mealBlock}>
                      <View style={styles.mealHeaderRow}>
                        <Text style={styles.mealTypeLabel}>
                          {isLunch ? '☀️ COMIDA · 14:00' : '🌙 CENA · 21:00'}
                        </Text>
                        {meal.in_freezer && (
                          <View style={styles.freezerBadge}>
                            <Text style={styles.freezerBadgeText}>🧊 En congelador</Text>
                          </View>
                        )}
                      </View>

                      <Text style={styles.dishTitleText}>{meal.name}</Text>
                      {meal.ingredients ? (
                        <Text style={styles.dishIngredientsText}>🧾 {meal.ingredients}</Text>
                      ) : null}

                      <View style={styles.mealActionsRow}>
                        <TouchableOpacity
                          style={styles.vetoActionBtn}
                          onPress={() => openVetoModal(dayEntry.day, mealLabel, meal.name)}
                        >
                          <Text style={styles.vetoActionBtnText}>⚡ Vetar plato</Text>
                        </TouchableOpacity>

                        {meal.gcal_url ? (
                          <TouchableOpacity
                            style={styles.calActionBtn}
                            onPress={() => Linking.openURL(meal.gcal_url)}
                          >
                            <Text style={styles.calActionBtnText}>📅 + Google Cal</Text>
                          </TouchableOpacity>
                        ) : null}
                      </View>
                    </View>
                  );
                })}
              </View>
            ))}
          </View>
        )}

        {/* ==================== TAB 2: LISTA DE LA COMPRA ==================== */}
        {activeTab === 'shopping' && state && (
          <View>
            <View style={styles.sectionCard}>
              <View style={styles.sectionHeaderRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.sectionTitle}>🛒 Lista de la Compra</Text>
                  <Text style={styles.sectionSub}>
                    {state.shopping.checked.length} de {state.shopping.ingredients.length}{' '}
                    ingredientes comprados
                  </Text>
                </View>
                <TouchableOpacity
                  style={styles.primaryActionBtn}
                  onPress={handleShareShoppingList}
                >
                  <Text style={styles.primaryActionBtnText}>📤 Compartir</Text>
                </TouchableOpacity>
              </View>

              {/* Barra de Progreso */}
              <View style={styles.progressBarBg}>
                <View
                  style={[
                    styles.progressBarFill,
                    {
                      width: `${
                        state.shopping.ingredients.length
                          ? Math.round(
                              (state.shopping.checked.length /
                                state.shopping.ingredients.length) *
                                100
                            )
                          : 0
                      }%`,
                    },
                  ]}
                />
              </View>

              {state.shopping.checked.length > 0 && (
                <TouchableOpacity
                  style={styles.clearCheckedBtn}
                  onPress={handleClearShoppingChecked}
                >
                  <Text style={styles.clearCheckedBtnText}>
                    🔄 Desmarcar todos ({state.shopping.checked.length})
                  </Text>
                </TouchableOpacity>
              )}

              {/* Checklist Nativa */}
              <View style={styles.shoppingListContainer}>
                {state.shopping.ingredients.map((ing) => {
                  const isChecked = state.shopping.checked.includes(ing);
                  return (
                    <TouchableOpacity
                      key={ing}
                      style={[
                        styles.shoppingItemRow,
                        isChecked ? styles.shoppingItemRowChecked : null,
                      ]}
                      onPress={() => handleToggleShoppingItem(ing)}
                      activeOpacity={0.7}
                    >
                      <View
                        style={[
                          styles.checkboxSquare,
                          isChecked ? styles.checkboxSquareChecked : null,
                        ]}
                      >
                        {isChecked && <Text style={styles.checkboxTick}>✓</Text>}
                      </View>
                      <Text
                        style={[
                          styles.shoppingItemText,
                          isChecked ? styles.shoppingItemTextChecked : null,
                        ]}
                      >
                        {ing}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>

            {/* Desglose por Plato */}
            <View style={styles.sectionCard}>
              <TouchableOpacity
                onPress={() => setShowBreakdown(!showBreakdown)}
                style={styles.sectionHeaderRow}
              >
                <Text style={styles.sectionTitle}>
                  📋 Desglose por plato ({state.shopping.breakdown.length})
                </Text>
                <Text style={styles.expandToggleText}>{showBreakdown ? '▲' : '▼'}</Text>
              </TouchableOpacity>
              {showBreakdown &&
                state.shopping.breakdown.map((b, i) => (
                  <View key={i} style={styles.breakdownRow}>
                    <Text style={styles.breakdownDay}>
                      {b.day} · {b.dish}
                    </Text>
                    <Text style={styles.breakdownIng}>{b.ingredients}</Text>
                  </View>
                ))}
            </View>
          </View>
        )}

        {/* ==================== TAB 3: CONGELADOR & VALES ==================== */}
        {activeTab === 'freezer' && state && (
          <View>
            <View style={styles.segmentedControl}>
              <TouchableOpacity
                style={[
                  styles.segmentBtn,
                  freezerSection === 'tuppers' ? styles.segmentBtnActive : null,
                ]}
                onPress={() => setFreezerSection('tuppers')}
              >
                <Text
                  style={[
                    styles.segmentBtnText,
                    freezerSection === 'tuppers' ? styles.segmentBtnTextActive : null,
                  ]}
                >
                  🧊 Congelador ({state.freezer.enabled_count}/{state.freezer.items.length})
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.segmentBtn,
                  freezerSection === 'coupons' ? styles.segmentBtnActive : null,
                ]}
                onPress={() => setFreezerSection('coupons')}
              >
                <Text
                  style={[
                    styles.segmentBtnText,
                    freezerSection === 'coupons' ? styles.segmentBtnTextActive : null,
                  ]}
                >
                  🎟️ Vales ({state.metrics.pending_coupons})
                </Text>
              </TouchableOpacity>
            </View>

            {freezerSection === 'tuppers' ? (
              <View style={styles.sectionCard}>
                <Text style={styles.sectionTitle}>🧊 Stock del Congelador</Text>
                <Text style={styles.sectionSub}>
                  Los platos disponibles tienen prioridad en el generador semanal. Toca el
                  interruptor para marcar si queda o se ha agotado.
                </Text>

                {state.freezer.items.map((item) => (
                  <View key={item.name} style={styles.freezerItemCard}>
                    <View style={{ flex: 1, paddingRight: 10 }}>
                      <Text style={styles.freezerItemName}>{item.name}</Text>
                      <Text style={styles.freezerItemMatches}>
                        {item.matched_dishes.length > 0
                          ? `Platos asociados: ${item.matched_dishes.join(', ')}`
                          : 'Tupper directo del congelador'}
                      </Text>
                    </View>
                    <Switch
                      value={item.available}
                      onValueChange={() => handleToggleFreezer(item.name)}
                      trackColor={{ false: '#CBD5E1', true: '#6EE7B7' }}
                      thumbColor={item.available ? '#059669' : '#94A3B8'}
                    />
                  </View>
                ))}
              </View>
            ) : (
              <View style={styles.sectionCard}>
                <View style={styles.sectionHeaderRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.sectionTitle}>🎟️ Vales y Cupones Gourmet</Text>
                    <Text style={styles.sectionSub}>
                       Avisos de caducidad para cenas y caprichos
                    </Text>
                  </View>
                  <TouchableOpacity
                    style={styles.primaryActionBtn}
                    onPress={() => setCouponModalVisible(true)}
                  >
                    <Text style={styles.primaryActionBtnText}>+ Nuevo Vale</Text>
                  </TouchableOpacity>
                </View>

                <View style={styles.filterPillsRow}>
                  {(['pendiente', 'usado', 'todos'] as const).map((f) => (
                    <TouchableOpacity
                      key={f}
                      style={[
                        styles.filterPill,
                        couponFilter === f ? styles.filterPillActive : null,
                      ]}
                      onPress={() => setCouponFilter(f)}
                    >
                      <Text
                        style={[
                          styles.filterPillText,
                          couponFilter === f ? styles.filterPillTextActive : null,
                        ]}
                      >
                        {f.toUpperCase()}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>

                {filteredCoupons.length === 0 ? (
                  <Text style={styles.emptyStateText}>No hay vales en este filtro.</Text>
                ) : (
                  filteredCoupons.map((c) => (
                    <View key={c.id} style={styles.couponCard}>
                      <View style={styles.couponTopRow}>
                        <Text style={styles.couponTitle}>{c.title}</Text>
                        <Text style={styles.couponUserBadge}>👤 {c.user}</Text>
                      </View>
                      {c.restaurant ? (
                        <Text style={styles.couponMetaText}>📍 {c.restaurant}</Text>
                      ) : null}
                      <Text style={styles.couponExpText}>{c.exp_msg}</Text>
                      {c.notes ? <Text style={styles.couponNotesText}>📝 {c.notes}</Text> : null}

                      <View style={styles.couponActionsRow}>
                        <TouchableOpacity
                          style={styles.smallOutlineBtn}
                          onPress={() => handleToggleCoupon(c.id)}
                        >
                          <Text style={styles.smallOutlineBtnText}>
                            {c.status === 'pendiente' ? '✅ Marcar usado' : '↩️ Reabrir'}
                          </Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                          style={styles.smallDangerBtn}
                          onPress={() => handleDeleteCoupon(c.id, c.title)}
                        >
                          <Text style={styles.smallDangerBtnText}>🗑️ Borrar</Text>
                        </TouchableOpacity>
                      </View>
                    </View>
                  ))
                )}
              </View>
            )}
          </View>
        )}

        {/* ==================== TAB 4: CATÁLOGO DE PLATOS ==================== */}
        {activeTab === 'dishes' && state && (
          <View style={styles.sectionCard}>
            <View style={styles.sectionHeaderRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.sectionTitle}>
                  🍲 Catálogo ({filteredDishes.length}/{state.dishes.length})
                </Text>
                <Text style={styles.sectionSub}>Toca cualquier plato para editar sus ingredientes</Text>
              </View>
              <TouchableOpacity
                style={styles.primaryActionBtn}
                onPress={() =>
                  setDishModal({
                    visible: true,
                    id: null,
                    name: '',
                    type: 'comida',
                    ingredients: '',
                  })
                }
              >
                <Text style={styles.primaryActionBtnText}>+ Añadir</Text>
              </TouchableOpacity>
            </View>

            <TextInput
              style={styles.searchInput}
              placeholder="🔍 Buscar por plato o ingrediente..."
              placeholderTextColor="#94A3B8"
              value={dishSearch}
              onChangeText={setDishSearch}
            />

            <View style={styles.filterPillsRow}>
              {(
                [
                  { k: 'todos', label: 'Todos' },
                  { k: 'comida', label: '☀️ Comida' },
                  { k: 'cena', label: '🌙 Cena' },
                  { k: 'ambas', label: '🔄 Ambas' },
                ] as const
              ).map((item) => (
                <TouchableOpacity
                  key={item.k}
                  style={[
                    styles.filterPill,
                    dishTypeFilter === item.k ? styles.filterPillActive : null,
                  ]}
                  onPress={() => setDishTypeFilter(item.k)}
                >
                  <Text
                    style={[
                      styles.filterPillText,
                      dishTypeFilter === item.k ? styles.filterPillTextActive : null,
                    ]}
                  >
                    {item.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {filteredDishes.map((dish) => (
              <TouchableOpacity
                key={dish.id}
                style={styles.dishCatalogCard}
                onPress={() =>
                  setDishModal({
                    visible: true,
                    id: dish.id,
                    name: dish.name,
                    type: (dish.type as any) || 'ambas',
                    ingredients: dish.ingredients || '',
                  })
                }
              >
                <View style={styles.dishCatalogHeader}>
                  <Text style={styles.dishCatalogName}>{dish.name}</Text>
                  <View style={styles.dishTypeBadge}>
                    <Text style={styles.dishTypeBadgeText}>{dish.type.toUpperCase()}</Text>
                  </View>
                </View>
                <Text style={styles.dishCatalogIng}>
                  {dish.ingredients || 'Sin ingredientes especificados'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* ==================== TAB 5: AJUSTES, EMAIL Y CALENDARIO ==================== */}
        {activeTab === 'settings' && state && (
          <View>
            {/* Suscripción a Calendario (.ics) */}
            <View style={styles.sectionCard}>
              <Text style={styles.sectionTitle}>📲 Suscripción a Calendario (.ics)</Text>
              <Text style={styles.sectionSub}>
                Sincroniza todas las comidas (14:00) y cenas (21:00) en el calendario nativo de
                tu iPhone o Android.
              </Text>
              <View style={styles.settingsBtnGroup}>
                <TouchableOpacity
                  style={styles.primaryActionBtn}
                  onPress={() =>
                    Linking.openURL(`${apiBaseUrlInput}/menu_semanal_AyA.ics`)
                  }
                >
                  <Text style={styles.primaryActionBtnText}>📅 Abrir / Suscribir Calendario</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.smallOutlineBtn}
                  onPress={() =>
                    Share.share({
                      message: `${apiBaseUrlInput}/menu_semanal_AyA.ics`,
                    })
                  }
                >
                  <Text style={styles.smallOutlineBtnText}>📋 Compartir URL .ics</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* Envío de Email Semanal */}
            <View style={styles.sectionCard}>
              <Text style={styles.sectionTitle}>✉️ Enviar Menú por Correo</Text>
              <Text style={styles.sectionSub}>
                Envía el resumen semanal HTML con lista de la compra a Álvaro y Ana.
              </Text>
              <View style={styles.settingsBtnGroup}>
                <TouchableOpacity
                  style={styles.smallOutlineBtn}
                  onPress={() => handleSendEmail(true)}
                >
                  <Text style={styles.smallOutlineBtnText}>🧪 Enviar Prueba</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.primaryActionBtn}
                  onPress={() => handleSendEmail(false)}
                >
                  <Text style={styles.primaryActionBtnText}>🚀 Enviar Menú Oficial</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* Estado de Variables en Render */}
            <View style={styles.sectionCard}>
              <Text style={styles.sectionTitle}>🔐 Estado de Secretos en Render</Text>
              <Text style={styles.sectionSub}>
                Variables configuradas de forma segura en el servidor en la nube:
              </Text>
              <View style={styles.secretsStatusGrid}>
                {[
                  { label: 'Google Sheets URL', ok: state.settings.secrets_active.sheet_url },
                  { label: 'Google Calendar ICS', ok: state.settings.secrets_active.calendar_ics_url },
                  { label: 'Usuario SMTP', ok: state.settings.secrets_active.smtp_user },
                  { label: 'Password SMTP', ok: state.settings.secrets_active.smtp_password },
                  { label: 'Destinatarios', ok: state.settings.secrets_active.recipients },
                ].map((item) => (
                  <View key={item.label} style={styles.secretBadge}>
                    <Text style={styles.secretBadgeText}>
                      {item.ok ? '✅' : '⚪'} {item.label}
                    </Text>
                  </View>
                ))}
              </View>

              <Text style={styles.inputLabel}>Servidor Backend (Render URL)</Text>
              <TextInput
                style={styles.textInput}
                value={apiBaseUrlInput}
                onChangeText={setApiBaseUrlInput}
                autoCapitalize="none"
                keyboardType="url"
              />

              <TouchableOpacity
                style={[styles.primaryActionBtn, { marginTop: 12, alignSelf: 'flex-start' }]}
                onPress={handleSaveSettings}
              >
                <Text style={styles.primaryActionBtnText}>💾 Guardar Conexión y Ajustes</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
      </ScrollView>

      {/* ==================== MODAL NATIVO DE VETO ==================== */}
      <Modal
        visible={vetoModal.visible}
        transparent
        animationType="slide"
        onRequestClose={() => setVetoModal((p) => ({ ...p, visible: false }))}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>⚡ Vetar Plato</Text>
            <Text style={styles.modalSubtitle}>
              {vetoModal.day} ({vetoModal.mealType}):{' '}
              <Text style={{ fontWeight: '700', color: '#1E293B' }}>{vetoModal.dishName}</Text>
            </Text>

            <Text style={styles.inputLabel}>¿Quién aplica el veto?</Text>
            <View style={styles.userSelectorRow}>
              {(['Álvaro', 'Ana'] as const).map((u) => (
                <TouchableOpacity
                  key={u}
                  style={[
                    styles.userOptionBtn,
                    vetoModal.selectedUser === u ? styles.userOptionBtnActive : null,
                  ]}
                  onPress={() => setVetoModal((p) => ({ ...p, selectedUser: u }))}
                >
                  <Text
                    style={[
                      styles.userOptionText,
                      vetoModal.selectedUser === u ? styles.userOptionTextActive : null,
                    ]}
                  >
                    👤 {u} (
                    {u === 'Álvaro'
                      ? state?.metrics.alvaro_vetos_left
                      : state?.metrics.ana_vetos_left}{' '}
                    libres)
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <View style={styles.modalButtonsRow}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setVetoModal((p) => ({ ...p, visible: false }))}
              >
                <Text style={styles.modalCancelText}>Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalConfirmBtn} onPress={handleConfirmVeto}>
                <Text style={styles.modalConfirmText}>Cambiar por otro plato</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ==================== MODAL NATIVO DE CUPÓN ==================== */}
      <Modal
        visible={couponModalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setCouponModalVisible(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.modalBackdrop}
        >
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>🎟️ Nuevo Vale o Cupón</Text>

            <Text style={styles.inputLabel}>Propietario</Text>
            <View style={styles.userSelectorRow}>
              {(['Álvaro', 'Ana'] as const).map((u) => (
                <TouchableOpacity
                  key={u}
                  style={[
                    styles.userOptionBtn,
                    newCoupon.user === u ? styles.userOptionBtnActive : null,
                  ]}
                  onPress={() => setNewCoupon((p) => ({ ...p, user: u }))}
                >
                  <Text
                    style={[
                      styles.userOptionText,
                      newCoupon.user === u ? styles.userOptionTextActive : null,
                    ]}
                  >
                    👤 {u}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.inputLabel}>Título del vale *</Text>
            <TextInput
              style={styles.textInput}
              placeholder="Ej: 2x1 en Pizzería o Vale Cena Romántica"
              value={newCoupon.title}
              onChangeText={(t) => setNewCoupon((p) => ({ ...p, title: t }))}
            />

            <Text style={styles.inputLabel}>Restaurante / Lugar</Text>
            <TextInput
              style={styles.textInput}
              placeholder="Ej: Grosso Napoletano"
              value={newCoupon.restaurant}
              onChangeText={(t) => setNewCoupon((p) => ({ ...p, restaurant: t }))}
            />

            <Text style={styles.inputLabel}>Fecha caducidad (AAAA-MM-DD)</Text>
            <TextInput
              style={styles.textInput}
              placeholder="2026-12-31"
              value={newCoupon.expiration_date}
              onChangeText={(t) => setNewCoupon((p) => ({ ...p, expiration_date: t }))}
            />

            <Text style={styles.inputLabel}>Notas</Text>
            <TextInput
              style={styles.textInput}
              placeholder="Condiciones, código..."
              value={newCoupon.notes}
              onChangeText={(t) => setNewCoupon((p) => ({ ...p, notes: t }))}
            />

            <View style={styles.modalButtonsRow}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setCouponModalVisible(false)}
              >
                <Text style={styles.modalCancelText}>Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalConfirmBtn} onPress={handleCreateCoupon}>
                <Text style={styles.modalConfirmText}>Guardar Vale</Text>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* ==================== MODAL NATIVO DE PLATO ==================== */}
      <Modal
        visible={dishModal.visible}
        transparent
        animationType="slide"
        onRequestClose={() => setDishModal((p) => ({ ...p, visible: false }))}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.modalBackdrop}
        >
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>
              {dishModal.id ? '✏️ Editar Plato' : '🍲 Añadir Plato'}
            </Text>

            <Text style={styles.inputLabel}>Nombre del plato *</Text>
            <TextInput
              style={styles.textInput}
              placeholder="Ej: Lentejas estofadas"
              value={dishModal.name}
              onChangeText={(t) => setDishModal((p) => ({ ...p, name: t }))}
            />

            <Text style={styles.inputLabel}>Tipo de comida</Text>
            <View style={styles.userSelectorRow}>
              {(['comida', 'cena', 'ambas'] as const).map((t) => (
                <TouchableOpacity
                  key={t}
                  style={[
                    styles.userOptionBtn,
                    dishModal.type === t ? styles.userOptionBtnActive : null,
                  ]}
                  onPress={() => setDishModal((p) => ({ ...p, type: t }))}
                >
                  <Text
                    style={[
                      styles.userOptionText,
                      dishModal.type === t ? styles.userOptionTextActive : null,
                    ]}
                  >
                    {t.toUpperCase()}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.inputLabel}>Ingredientes (separados por comas)</Text>
            <TextInput
              style={[styles.textInput, { minHeight: 70, textAlignVertical: 'top' }]}
              multiline
              placeholder="Ej: Lentejas, zanahoria, patata, chorizo"
              value={dishModal.ingredients}
              onChangeText={(t) => setDishModal((p) => ({ ...p, ingredients: t }))}
            />

            <View style={styles.modalButtonsRow}>
              {dishModal.id && (
                <TouchableOpacity
                  style={styles.smallDangerBtn}
                  onPress={() =>
                    handleDeleteDish({
                      id: dishModal.id!,
                      name: dishModal.name,
                      type: dishModal.type,
                      ingredients: dishModal.ingredients,
                    })
                  }
                >
                  <Text style={styles.smallDangerBtnText}>🗑️ Eliminar</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setDishModal((p) => ({ ...p, visible: false }))}
              >
                <Text style={styles.modalCancelText}>Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalConfirmBtn} onPress={handleSaveDish}>
                <Text style={styles.modalConfirmText}>Guardar</Text>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* ==================== BARRA DE NAVEGACIÓN INFERIOR NATIVA ==================== */}
      <View style={styles.bottomTabBar}>
        {(
          [
            { key: 'menu', icon: '📅', label: 'Menú' },
            { key: 'shopping', icon: '🛒', label: 'Compra' },
            { key: 'freezer', icon: '🧊', label: 'Congelador' },
            { key: 'dishes', icon: '🍲', label: 'Platos' },
            { key: 'settings', icon: '⚙️', label: 'Ajustes' },
          ] as const
        ).map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <TouchableOpacity
              key={tab.key}
              style={styles.bottomTabItem}
              onPress={() => setActiveTab(tab.key)}
              activeOpacity={0.7}
            >
              <Text style={[styles.bottomTabIcon, isActive ? styles.bottomTabIconActive : null]}>
                {tab.icon}
              </Text>
              <Text style={[styles.bottomTabLabel, isActive ? styles.bottomTabLabelActive : null]}>
                {tab.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#F1F5F9',
    paddingTop: Platform.OS === 'android' ? RNStatusBar.currentHeight || 0 : 0,
  },
  loadingScreen: {
    flex: 1,
    backgroundColor: '#1E3A8A',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  loadingTitle: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '800',
    marginTop: 16,
  },
  loadingSub: {
    color: '#BFDBFE',
    fontSize: 14,
    marginTop: 6,
  },
  topHeader: {
    backgroundColor: '#1E3A8A',
    paddingHorizontal: 16,
    paddingVertical: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  topHeaderLeft: {
    flex: 1,
    paddingRight: 8,
  },
  appTitle: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '800',
  },
  cycleSubtitle: {
    color: '#BFDBFE',
    fontSize: 12,
    marginTop: 2,
  },
  topHeaderActions: {
    flexDirection: 'row',
    gap: 8,
  },
  headerIconBtn: {
    backgroundColor: 'rgba(255,255,255,0.16)',
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 8,
  },
  headerIconText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  headerPrimaryBtn: {
    backgroundColor: '#3B82F6',
  },
  headerPrimaryBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  busyBanner: {
    backgroundColor: '#DBEAFE',
    paddingVertical: 8,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  busyBannerText: {
    color: '#1E3A8A',
    fontSize: 13,
    fontWeight: '600',
  },
  toastBanner: {
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  toastOk: {
    backgroundColor: '#059669',
  },
  toastErr: {
    backgroundColor: '#DC2626',
  },
  toastText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '700',
    textAlign: 'center',
  },
  contentScroll: {
    flex: 1,
  },
  contentContainer: {
    padding: 14,
    paddingBottom: 32,
  },
  metricsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  metricCard: {
    flex: 1,
    minWidth: '22%',
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 10,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  metricLabel: {
    fontSize: 11,
    color: '#64748B',
    fontWeight: '600',
  },
  metricValue: {
    fontSize: 18,
    fontWeight: '800',
    color: '#0F172A',
    marginTop: 2,
  },
  vetoBannerCard: {
    borderRadius: 14,
    padding: 14,
    marginBottom: 14,
    borderWidth: 1,
  },
  vetoOpenBg: {
    backgroundColor: '#ECFDF5',
    borderColor: '#A7F3D0',
  },
  vetoClosedBg: {
    backgroundColor: '#F8FAFC',
    borderColor: '#CBD5E1',
  },
  vetoBannerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  vetoBannerTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: '#0F172A',
  },
  vetoBannerSub: {
    fontSize: 12,
    color: '#475569',
    marginTop: 2,
  },
  overrideSwitchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: 'rgba(148,163,184,0.25)',
  },
  overrideSwitchLabel: {
    fontSize: 12,
    color: '#334155',
    fontWeight: '600',
    flex: 1,
  },
  historyBox: {
    marginTop: 8,
  },
  historyToggleBtn: {
    paddingVertical: 4,
  },
  historyToggleText: {
    fontSize: 12,
    color: '#2563EB',
    fontWeight: '700',
  },
  historyItemText: {
    fontSize: 12,
    color: '#334155',
    marginTop: 4,
  },
  dayCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  dayCardFestive: {
    borderColor: '#93C5FD',
    backgroundColor: '#F8FAFC',
  },
  dayCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  dayTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  dayNameText: {
    fontSize: 18,
    fontWeight: '800',
    color: '#0F172A',
  },
  dayDateBadge: {
    fontSize: 12,
    fontWeight: '700',
    color: '#475569',
    backgroundColor: '#F1F5F9',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  tagPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 99,
  },
  tagHoliday: {
    backgroundColor: '#FEF3C7',
  },
  tagHolidayText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#B45309',
  },
  tagWeekend: {
    backgroundColor: '#DBEAFE',
  },
  tagWeekendText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#1D4ED8',
  },
  calendarEventAlert: {
    backgroundColor: '#EFF6FF',
    borderLeftWidth: 3,
    borderLeftColor: '#3B82F6',
    padding: 8,
    borderRadius: 6,
    marginBottom: 8,
  },
  calendarEventText: {
    fontSize: 12,
    color: '#1E40AF',
    fontWeight: '600',
  },
  mealBlock: {
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    padding: 12,
    marginTop: 8,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  mealHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  mealTypeLabel: {
    fontSize: 11,
    fontWeight: '800',
    color: '#64748B',
    letterSpacing: 0.4,
  },
  freezerBadge: {
    backgroundColor: '#E0F2FE',
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 6,
  },
  freezerBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#0369A1',
  },
  dishTitleText: {
    fontSize: 16,
    fontWeight: '800',
    color: '#0F172A',
  },
  dishIngredientsText: {
    fontSize: 12,
    color: '#475569',
    marginTop: 4,
  },
  mealActionsRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 10,
  },
  vetoActionBtn: {
    backgroundColor: '#EFF6FF',
    borderWidth: 1,
    borderColor: '#BFDBFE',
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
  },
  vetoActionBtnText: {
    color: '#1D4ED8',
    fontSize: 12,
    fontWeight: '700',
  },
  calActionBtn: {
    backgroundColor: '#F1F5F9',
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
  },
  calActionBtnText: {
    color: '#334155',
    fontSize: 12,
    fontWeight: '600',
  },
  sectionCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: '#0F172A',
  },
  sectionSub: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 3,
  },
  primaryActionBtn: {
    backgroundColor: '#2563EB',
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 10,
  },
  primaryActionBtnText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '700',
  },
  smallOutlineBtn: {
    borderWidth: 1,
    borderColor: '#CBD5E1',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
  },
  smallOutlineBtnText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#334155',
  },
  smallDangerBtn: {
    borderWidth: 1,
    borderColor: '#FECACA',
    backgroundColor: '#FEF2F2',
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
  },
  smallDangerBtnText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#DC2626',
  },
  progressBarBg: {
    height: 8,
    backgroundColor: '#E2E8F0',
    borderRadius: 99,
    overflow: 'hidden',
    marginTop: 12,
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#10B981',
  },
  clearCheckedBtn: {
    marginTop: 10,
    alignSelf: 'flex-start',
  },
  clearCheckedBtnText: {
    fontSize: 12,
    color: '#2563EB',
    fontWeight: '700',
  },
  shoppingListContainer: {
    marginTop: 12,
  },
  shoppingItemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 11,
    paddingHorizontal: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
    borderRadius: 8,
  },
  shoppingItemRowChecked: {
    backgroundColor: '#F8FAFC',
  },
  checkboxSquare: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#94A3B8',
    marginRight: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxSquareChecked: {
    backgroundColor: '#10B981',
    borderColor: '#10B981',
  },
  checkboxTick: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '800',
  },
  shoppingItemText: {
    fontSize: 15,
    color: '#0F172A',
    fontWeight: '500',
  },
  shoppingItemTextChecked: {
    textDecorationLine: 'line-through',
    color: '#94A3B8',
  },
  expandToggleText: {
    fontSize: 16,
    color: '#64748B',
    fontWeight: '800',
  },
  breakdownRow: {
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
  },
  breakdownDay: {
    fontSize: 13,
    fontWeight: '700',
    color: '#1E293B',
  },
  breakdownIng: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 2,
  },
  segmentedControl: {
    flexDirection: 'row',
    backgroundColor: '#E2E8F0',
    borderRadius: 12,
    padding: 4,
    marginBottom: 12,
  },
  segmentBtn: {
    flex: 1,
    paddingVertical: 9,
    alignItems: 'center',
    borderRadius: 9,
  },
  segmentBtnActive: {
    backgroundColor: '#FFFFFF',
  },
  segmentBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#64748B',
  },
  segmentBtnTextActive: {
    color: '#0F172A',
  },
  freezerItemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
  },
  freezerItemName: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0F172A',
  },
  freezerItemMatches: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 2,
  },
  filterPillsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginVertical: 12,
  },
  filterPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 99,
    backgroundColor: '#F1F5F9',
  },
  filterPillActive: {
    backgroundColor: '#1E3A8A',
  },
  filterPillText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#475569',
  },
  filterPillTextActive: {
    color: '#FFFFFF',
  },
  emptyStateText: {
    textAlign: 'center',
    color: '#94A3B8',
    paddingVertical: 20,
    fontSize: 14,
  },
  couponCard: {
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    padding: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  couponTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  couponTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: '#0F172A',
    flex: 1,
  },
  couponUserBadge: {
    fontSize: 12,
    fontWeight: '700',
    color: '#1D4ED8',
    backgroundColor: '#DBEAFE',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  couponMetaText: {
    fontSize: 13,
    color: '#334155',
    marginTop: 4,
  },
  couponExpText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#B45309',
    marginTop: 4,
  },
  couponNotesText: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 4,
  },
  couponActionsRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 10,
  },
  searchInput: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: '#CBD5E1',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: '#0F172A',
    marginTop: 12,
  },
  dishCatalogCard: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
  },
  dishCatalogHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  dishCatalogName: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0F172A',
    flex: 1,
  },
  dishTypeBadge: {
    backgroundColor: '#EFF6FF',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  dishTypeBadgeText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#1D4ED8',
  },
  dishCatalogIng: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 3,
  },
  settingsBtnGroup: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginTop: 12,
  },
  secretsStatusGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 10,
    marginBottom: 14,
  },
  secretBadge: {
    backgroundColor: '#F1F5F9',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  secretBadgeText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#1E293B',
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#475569',
    marginTop: 10,
    marginBottom: 4,
  },
  textInput: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: '#CBD5E1',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 9,
    fontSize: 14,
    color: '#0F172A',
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.55)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#0F172A',
  },
  modalSubtitle: {
    fontSize: 14,
    color: '#64748B',
    marginTop: 4,
    marginBottom: 8,
  },
  userSelectorRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 4,
  },
  userOptionBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#CBD5E1',
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: 'center',
  },
  userOptionBtnActive: {
    backgroundColor: '#EFF6FF',
    borderColor: '#2563EB',
  },
  userOptionText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#475569',
  },
  userOptionTextActive: {
    color: '#1D4ED8',
  },
  modalButtonsRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 18,
  },
  modalCancelBtn: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: '#F1F5F9',
  },
  modalCancelText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#475569',
  },
  modalConfirmBtn: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: '#2563EB',
  },
  modalConfirmText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  bottomTabBar: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E2E8F0',
    paddingVertical: 8,
    paddingBottom: Platform.OS === 'ios' ? 18 : 8,
  },
  bottomTabItem: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bottomTabIcon: {
    fontSize: 18,
    opacity: 0.65,
  },
  bottomTabIconActive: {
    opacity: 1,
  },
  bottomTabLabel: {
    fontSize: 11,
    color: '#64748B',
    fontWeight: '600',
    marginTop: 2,
  },
  bottomTabLabelActive: {
    color: '#1E3A8A',
    fontWeight: '800',
  },
});
