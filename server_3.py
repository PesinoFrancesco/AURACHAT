import socket
import threading
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
import signal
import sys
import platform

# --- COLORI ANSI BASE ---
class Colori:
    RESET = '\033[0m'
    ROSSO = '\033[31m'
    VERDE = '\033[32m'
    GIALLO = '\033[33m'
    BLU = '\033[34m'
    MAGENTA = '\033[35m'
    CIANO = '\033[36m'
    GRIGIO = '\033[90m'
    BOLD = '\033[1m'

# Statistiche globali del server
statistiche = {
    'totale_connessioni': 0,
    'connessioni_attive': 0,
    'comandi_time': 0,
    'comandi_name': 0,
    'comandi_exit': 0,
    'comandi_info': 0,
    'comandi_invalidi': 0
}
stats_lock = threading.Lock()

# Lock per scrittura XML thread-safe
xml_lock = threading.Lock()

# Mappa per assegnare un nome identificativo ai client
client_names = {}
client_counter = 1
client_names_lock = threading.Lock()

# Database utenti simulato (aggiungi utenti come preferisci)
db_utenti = {
    'user1': {'nome': 'Mario Rossi', 'status': 'online'},
    'user2': {'nome': 'Luigi Verdi', 'status': 'offline'},
    'user3': {'nome': 'Anna Bianchi', 'status': 'online'},
    'user4': {'nome': 'Paolo Neri', 'status': 'online'},
    'user5': {'nome': 'Giulia Gialli', 'status': 'offline'}
}
db_lock = threading.Lock()

# Flag per shutdown controllato
server_running = True

def get_client_name(client_address):
    """Restituisce o assegna un nome identificativo per il client dato l'indirizzo (ip, porta)"""
    global client_counter
    key = f"{client_address[0]}:{client_address[1]}"
    with client_names_lock:
        if key not in client_names:
            client_names[key] = f"client{client_counter}"
            client_counter += 1
        return client_names[key]

def setup_xml_log():
    """Configura il file XML di log"""
    Path("logs").mkdir(exist_ok=True)
    log_filename = f"logs/server_{datetime.now().strftime('%Y-%m-%d')}.xml"
    
    # Se il file non esiste, crea la struttura base
    if not os.path.exists(log_filename):
        root = ET.Element("log")
        root.set("server_name", socket.gethostname())
        root.set("date", datetime.now().strftime('%Y-%m-%d'))
        
        session = ET.SubElement(root, "session")
        session.set("start_time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(log_filename, encoding='utf-8', xml_declaration=True)
    
    return log_filename

def log_to_xml(log_filename, level, log_type, message, **extra_data):
    """
    Scrive un'entry nel file XML di log in modo thread-safe
    
    Args:
        log_filename: percorso file XML
        level: INFO, WARNING, ERROR
        log_type: CONNECTION, REQUEST, RESPONSE, ERROR, etc.
        message: messaggio principale
        **extra_data: dati aggiuntivi da includere nell'entry
    """
    with xml_lock:
        try:
            # Leggi il file XML esistente
            tree = ET.parse(log_filename)
            root = tree.getroot()
            
            # Trova l'ultimo session element
            sessions = root.findall("session")
            if sessions:
                current_session = sessions[-1]
            else:
                current_session = ET.SubElement(root, "session")
                current_session.set("start_time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # Crea nuova entry
            entry = ET.SubElement(current_session, "entry")
            entry.set("timestamp", datetime.now().strftime('%H:%M:%S'))
            entry.set("level", level)
            entry.set("type", log_type)
            
            # Aggiungi messaggio
            msg_elem = ET.SubElement(entry, "message")
            msg_elem.text = message
            
            # Aggiungi dati extra
            for key, value in extra_data.items():
                elem = ET.SubElement(entry, key)
                elem.text = str(value)
            
            # Salva con formattazione
            ET.indent(tree, space="  ")
            tree.write(log_filename, encoding='utf-8', xml_declaration=True)
            
            # --- COLORI PER LA CONSOLE ---
            if level == "INFO":
                level_colored = Colori.VERDE + level + Colori.RESET
            elif level == "WARNING":
                level_colored = Colori.GIALLO + level + Colori.RESET
            elif level == "ERROR":
                level_colored = Colori.ROSSO + level + Colori.RESET
            else:
                level_colored = level
            # Colora il nome client se presente
            client_name = extra_data.get('client_name', None)
            if client_name:
                client_name_colored = Colori.BLU + client_name + Colori.RESET
                # Sostituisci nel messaggio se presente
                msg_colored = message.replace(str(client_name), client_name_colored)
            else:
                msg_colored = message
            # Stampa su console
            if log_type in ["CONNECTION", "ERROR", "DISCONNECTION"]:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level_colored}] {msg_colored}")
        except Exception as e:
            print(f"Errore scrittura XML log: {e}")

