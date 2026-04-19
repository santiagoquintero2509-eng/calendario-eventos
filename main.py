from dotenv import load_dotenv
import os
import re
import dropbox
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# 🔐 CONFIG
load_dotenv()
DROPBOX_TOKEN = os.getenv("DROPBOX_TOKEN")

# 🔗 GOOGLE AUTH
creds = Credentials.from_authorized_user_file("token.json")
service = build('calendar', 'v3', credentials=creds)

# 📦 DROPBOX
dbx = dropbox.Dropbox(DROPBOX_TOKEN)

# 🧠 PARSER
def interpretar_nombre(nombre):
    try:
        year = re.search(r"\d{4}", nombre).group()
        dias = re.search(r"\((.*?)\)", nombre).group(1)

        partes = nombre.split("-")
        evento = partes[-3].strip()
        cliente = partes[-4].strip()
        lugar = partes[-1].strip()

        numeros = re.findall(r"\d{1,2}", dias)

        inicio = f"{year}-04-{numeros[0].zfill(2)}"
        fin = f"{year}-04-{numeros[-1].zfill(2)}"

        return {
            "evento": evento,
            "cliente": cliente,
            "lugar": lugar,
            "montaje_inicio": inicio,
            "montaje_fin": inicio,
            "desmontaje": fin
        }
    except:
        return None

# 🔍 BUSCAR EVENTO
def buscar_evento(service, summary, start):
    eventos = service.events().list(
        calendarId='primary',
        timeMin=start + "T00:00:00Z",
        maxResults=50,
        singleEvents=True
    ).execute()

    for e in eventos.get('items', []):
        if e['summary'] == summary:
            return e
    return None

# ➕ / 🔄 CREAR O ACTUALIZAR
def crear_o_actualizar_evento(service, summary, start, end, location):
    existente = buscar_evento(service, summary, start)

    evento = {
        'summary': summary,
        'location': location,
        'start': {'dateTime': start + "T08:00:00", 'timeZone': 'America/Bogota'},
        'end': {'dateTime': end + "T20:00:00", 'timeZone': 'America/Bogota'},
    }

    if existente:
        service.events().update(
            calendarId='primary',
            eventId=existente['id'],
            body=evento
        ).execute()
        print(f"🔄 Actualizado: {summary}")
    else:
        service.events().insert(
            calendarId='primary',
            body=evento
        ).execute()
        print(f"🆕 Creado: {summary}")

# 🗑 ELIMINAR EVENTOS VIEJOS
def limpiar_eventos(service, eventos_actuales):
    now = datetime.now(timezone.utc).isoformat()

    eventos = service.events().list(
        calendarId='primary',
        timeMin="2020-01-01T00:00:00Z",
        maxResults=250,
        singleEvents=True
    ).execute()

    for e in eventos.get('items', []):
        if "MONTAJE" in e['summary'] or "DESMONTAJE" in e['summary']:
            if e['summary'] not in eventos_actuales:
                service.events().delete(
                    calendarId='primary',
                    eventId=e['id']
                ).execute()
                print(f"🗑 Eliminado: {e['summary']}")

# 🚀 MAIN
def main():
    print("📁 Procesando carpetas...")
    eventos_actuales = []

    for entry in dbx.files_list_folder("").entries:
        data = interpretar_nombre(entry.name)
        if not data:
            continue

        # MONTAJE
        nombre_montaje = f"MONTAJE - {data['evento']} - {data['lugar']}"
        crear_o_actualizar_evento(
            service,
            nombre_montaje,
            data['montaje_inicio'],
            data['montaje_fin'],
            data['lugar']
        )
        eventos_actuales.append(nombre_montaje)

        # DESMONTAJE
        nombre_desmontaje = f"DESMONTAJE - {data['evento']} - {data['lugar']}"
        crear_o_actualizar_evento(
            service,
            nombre_desmontaje,
            data['desmontaje'],
            data['desmontaje'],
            data['lugar']
        )
        eventos_actuales.append(nombre_desmontaje)

    limpiar_eventos(service, eventos_actuales)

    print("🚀 Calendario sincronizado")

if __name__ == "__main__":
    main()
