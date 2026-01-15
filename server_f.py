import socket
import threading
from datetime import datetime

import xml.etree.ElementTree as ET
import os

LOG_FILE = "log.xml"
log_lock = threading.Lock()

def log_message(sender, text):
    with log_lock:
        if not os.path.exists(LOG_FILE):
            root = ET.Element("log")
            tree = ET.ElementTree(root)
        else:
            tree = ET.parse(LOG_FILE)
            root = tree.getroot()

        msg = ET.SubElement(root, "message")
        ET.SubElement(msg, "sender").text = sender
        ET.SubElement(msg, "timestamp").text = datetime.now().isoformat(timespec="milliseconds")
        ET.SubElement(msg, "text").text = text

        ET.indent(tree, space="  ")
        tree.write(LOG_FILE, encoding="utf-8", xml_declaration=True)

        
def gestisci_messaggi(client_socket,client_address):
    print(f"Connessione da {client_address}")
    
    while True: #ciclo che rimane in ascolto di messaggi finche non riceve exit
        try:
            data = client_socket.recv(1024).decode() #riceve il messaggio

            log_message("client", data)
            
            if data == "TIME":
                ora = datetime.now().strftime("%H:%M") #salva l'orario attuale
                risposta = f"Sono le {ora}" 
                client_socket.send(f"Sono le {ora}".encode()) #invia un messaggio con l'orario attuale
            elif data == "NAME":
                hostname = socket.gethostname() #salva il nome 
                risposta = f"Hostname: {hostname}"
                client_socket.send(f"Hostname: {hostname}".encode()) #invia un messaggio con il nome 

            elif data == "EXIT" : #se il messaggio è exit o non c'è ferma la connessione
                risposta = f"-1"
                client_socket.send("-1".encode())
                print(f"{client_address} ha chiuso la connessione") 
                break
            else:
                risposta = f"Ciao {client_address}, ho ricevuto il tuo messaggio"
                client_socket.send(f"Ciao {client_address}, ho ricevuto il tuo messaggio".encode()) #invia messaggio a client inserendo il messaggio che ha ricevuto
            
            log_message("server", risposta)

            print(f"{client_address} dice: {data}") #stampa il messaggio ricevuto sul server
            print()
        except ConnectionResetError:
            break
    client_socket.close()
    


server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # 1. Creazione del socket TCP (IPv4 + TCP)

server_socket.bind(("0.0.0.0", 12345)) # 2. Bind su IP e porta (0.0.0.0 = accetta da tutte le interfacce)

# 3. Mettere il server in ascolto
server_socket.listen(5)
print("Server in ascolto sulla porta 12345...")

try:
    while True:
        client_socket, client_address = server_socket.accept()
        thread = threading.Thread(target=gestisci_messaggi, args=(client_socket,client_address))
        thread.start()
except KeyboardInterrupt:
    print("Chiusura server")
    server_socket.close()