def aggiorna_stats(campo, incremento=1):
    """Aggiorna statistiche in modo thread-safe"""
    with stats_lock:
        statistiche[campo] += incremento

def get_info_server():
    """Restituisce informazioni di rete del server"""
    hostname = socket.gethostname()
    try:
        ip_address = socket.gethostbyname(hostname)
    except:
        ip_address = "N/A"
    
    sistema = platform.system()
    versione = platform.version()
    
    info = f"""
╔═══════════════════════════════════════════════════════════╗
║           INFORMAZIONI DI RETE DEL SERVER                 ║
╠═══════════════════════════════════════════════════════════╣
║  Hostname:        {hostname:<40}║
║  IP Address:      {ip_address:<40}║
║  Porta:           12345{' '*35}║
║  Sistema:         {sistema:<40}║
║  Versione:        {versione[:40]:<40}║
╚═══════════════════════════════════════════════════════════╝
"""
    return info

def gestisci_comando_info(comando_completo, client_address, client_name):
    """
    Gestisce il comando INFO e le sue varianti
    Ritorna la risposta da inviare al client
    """
    parti = comando_completo.split()
    
    # Se è solo "INFO" senza parametri, mostra help
    if len(parti) == 1:
        risposta = """
╔═══════════════════════════════════════════════════════════╗
║                  COMANDO INFO - HELP                      ║
╠═══════════════════════════════════════════════════════════╣
║  Uso: INFO [type]                                         ║
║                                                           ║
║  Type disponibili:                                        ║
║  1 → Numero di client attualmente collegati              ║
║  2 → Numero di utenti presenti nel DB                    ║
║  3 → Informazioni di rete del server                     ║
║  4 → Informazioni di rete del client (solo client)       ║
║  5 → Lista utenti disponibili per chat                   ║
║                                                           ║
║  Esempio: INFO 1                                          ║
╚═══════════════════════════════════════════════════════════╝
"""
        return risposta
    
    # Estrai il type
    try:
        info_type = int(parti[1])
    except (ValueError, IndexError):
        return "Errore: Specificare un type valido (1-5). Usa 'INFO' per vedere l'help."
    
    # INFO 1: Numero client collegati
    if info_type == 1:
        with stats_lock:
            num_client = statistiche['connessioni_attive']
        risposta = f"""
╔═══════════════════════════════════════════════════════════╗
║           CLIENT ATTUALMENTE COLLEGATI                    ║
╠═══════════════════════════════════════════════════════════╣
║  Numero di client connessi: {num_client:<28}║
║  Totale connessioni:        {statistiche['totale_connessioni']:<28}║
╚═══════════════════════════════════════════════════════════╝
"""
        return risposta
    
    # INFO 2: Numero utenti nel DB
    elif info_type == 2:
        with db_lock:
            num_utenti = len(db_utenti)
            utenti_online = sum(1 for u in db_utenti.values() if u['status'] == 'online')
            utenti_offline = num_utenti - utenti_online
        
        risposta = f"""
╔═══════════════════════════════════════════════════════════╗
║           STATISTICHE DATABASE UTENTI                     ║
╠═══════════════════════════════════════════════════════════╣
║  Totale utenti nel DB:      {num_utenti:<28}║
║  Utenti online:             {utenti_online:<28}║
║  Utenti offline:            {utenti_offline:<28}║
╚═══════════════════════════════════════════════════════════╝
"""
        return risposta
    
    # INFO 3: Informazioni di rete del server
    elif info_type == 3:
        return get_info_server()
    
    # INFO 4: Informazioni di rete del client
    elif info_type == 4:
        # Questa operazione deve essere gestita dal client
        # Il server invia un comando speciale che dice al client di elaborare
        return "CLIENT_HANDLE_INFO_4"
    
    # INFO 5: Lista utenti disponibili per chat
    elif info_type == 5:
        with db_lock:
            utenti_online = [(username, dati['nome']) 
                           for username, dati in db_utenti.items() 
                           if dati['status'] == 'online']
        
        if not utenti_online:
            return "Nessun utente disponibile per chat al momento."
        
        risposta = """
╔═══════════════════════════════════════════════════════════╗
║           UTENTI DISPONIBILI PER CHAT                     ║
╠═══════════════════════════════════════════════════════════╣
"""
        for username, nome in utenti_online:
            riga = f"║  • {username:<15} - {nome:<32}║\n"
            risposta += riga
        
        risposta += "╚═══════════════════════════════════════════════════════════╝"
        return risposta
    
    else:
        return f"Errore: Type {info_type} non valido. Usare un valore tra 1 e 5."

