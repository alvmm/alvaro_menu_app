# 🍽️ Menú Semanal • Álvaro & Ana (v2.0 FastAPI + PWA)

Aplicación web progresiva (**PWA**) y API REST desarrollada con **FastAPI** + **Single Page Application (SPA)** moderna, diseñada para Álvaro y Ana. Permite planificar el menú semanal (almuerzos y cenas), aplicar vetos individuales con alternativas automáticas, controlar el stock del congelador sincronizado con Google Sheets, llevar la lista de la compra interactiva en el supermercado, gestionar cupones para comer fuera y enviar notificaciones automáticas por correo electrónico.

---

## 🏗️ Arquitectura Profesional del Proyecto

| Archivo / Módulo | Descripción y Responsabilidad |
| :--- | :--- |
| **`server.py`** | **Servidor principal FastAPI (API REST + PWA)**. Sirve la aplicación web reactiva sin recargas de página, expone endpoints JSON tipados (`/api/*`), documentación interactiva (`/docs`) y el feed `.ics` en vivo (`/menu_semanal_AyA.ics`). |
| **`static/index.html`** | Interfaz SPA/PWA moderna y responsive (barra lateral en escritorio y navegación inferior estilo app nativa en iOS/Android). |
| **`static/styles.css`** | Sistema de diseño moderno con tarjetas, badges semánticos, modales y notificaciones *toast*. |
| **`static/app.js`** | Controlador reactivo cliente con actualizaciones instantáneas vía `fetch()` sin recargar la página. |
| **`static/manifest.json` & `sw.js`** | Manifiesto Web y Service Worker para instalar la aplicación en la pantalla de inicio de iPhone y Android a pantalla completa. |
| **`menu_generator.py`** | Algoritmo que genera el menú semanal (7 días x Comida/Cena) filtrando por tipo (`comida`, `cena`, `ambas`), congelador y festivos. |
| **`veto_manager.py`** | Lógica del sistema de vetos: límite de 2 vetos por semana por persona (Álvaro / Ana) y ventana de sábado a domingo 16:00. |
| **`coupon_manager.py`** | Gestión de invitaciones y cupones para pedir o comer fuera con alertas de caducidad. |
| **`csv_loader.py`** | Sincronización de platos e inventario del congelador desde Google Sheets (CSV) con enriquecimiento automático de ingredientes. |
| **`calendar_loader.py` & `calendar_exporter.py`** | Lectura de eventos (incluyendo eventos multi-día) desde Google Calendar (`.ics`) y exportación del menú semanal a iCal / Google Calendar. |
| **`holidays_manager.py`** | Cálculo de festivos nacionales/Comunidad de Madrid (incluyendo Semana Santa) y zona horaria `Europe/Madrid`. |
| **`emailer.py`** | Formateador de correo HTML/Texto plano escapado y cliente SMTP para notificaciones semanales. |
| **`storage_manager.py`** | Persistencia de datos en JSON (`menu_app_data.json`) con separación segura de secretos en memoria. |
| **`Dockerfile` & `render.yaml`** | Configuración lista para despliegue gratuito en la nube (Render, Railway, Fly.io, Koyeb). |
| **`test_suite.py`** | Batería de 20 pruebas unitarias y de integración. |

---

## 🚀 Cómo Ejecutar la Nueva Versión (FastAPI + PWA)

```bash
# 1. Instalar dependencias
py -m pip install -r requirements.txt

# 2. Iniciar el servidor FastAPI
py server.py
```

* **Aplicación Web / PWA**: Abre `http://localhost:8000` en tu navegador.
* **Documentación interactiva de la API (Swagger UI)**: Abre `http://localhost:8000/docs`.
* **Instalar como App en iPhone / Android**:
  * **iPhone (Safari)**: Abre el enlace de la app, pulsa el botón **Compartir** y selecciona **"Añadir a pantalla de inicio"**.
  * **Android (Chrome)**: Abre el enlace y pulsa **"Instalar aplicación"** en el menú del navegador.

---

## ☁️ Cómo Desplegar Gratis en la Nube

La aplicación empaqueta backend y frontend en un único servicio ligero (`server.py`), por lo que puedes alojarla gratis en plataformas como **Render** o **Railway**:

1. Sube el repositorio a GitHub.
2. En **Render.com** (plan Free):
   * Crea un nuevo **Web Service** conectado a tu repositorio (detectará automáticamente `render.yaml` o `Dockerfile`).
   * Comando de inicio: `uvicorn server:app --host 0.0.0.0 --port $PORT`
3. Añade tus variables de entorno privadas en el panel del servidor (sin subirlas a Git):
   * `SHEET_URL`: Enlace a vuestro Google Sheets
   * `CALENDAR_ICS_URL`: Enlace privado `.ics` de vuestro Google Calendar
   * `SMTP_USER`: Tu correo de Gmail
   * `SMTP_PASSWORD`: Contraseña de aplicación de 16 caracteres de Gmail
   * `SMTP_RECIPIENTS`: Correos destinatarios separados por comas

---

## 🧪 Ejecutar Pruebas Unitarias

```bash
py -m unittest test_suite.py -v
```
