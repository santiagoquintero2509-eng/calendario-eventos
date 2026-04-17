from dotenv import load_dotenv
import os
import dropbox
import re
from github import Github

# 🔹 Cargar variables
load_dotenv()

DROPBOX_TOKEN = os.getenv("DROPBOX_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

if not DROPBOX_TOKEN:
    print("❌ Falta DROPBOX_TOKEN")
    exit()

dbx = dropbox.Dropbox(DROPBOX_TOKEN)


# 🧠 PARSER
def interpretar_nombre(nombre):
    try:
        year = re.search(r"\d{4}", nombre).group()
        month = re.search(r"- (\d{2})", nombre).group(1)

        montaje = re.search(r"\((\d{1,2})(?:-(\d{1,2}))?\)", nombre)
        if not montaje:
            return None

        m_inicio = montaje.group(1)
        m_fin = montaje.group(2) if montaje.group(2) else m_inicio

        despues = nombre.split(")")[-1].strip()

        rango = re.match(r"(\d{1,2})\s*-\s*(\d{1,2})", despues)
        simple = re.match(r"(\d{1,2})", despues)

        if rango:
            e_inicio = rango.group(1)
            e_fin = rango.group(2)
            texto = despues.replace(f"{e_inicio} - {e_fin}", "")
        elif simple:
            e_inicio = simple.group(1)
            e_fin = e_inicio
            texto = despues.replace(f"{e_inicio}", "")
        else:
            return None

        texto = texto.strip(" -")
        partes = texto.split(" - ")

        if len(partes) >= 2:
            cliente = partes[0]
            evento = partes[1]
        else:
            cliente = "Cliente"
            evento = "Evento"

        lugar = partes[-1]

        return {
            "evento": evento,
            "cliente": cliente,
            "lugar": lugar,
            "montaje_inicio": f"{year}-{month}-{m_inicio.zfill(2)}",
            "montaje_fin": f"{year}-{month}-{m_fin.zfill(2)}",
            "desmontaje": f"{year}-{month}-{e_fin.zfill(2)}"
        }

    except Exception as e:
        print("❌ Error interpretando:", nombre)
        print(e)
        return None


# 📅 CREAR ICS
def crear_ics(eventos):
    contenido = "BEGIN:VCALENDAR\nVERSION:2.0\n"

    for e in eventos:
        contenido += f"""BEGIN:VEVENT
SUMMARY:{e['titulo']}
DTSTART:{e['inicio']}
DTEND:{e['fin']}
LOCATION:{e['lugar']}
END:VEVENT
"""

    contenido += "END:VCALENDAR"

    with open("eventos.ics", "w", encoding="utf-8") as f:
        f.write(contenido)

    print("📅 Archivo eventos.ics creado")


# ☁️ SUBIR A GITHUB
def subir_a_github():
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("❌ Falta configuración de GitHub")
        return

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_user().get_repo(GITHUB_REPO)

        with open("eventos.ics", "r", encoding="utf-8") as f:
            contenido = f.read()

        try:
            archivo = repo.get_contents("eventos.ics")

            repo.update_file(
                path="eventos.ics",
                message="🔄 Actualización automática calendario",
                content=contenido,
                sha=archivo.sha
            )

            print("☁️ Archivo actualizado en GitHub")

        except:
            repo.create_file(
                path="eventos.ics",
                message="📅 Creación inicial calendario",
                content=contenido
            )

            print("☁️ Archivo subido a GitHub")

    except Exception as e:
        print("❌ Error GitHub:", e)


# 📂 PROCESO PRINCIPAL
def procesar():
    eventos_lista = []

    try:
        result = dbx.files_list_folder("")
        print("\n📂 Procesando carpetas:\n")

        for entry in result.entries:
            if isinstance(entry, dropbox.files.FolderMetadata):
                nombre = entry.name
                print("📁", nombre)

                data = interpretar_nombre(nombre)

                if data:
                    print("✅ OK:", data)

                    eventos_lista.append({
                        "titulo": f"MONTAJE - {data['evento']}",
                        "inicio": data["montaje_inicio"].replace("-", "") + "T080000",
                        "fin": data["montaje_fin"].replace("-", "") + "T200000",
                        "lugar": data["lugar"]
                    })

                    eventos_lista.append({
                        "titulo": f"DESMONTAJE - {data['evento']}",
                        "inicio": data["desmontaje"].replace("-", "") + "T080000",
                        "fin": data["desmontaje"].replace("-", "") + "T200000",
                        "lugar": data["lugar"]
                    })

                else:
                    print("⚠️ No se pudo interpretar")

                print("-" * 50)

        print(f"\n🔢 Total eventos: {len(eventos_lista)}")

        crear_ics(eventos_lista)
        subir_a_github()

    except Exception as e:
        print("❌ Error Dropbox:", e)


# 🚀 EJECUTAR
procesar()