def gestisci_client(mio_socket, client_address, log_filename):
    """Gestisce la comunicazione con un singolo client"""
    client_id = f"{client_address[0]}:{client_address[1]}"
    client_name = get_client_name(client_address)
    
    # Imposta timeout sul socket del client per permettere chiusura controllata
    mio_socket.settimeout(1.0)
    
    # Invia il nome identificativo al client appena si connette
    try:
        mio_socket.send(client_name.encode('utf-8'))
    except Exception:
        pass
    
    log_to_xml(log_filename, "INFO", "CONNECTION", 
               f"Connessione da {client_id} ({client_name})",
               client_ip=client_address[0],
               client_port=client_address[1],
               client_name=client_name)
    
    aggiorna_stats('totale_connessioni')
    aggiorna_stats('connessioni_attive')
    
    try:
        while server_running:
            try:
                # Ricezione messaggio dal client con timeout
                data = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip()
                
                # Stampa sempre il messaggio ricevuto dal client in console
                if data:
                    print(f"{Colori.CIANO}[{client_name}]{Colori.RESET} Messaggio dal client: {data}")
                
                # Se il client si è disconnesso (stringa vuota)
                if not data:
                    log_to_xml(log_filename, "INFO", "DISCONNECTION",
                              f"Client {client_id} ({client_name}) ha chiuso la connessione",
                              client=client_id,
                              client_name=client_name,
                              reason="socket_closed")
                    break
                    
                log_to_xml(log_filename, "INFO", "REQUEST",
                          f"Richiesta '{data}' da {client_id} ({client_name})",
                          client=client_id,
                          client_name=client_name,
                          command=data)

                # Elaborazione comandi
                comando = data.upper()
                
                if comando == "TIME":
                    current_time = datetime.now().strftime("%H:%M:%S")
                    risposta = f"Ciao {client_name} ({client_address[0]}) - Ora corrente: {current_time}"
                    mio_socket.send(risposta.encode('utf-8'))
                    
                    log_to_xml(log_filename, "INFO", "RESPONSE",
                              f"Risposta TIME inviata a {client_id} ({client_name})",
                              client=client_id,
                              client_name=client_name,
                              command="TIME",
                              response=current_time)
                    aggiorna_stats('comandi_time')
                    
                elif comando == "NAME":
                    hostname = socket.gethostname()
                    risposta = f"Ciao {client_name} ({client_address[0]}) - Hostname server: {hostname}"
                    mio_socket.send(risposta.encode('utf-8'))
                    
                    log_to_xml(log_filename, "INFO", "RESPONSE",
                              f"Risposta NAME inviata a {client_id} ({client_name})",
                              client=client_id,
                              client_name=client_name,
                              command="NAME",
                              response=hostname)
                    aggiorna_stats('comandi_name')
                    
                elif comando == "EXIT":
                    risposta = f"Ciao {client_name} ({client_address[0]}) - Disconnessione in corso..."
                    mio_socket.send(risposta.encode('utf-8'))
                    
                    log_to_xml(log_filename, "INFO", "EXIT_REQUEST",
                              f"EXIT richiesto da {client_id} ({client_name})",
                              client=client_id,
                              client_name=client_name)
                    aggiorna_stats('comandi_exit')
                    break
                    
                elif comando == "STATS":
                    with stats_lock:
                        risposta = (f"STATISTICHE SERVER | "
                                  f"Tot.Conn: {statistiche['totale_connessioni']} | "
                                  f"Attive: {statistiche['connessioni_attive']} | "
                                  f"TIME: {statistiche['comandi_time']} | "
                                  f"NAME: {statistiche['comandi_name']} | "
                                  f"INFO: {statistiche['comandi_info']} | "
                                  f"EXIT: {statistiche['comandi_exit']}")
                    mio_socket.send(risposta.encode('utf-8'))
                    
                    log_to_xml(log_filename, "INFO", "STATS",
                              f"Statistiche inviate a {client_id} ({client_name})",
                              client=client_id,
                              client_name=client_name,
                              total_connections=statistiche['totale_connessioni'],
                              active_connections=statistiche['connessioni_attive'])
                
                elif comando.startswith("INFO"):
                    # Gestisci comando INFO
                    risposta = gestisci_comando_info(comando, client_address, client_name)
                    mio_socket.send(risposta.encode('utf-8'))
                    
                    log_to_xml(log_filename, "INFO", "INFO_RESPONSE",
                              f"Risposta INFO inviata a {client_id} ({client_name})",
                              client=client_id,
                              client_name=client_name,
                              command=comando)
                    aggiorna_stats('comandi_info')
                    
                else:
                    risposta = f"Comando '{data}' non riconosciuto. Comandi: TIME, NAME, INFO, STATS, EXIT"
                    mio_socket.send(risposta.encode('utf-8'))
                    print(f"{Colori.GIALLO}Comando non riconosciuto da {Colori.BLU}{client_name}{Colori.RESET}: {data}{Colori.RESET}")
                    log_to_xml(log_filename, "WARNING", "INVALID_COMMAND",
                              f"Comando invalido '{data}' da {client_id} ({client_name})",
                              client=client_id,
                              client_name=client_name,
                              invalid_command=data)
                    aggiorna_stats('comandi_invalidi')
                    
            except socket.timeout:
                # Timeout normale, continua il loop
                continue
                
    except ConnectionResetError:
        log_to_xml(log_filename, "WARNING", "CONNECTION_ERROR",
                  f"Connessione interrotta da {client_id} ({client_name})",
                  client=client_id,
                  client_name=client_name,
                  error_type="ConnectionResetError")
    except Exception as e:
        if server_running:  # Log solo se non stiamo chiudendo
            log_to_xml(log_filename, "ERROR", "EXCEPTION",
                      f"Errore con client {client_id} ({client_name}): {e}",
                      client=client_id,
                      client_name=client_name,
                      exception_type=type(e).__name__,
                      exception_message=str(e))
    finally:
        try:
            mio_socket.close()
        except:
            pass
        aggiorna_stats('connessioni_attive', -1)
        
        log_to_xml(log_filename, "INFO", "THREAD_CLOSE",
                  f"Chiusura thread per {client_id} ({client_name})",
                  client=client_id,
                  client_name=client_name,
                  active_threads=threading.active_count() - 1)

