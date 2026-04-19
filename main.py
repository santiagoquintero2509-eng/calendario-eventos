import os
import re
import json
from datetime import datetime, UTC

from dotenv import load_dotenv
import dropbox

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ---------------- CONFIG ----------------
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'primary'

load_dotenv()

DROPBOX_TOKEN = os.getenv("DROPBOX_TOKEN")

if not DROPBOX_TOKEN:
    print("❌ Falta DROPBOX_TOKEN")
    exit()

dbx = dropbox.Dropbox(DROPBOX_TOKEN)

# ---------------- GOOGLE AUTH (GITHUB READY) ----------------
def get_calendar_service():
    if "GOOGLE_TOKEN_JSON" not in os.environ:
        print("❌ Falta GOOGLE_TOKEN_JSON")
        exit()

    token_data = json.loads(os.environ["GOOGLE_TOKEN_JSON"])
    creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    service = build("calendar", "v3", credentials=creds)
    return service


# ---------------- PARSER ----------------
def interpretar_nombre(nombre):
    try:
        year = re.search(r"\d{4}", nombre).group()
        month = re.search(r"- (\d{2})", nombre).group(1)

        montaje = re.search(r"\((\d{1,2})(?:-(\d{1,2}))?\)", nombre)
        if not montaje:
            return None

        m_inicio = montaje.group(1)
        m_fin = montaje.group(2) if montaje.group(2) else m_inicio

        partes = nombre.split(" - ")

        evento = partes[-2]
        lugar = partes[-1]
        cliente = partes[-3] if len(partes) >= 3 else "Sin cliente"

        return {
            "evento": evento.strip(),
            "cliente": cliente.strip(),
            "lugar": lugar.strip(),
            "montaje_inicio": f"{year}-{month}-{int(m_inicio):02d}",
            "montaje_fin": f"{year}-{month}-{int(m_fin):02d}",
            "desmontaje": f"{year}-{month}-{int(m_fin)+1:02d}"
        }

    except Exception as e:
        print(f"❌ Error interpretando: {nombre}")
        return None


# ---------------- GOOGLE UTILS ----------------
def buscar_evento_existente(service, summary, start_date):
    eventos = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=f"{start_date}T00:00:00Z",
        timeMax=f"{start_date}T23:59:59Z",
        q=summary
    ).execute()

    items = eventos.get("items", [])
    return items[0] if items else None


def crear_o_actualizar_evento(service, summary, start, end, location):
    existente = buscar_evento_existente(service, summary, start[:10])

    evento_body = {
        "summary": summary,
        "location": location,
        "start": {"dateTime": start, "timeZone": "America/Bogota"},
        "end": {"dateTime": end, "timeZone": "America/Bogota"},
    }

    if existente:
        print(f"🔄 Actualizando: {summary}")
        service.events().update(
            calendarId=CALENDAR_ID,
            eventId=existente["id"],
            body=evento_body
        ).execute()
    else:
        print(f"🆕 Creando: {summary}")
        service.events().insert(
            calendarId=CALENDAR_ID,
            body=evento_body
        ).execute()


def limpiar_eventos_viejos(service):
    hoy = datetime.now(UTC).isoformat()

    eventos = service.events().list(
        calendarId=CALENDAR_ID,
        timeMax=hoy
    ).execute()

    for evento in eventos.get("items", []):
        summary = evento.get("summary", "")
        if "MONTAJE" in summary or "DESMONTAJE" in summary:
            print(f"🗑 Eliminando viejo: {summary}")
            service.events().delete(
                calendarId=CALENDAR_ID,
                eventId=evento["id"]
            ).execute()


def limpiar_eventos_huerfanos(service, eventos_validos):
    print("\n🔍 Verificando eventos huérfanos...")

    eventos_google = service.events().list(
        calendarId=CALENDAR_ID
    ).execute().get("items", [])

    for evento in eventos_google:
        summary = evento.get("summary", "")

        if "MONTAJE" in summary or "DESMONTAJE" in summary:
            if summary not in eventos_validos:
                print(f"🗑 Eliminando huérfano: {summary}")
                service.events().delete(
                    calendarId=CALENDAR_ID,
                    eventId=evento["id"]
                ).execute()


# ---------------- MAIN ----------------
def main():
    service = get_calendar_service()

    print("📁 Procesando carpetas...\n")

    resultados = []
    eventos_validos = []

    for entry in dbx.files_list_folder("").entries:
        if isinstance(entry, dropbox.files.FolderMetadata):
            data = interpretar_nombre(entry.name)
            if data:
                resultados.append(data)
                print("✔ OK:", data)

    print(f"\n📊 Total eventos: {len(resultados)}\n")

    # 🧹 limpiar eventos viejos
    limpiar_eventos_viejos(service)

    for evento in resultados:

        nombre_montaje = f"MONTAJE - {evento['evento']} - {evento['lugar']}"
        nombre_desmontaje = f"DESMONTAJE - {evento['evento']} - {evento['lugar']}"

        eventos_validos.append(nombre_montaje)
        eventos_validos.append(nombre_desmontaje)

        crear_o_actualizar_evento(
            service,
            nombre_montaje,
            evento['montaje_inicio'] + "T08:00:00",
            evento['montaje_fin'] + "T20:00:00",
            evento['lugar']
        )

        crear_o_actualizar_evento(
            service,
            nombre_desmontaje,
            evento['desmontaje'] + "T08:00:00",
            evento['desmontaje'] + "T20:00:00",
            evento['lugar']
        )

    # 🧠 eliminar huérfanos
    limpiar_eventos_huerfanos(service, eventos_validos)

    print("\n🚀 Calendario sincronizado correctamente")


if __name__ == "__main__":
    main()