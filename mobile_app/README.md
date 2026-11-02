# 📱 Menú Semanal AyA — App Móvil 100% Nativa (iOS + Android)

Aplicación móvil 100% nativa construida con **React Native + Expo (TypeScript)** y conectada directamente al servidor en producción:
`https://alvaro-menu-app.onrender.com`

## ✨ Características Nativas

- **Caché Offline Instantánea (`AsyncStorage`):** El menú semanal, la lista de la compra, el congelador y los platos se abren al instante incluso sin cobertura o mientras el servidor despierta.
- **Gestos Nativos:** Pull-to-refresh para sincronizar, hojas modales inferiores (`Bottom Sheets`) para aplicar vetos, crear vales o editar recetas, e interruptores (`Switch`) nativos de iOS/Android.
- **Integración con el Sistema Operativo:**
  - **Compartir Lista de la Compra** directamente por WhatsApp / iMessage con `Share.share()`.
  - **Añadir platos a Google Calendar / Apple Calendar** y **Suscripción al calendario `.ics`** con `Linking.openURL()`.

---

## 🚀 Cómo abrirla en tu iPhone o Android en 30 segundos (Expo Go)

1. Instala la app gratuita **Expo Go** desde la **App Store (iPhone)** o **Google Play (Android)**.
2. En tu ordenador, dentro de la carpeta `mobile_app`, ejecuta:
   ```bash
   npx expo start --tunnel
   ```
3. Escanea el código QR que aparece en la terminal con la cámara de tu iPhone o con la app Expo Go en Android.

---

## 📦 Cómo descargar el instalador `.apk` nativo para Android (Sin cables)

Cada vez que se hace `git push` a `main`, el flujo de **GitHub Actions** ([`.github/workflows/build-mobile.yml`](../.github/workflows/build-mobile.yml)) compila automáticamente el archivo `.apk` de Android en la nube:

1. Entra en tu repositorio de GitHub: `https://github.com/alvmm/alvaro_menu_app/actions`
2. Abre la ejecución más reciente de **"Build Native Android APK (Menú AyA)"**.
3. En la sección **Artifacts**, descarga **`Menu-AyA-Android-APK`** e instálalo en tu móvil Android.