def aggiungi_statistiche_finali(log_filename):
    """Aggiunge le statistiche finali nel file XML"""
    with xml_lock:
        try:
            tree = ET.parse(log_filename)
            root = tree.getroot()
            
            sessions = root.findall("session")
            if sessions:
                current_session = sessions[-1]
                current_session.set("end_time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                
                # Aggiungi statistiche finali
                stats_elem = ET.SubElement(current_session, "final_statistics")
                with stats_lock:
                    for key, value in statistiche.items():
                        stat = ET.SubElement(stats_elem, key.replace('_', '-'))
                        stat.text = str(value)
                
                ET.indent(tree, space="  ")
                tree.write(log_filename, encoding='utf-8', xml_declaration=True)
        except Exception as e:
            print(f"Errore scrittura statistiche finali: {e}")

def mostra_statistiche():
    """Mostra statistiche finali del server"""
    print("\n" + "=" * 60)
    print("STATISTICHE FINALI SERVER")
    print("=" * 60)
    with stats_lock:
        for chiave, valore in statistiche.items():
            print(f"  {chiave.replace('_', ' ').title()}: {valore}")
    print("=" * 60)

def signal_handler(sig, frame):
    """Gestisce il segnale CTRL+C"""
    global server_running
    print(f"\n{Colori.GIALLO}CTRL+C ricevuto - Chiusura server in corso...{Colori.RESET}")
    server_running = False

# MAIN del server
if __name__ == "__main__":
    print("=" * 60)
    print("AVVIO SERVER TCP (Log XML)")
    print("=" * 60)
    
    # Registra handler per CTRL+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Setup log XML
    log_filename = setup_xml_log()
    print(f"Log XML: {log_filename}")
    
    log_to_xml(log_filename, "INFO", "SERVER_START",
               "Server TCP avviato",
               port=12345,
               host="0.0.0.0")
    
    # Creazione socket
    mio_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mio_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # IMPORTANTE: Imposta timeout sul socket server
    mio_server.settimeout(1.0)

    porta = 12345
    mio_server.bind(("0.0.0.0", porta))
    mio_server.listen(5)
    
    print(f"Server in ascolto su porta {porta}")
    print("Comandi disponibili: TIME, NAME, INFO, STATS, EXIT")
    print(f"{Colori.VERDE}Premi CTRL+C per fermare il server{Colori.RESET}")
    print("-" * 60)

    try:
        while server_running:
            try:
                mio_socket, client_address = mio_server.accept()
                
                if not server_running:
                    mio_socket.close()
                    break
                
                thread_client = threading.Thread(
                    target=gestisci_client, 
                    args=(mio_socket, client_address, log_filename),
                    daemon=True
                )
                thread_client.start()
                
                print(f"Thread attivi: {threading.active_count() - 1}")
                
            except socket.timeout:
                # Timeout normale, continua il loop
                continue
    
    except Exception as e:
        print(f"ERRORE FATALE: {e}")
        log_to_xml(log_filename, "ERROR", "FATAL_ERROR",
                   f"Errore fatale server: {e}",
                   exception_type=type(e).__name__)
    finally:
        mio_server.close()
        log_to_xml(log_filename, "INFO", "SERVER_SHUTDOWN",
                   "Server chiuso correttamente")
        aggiungi_statistiche_finali(log_filename)
        mostra_statistiche()
        print(f"{Colori.VERDE}Server chiuso correttamente{Colori.RESET}")