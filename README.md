# 🍽️ App Móvil Menú Semanal (Álvaro & Pareja)

Aplicación móvil privada desarrollada en Python (Kivy) para Android, diseñada exclusivamente para Álvaro y su pareja. Permite planificar el menú semanal (almuerzos y cenas), aplicar vetos con alternativas automáticas, gestionar invitaciones/cupones para comer fuera y recibir notificaciones automáticas por correo electrónico cada sábado.

---

## 🏗️ Arquitectura Modular del Proyecto

La aplicación ha sido desarrollada siguiendo una arquitectura limpia y modular en Python:

| Archivo / Módulo | Descripción y Responsabilidad |
| :--- | :--- |
| **`app.py`** | **Nueva versión Web Streamlit**. Compatible con iPhone, Android y PC, con interfaz moderna, lista de la compra interactiva y sincronización. |
| **`main.py`** | Punto de entrada alternativo para versión móvil en Kivy (Android). |
| **`alvaromenu.kv`** | Definición gráfica de la interfaz de usuario en Kivy. |
| **`csv_loader.py`** | Módulo de descarga y parseo de la Google Sheet en formato CSV usando `urllib.request`. |
| **`menu_generator.py`** | Algoritmo que genera el menú semanal (7 días x Comida/Cena) filtrando por tipo (`comida`, `cena`, `ambas`). |
| **`veto_manager.py`** | Lógica del sistema de vetos: límite estricto de 2 vetos por semana por persona (Álvaro / Pareja) con sustitución individual. |
| **`coupon_manager.py`** | Gestión de invitaciones y cupones para pedir comida fuera con alertas de caducidad. |
| **`emailer.py`** | Formateador de correo HTML/Texto plano y cliente SMTP simple para notificaciones semanales. |
| **`storage_manager.py`** | Persistencia de datos en archivo JSON local (`menu_app_data.json`). |
| **`buildozer.spec`** | Configuración de compilación para generar el paquete APK con Buildozer para Android. |
| **`test_suite.py`** | Batería de pruebas unitarias que verifican la corrección del algoritmo, vetos, cupones y CSV. |

---

## 🌐 Cómo Ejecutar la Versión Web (Streamlit)

La versión Streamlit funciona de forma nativa en cualquier navegador (iPhone Safari, Android Chrome, PC o Mac) sin necesidad de compilar APK ni instalar nada en los teléfonos:

```bash
# Ejecutar en tu ordenador
streamlit run app.py
```
- **Desde tu PC**: Abre `http://localhost:8501`.
- **Desde tu iPhone o móvil Android**: Conecta el móvil a la misma red Wi-Fi y abre la dirección IP que muestra la consola (ej: `http://192.168.1.52:8501`).
- **En la nube (gratis)**: Puedes conectarlo a tu repositorio de GitHub y publicarlo gratis en [share.streamlit.io](https://share.streamlit.io/) para tener un enlace HTTPS privado accesible desde cualquier lugar con 4G/5G.


---

## 🚀 Guía de Configuración

### 1. Google Sheets (CSV)
1. Crea una hoja de cálculo en Google Sheets con las columnas:
   - `ID` (número único)
   - `Nombre` (nombre del plato)
   - `Tipo` (`comida`, `cena` o `ambas`)
   - `Ingredientes` (lista de ingredientes)
2. En Google Sheets, ve a **Archivo > Compartir > Publicar en la web**.
3. Selecciona la hoja deseada y en formato elige **Valores separados por comas (.csv)**.
4. Copia el enlace resultante o el ID de la hoja e introdúcelo en la pantalla de **Configuración** de la App.

### 2. Servidor SMTP (Email)
- **Para Gmail**:
  1. Activa la *Verificación en dos pasos* en la cuenta de Google.
  2. Genera una **Contraseña de Aplicación** desde [Contraseñas de aplicación de Google](https://myaccount.google.com/apppasswords).
  3. En la app: Servidor = `smtp.gmail.com`, Puerto = `587`, Usuario = `tu_email@gmail.com`, Contraseña = `<tu_contraseña_de_aplicacion>`, Destinatarios = `alvaro@email.com, pareja@email.com`.

---

## 📦 Compilación del APK para Android con Buildozer

Puedes compilar la APK de dos formas principales:

### Opción A: Compilar en Ubuntu / WSL2 (Recomendado)
```bash
# 1. Instalar dependencias del sistema en Ubuntu/Debian
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libhidden-dev cmake

# 2. Instalar Buildozer y Cython
pip3 install --user buildozer cython

# 3. Situarse en la carpeta de la app y compilar en modo Debug
cd alvaro_menu_app
buildozer -v android debug
```
El archivo `.apk` se generará dentro de la carpeta `bin/`.

### Opción B: Compilar gratis en Google Colab (Sin instalar nada localmente)
1. Abre [Google Colab](https://colab.research.google.com/).
2. Sube la carpeta `alvaro_menu_app` o clona el repositorio.
3. Ejecuta en una celda:
```python
!pip install buildozer cython
!sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config zlib1g-dev cmake
!cd alvaro_menu_app && buildozer -v android debug
```
4. Descarga la APK compilada directamente a tu ordenador o móvil.

---

## 🔒 Recomendaciones para Mantener la App Privada

1. **Instalación Directa vía APK (Sideloading)**:
   - Transfiere la APK generada (`alvaromenu-1.0.0-arm64-v8a-debug.apk`) a los dos teléfonos móviles por **Google Drive, Telegram o WhatsApp**.
   - Al abrirla en Android, selecciona "Instalar aplicaciones desconocidas" o permitir la instalación desde el navegador/gestor de archivos.
2. **Sin Publicar en Play Store**:
   - Al no subirla a Google Play Store, la app permanece completamente privada entre Álvaro y su pareja.
3. **Sin Servidores Externos de Pago**:
   - Toda la información del menú y cupones se almacena localmente en el propio dispositivo Android (`menu_app_data.json`).
   - El único tráfico externo es la lectura del CSV público de Google Sheets y el envío de notificaciones SMTP estándar.
