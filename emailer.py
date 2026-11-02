import html as html_lib
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from holidays_manager import now_madrid
from menu_generator import get_current_menu_cycle_key

logger = logging.getLogger(__name__)

def generate_menu_html(menu_data, title="Menú Semanal para Álvaro y Ana"):
    """Genera un correo electrónico en formato HTML elegante con tabla de calendario."""
    html_rows = ""
    for entry in menu_data:
        day = html_lib.escape(str(entry.get("day", "")))
        date_str_day = html_lib.escape(str(entry.get("date_str", "")))
        day_label = f"{day} <span style='font-weight:normal; font-size:12px;'>({date_str_day})</span>" if date_str_day else day
        comida = entry.get("comida", {})
        cena = entry.get("cena", {})
        
        comida_name = html_lib.escape(str(comida.get("name", "No asignado")))
        comida_ing = html_lib.escape(str(comida.get("ingredients", "")))
        
        cena_name = html_lib.escape(str(cena.get("name", "No asignado")))
        cena_ing = html_lib.escape(str(cena.get("ingredients", "")))

        is_h = entry.get("is_holiday", False)
        h_name = html_lib.escape(str(entry.get("holiday_name") or ""))
        h_badge = f'<br><span style="color: #D97706; font-size: 11px; font-weight: normal;">🎉 {h_name}</span>' if is_h and h_name else ''

        html_rows += f"""
        <tr style="border-bottom: 1px solid #E2E8F0;">
            <td style="padding: 12px; font-weight: bold; color: #2B6CB0; background-color: {'#FEF3C7' if is_h else '#EDF2F7'}; text-align: center;">{day_label}{h_badge}</td>
            <td style="padding: 12px; vertical-align: top;">
                <div style="font-weight: bold; color: #2D3748; font-size: 15px;">☀️ {comida_name}</div>
                <div style="font-size: 12px; color: #718096; margin-top: 4px;"><em>Ingredientes:</em> {comida_ing}</div>
            </td>
            <td style="padding: 12px; vertical-align: top;">
                <div style="font-weight: bold; color: #2D3748; font-size: 15px;">🌙 {cena_name}</div>
                <div style="font-size: 12px; color: #718096; margin-top: 4px;"><em>Ingredientes:</em> {cena_ing}</div>
            </td>
        </tr>
        """

    now = now_madrid()
    _, cycle_desc = get_current_menu_cycle_key(now)
    safe_title = html_lib.escape(str(title))
    safe_cycle_desc = html_lib.escape(cycle_desc)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{safe_title}</title>
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #F7FAFC; padding: 20px; color: #1A202C;">
        <div style="max-width: 650px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; padding: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h2 style="color: #2B6CB0; margin-top: 0; text-align: center;">🍽️ {safe_title}</h2>
            <p style="text-align: center; color: #4A5568; font-size: 14px;">Planificación para la <strong>{safe_cycle_desc}</strong>.</p>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px;">
                <thead>
                    <tr style="background-color: #3182CE; color: #FFFFFF; text-align: left;">
                        <th style="padding: 12px; text-align: center; width: 18%;">Día</th>
                        <th style="padding: 12px; width: 41%;">☀️ Comida</th>
                        <th style="padding: 12px; width: 41%;">🌙 Cena</th>
                    </tr>
                </thead>
                <tbody>
                    {html_rows}
                </tbody>
            </table>
            
            <div style="margin-top: 25px; padding: 15px; background-color: #EBF8FF; border-left: 4px solid #3182CE; border-radius: 4px;">
                <p style="margin: 0; font-size: 13px; color: #2C5282;">
                    💡 <strong>Recordatorio:</strong> Tenéis <strong>2 vetos semanales cada uno</strong> en la app si queréis cambiar algún plato.
                </p>
            </div>
            <p style="text-align: center; font-size: 11px; color: #A0AEC0; margin-top: 30px;">
                Enviado automáticamente por la App Menú Álvaro & Ana.
            </p>
        </div>
    </body>
    </html>
    """
    return html

def generate_menu_text(menu_data):
    """Genera el texto plano para clientes de correo sin soporte HTML."""
    now = now_madrid()
    _, cycle_desc = get_current_menu_cycle_key(now)
    text = f"=== MENÚ SEMANAL PARA ÁLVARO Y ANA ===\nPeriodo: {cycle_desc}\n\n"
    for entry in menu_data:
        day = entry.get("day", "")
        comida = entry.get("comida", {}).get("name", "N/A")
        cena = entry.get("cena", {}).get("name", "N/A")
        is_h = entry.get("is_holiday", False)
        h_name = entry.get("holiday_name", "")
        day_tag = f"[{day} - 🎉 FESTIVO: {h_name}]" if is_h and h_name else f"[{day}]"
        text += f"{day_tag}\n  - Comida: {comida}\n  - Cena:   {cena}\n\n"
    text += "Recuerda: Tenéis 2 vetos semanales cada uno disponibles en la App.\n"
    return text

def send_weekly_menu_email(smtp_config: dict, menu_data: list, is_test: bool = False):
    """Envia el menú semanal vía SMTP simple (sin OAuth)."""
    host = smtp_config.get("smtp_host", "").strip()
    port = int(smtp_config.get("smtp_port", 587))
    user = smtp_config.get("smtp_user", "").strip()
    password = smtp_config.get("smtp_password", "").strip()
    use_tls = smtp_config.get("smtp_use_tls", True)
    recipients_str = smtp_config.get("recipients", "")
    
    recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]

    if not host or not user or not password or not recipients:
        msg = "Configuración SMTP incompleta. Por favor, especifica servidor, usuario, contraseña y destinatarios en Ajustes."
        logger.warning(msg)
        return False, msg

    now = now_madrid()
    _, cycle_desc = get_current_menu_cycle_key(now)
    subject = f"🧪 [Prueba] Menú Semanal Álvaro & Ana - {cycle_desc}" if is_test else f"🍽️ Menú Semanal Álvaro & Ana - {cycle_desc}"
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)

    text_part = MIMEText(generate_menu_text(menu_data), "plain", "utf-8")
    html_part = MIMEText(generate_menu_html(menu_data, title=subject), "html", "utf-8")

    msg.attach(text_part)
    msg.attach(html_part)

    try:
        if port == 465:
            # Conexión SSL directa
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            # Conexión estándar / STARTTLS (puerto 587 o 25)
            server = smtplib.SMTP(host, port, timeout=15)
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()

        server.login(user, password)
        server.sendmail(user, recipients, msg.as_string())
        server.quit()

        success_msg = f"Email enviado con éxito a: {', '.join(recipients)}"
        logger.info(success_msg)
        return True, success_msg

    except Exception as e:
        err_msg = f"Error al enviar email SMTP: {str(e)}"
        logger.error(err_msg)
        return False, err_msg
