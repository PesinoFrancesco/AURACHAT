import socket
import threading
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import json
import os
from colorama import Fore, Back, Style, init
import signal
import platform

# Inizializza colorama per Windows
init(autoreset=True)

# --- COLORI COLORAMA ---
class Colori:
    RESET = Style.RESET_ALL
    ROSSO = Fore.RED
    VERDE = Fore.GREEN
    GIALLO = Fore.YELLOW
    BLU = Fore.BLUE
    MAGENTA = Fore.MAGENTA
    CIANO = Fore.CYAN
    GRIGIO = Fore.LIGHTBLACK_EX
    BOLD = Style.BRIGHT

# File configurazione utenti
CONFIG_FILE = "config/users.json"
config_lock = threading.Lock()

SECRET_TOKEN = "AURACHAT"  # TOKEN SEGRETO PER DISCOVERY
DISCOVERY_PORT = 9999  # Porta UDP per discovery

# Statistiche globali del server
statistiche = {
    'totale_connessioni': 0,
    'connessioni_attive': 0,
    'comandi_time': 0,
    'comandi_name': 0,
    'comandi_exit': 0,
    'comandi_invalidi': 0,
    'login_successo': 0,
    'registrazioni': 0,
    'comandi_info': 0
}
stats_lock = threading.Lock()

# Lock per scrittura XML thread-safe
xml_lock = threading.Lock()

# Mappa utenti connessi {username: (socket, address)}
utenti_connessi = {}
utenti_lock = threading.Lock()

# Flag per shutdown controllato
server_running = True

def setup_config():
    """Crea la cartella config e il file users.json se non esistono"""
    Path("config").mkdir(exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"users": []}, f, indent=2)

def carica_utenti():
    """Carica gli utenti dal file JSON"""
    with config_lock:
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"users": []}

def salva_utenti(data):
    """Salva gli utenti nel file JSON"""
    with config_lock:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=2)

def verifica_credenziali(username, password):
    """Verifica se username e password sono corretti"""
    data = carica_utenti()    
    for user in data['users']:
        if user['username'] == username and user['password'] == password:
            return True
    return False

def username_esiste(username):
    """Controlla se un username esiste già"""
    data = carica_utenti()
    for user in data['users']:
        if user['username'] == username:
            return True
    return False

def registra_utente(username, password, ip, porta):
    """Registra un nuovo utente"""
    data = carica_utenti()
    
    nuovo_utente = {
        "username": username,
        "password": password,
        "ip": ip,
        "porta": porta,
        "data_registrazione": datetime.now().isoformat(),
        "ultimo_accesso": datetime.now().isoformat()
    }
    
    data['users'].append(nuovo_utente)
    salva_utenti(data)
    return True

def aggiorna_ultimo_accesso(username):
    """Aggiorna la data di ultimo accesso"""
    data = carica_utenti()
    for user in data['users']:
        if user['username'] == username:
            user['ultimo_accesso'] = datetime.now().isoformat()
            break
    salva_utenti(data)

def setup_xml_log():
    """Configura il file XML di log"""
    Path("logs").mkdir(exist_ok=True)
    log_filename = f"logs/server_{datetime.now().strftime('%Y-%m-%d')}.xml"
    
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
    """Scrive un'entry nel file XML di log in modo thread-safe"""
    with xml_lock:
        try:
            tree = ET.parse(log_filename)
            root = tree.getroot()
            
            sessions = root.findall("session")
            if sessions:
                current_session = sessions[-1]
            else:
                current_session = ET.SubElement(root, "session")
                current_session.set("start_time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            entry = ET.SubElement(current_session, "entry")
            entry.set("timestamp", datetime.now().strftime('%H:%M:%S'))
            entry.set("level", level)
            entry.set("type", log_type)
            
            msg_elem = ET.SubElement(entry, "message")
            msg_elem.text = message
            
            for key, value in extra_data.items():
                elem = ET.SubElement(entry, key)
                elem.text = str(value)
            
            ET.indent(tree, space="  ")
            tree.write(log_filename, encoding='utf-8', xml_declaration=True)
            
            if level == "INFO":
                level_colored = Colori.VERDE + level + Colori.RESET
            elif level == "WARNING":
                level_colored = Colori.GIALLO + level + Colori.RESET
            elif level == "ERROR":
                level_colored = Colori.ROSSO + level + Colori.RESET
            else:
                level_colored = level
                
            username = extra_data.get('username', None)
            if username:
                username_colored = Colori.BLU + username + Colori.RESET
                msg_colored = message.replace(str(username), username_colored)
            else:
                msg_colored = message
                
            if log_type in ["CONNECTION", "ERROR", "DISCONNECTION", "AUTH", "REGISTRATION"]:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level_colored}] {msg_colored}")
        except Exception as e:
            print(f"Errore scrittura XML log: {e}")

def aggiorna_stats(campo, incremento=1):
    """Aggiorna statistiche in modo thread-safe"""
    with stats_lock:
        statistiche[campo] += incremento

def get_info_server():
    """Restituisce informazioni di rete del server in formato semplice"""
    hostname = socket.gethostname()
    try:
        ip_address = socket.gethostbyname(hostname)
    except:
        ip_address = "N/A"
    sistema = platform.system()
    versione = platform.version()
    info = (
        f"SERVER INFO:\n"
        f"  Hostname: {hostname}\n"
        f"  IP Address: {ip_address}\n"
        f"  Porta: 12345\n"
        f"  Sistema: {sistema}\n"
        f"  Versione: {versione[:40]}"
    )
    return info

def gestisci_comando_info(comando_completo, client_address, username):
    """
    Gestisce il comando INFO e le sue varianti, risposta semplice senza grafiche
    """
    parti = comando_completo.split()
    if len(parti) == 1:
        risposta = (
            "Comando INFO - HELP\n"
            "  Uso: INFO [type]\n"
            "  Type disponibili:\n"
            "    1 → Numero di client attualmente collegati\n"
            "    2 → Numero di utenti presenti nel DB\n"
            "    3 → Info rete del server\n"
            "    4 → Info rete del client (solo client)\n"
            "    5 → Lista utenti disponibili per chat\n"
            "  Esempio: INFO 1"
        )
        return risposta
    try:
        info_type = int(parti[1])
    except (ValueError, IndexError):
        return "Errore: Specificare un type valido (1-5). Usa 'INFO' per vedere l'help."
    if info_type == 1:
        with stats_lock:
            num_client = statistiche['connessioni_attive']
        risposta = (
            f"Client collegati: {num_client}\n"
            f"Totale connessioni: {statistiche['totale_connessioni']}"
        )
        return risposta
    elif info_type == 2:
        data = carica_utenti()
        num_utenti = len(data['users'])
        utenti_online = len([u for u in data['users'] if 'ultimo_accesso' in u])
        utenti_offline = num_utenti - utenti_online
        risposta = (
            f"Utenti nel DB: {num_utenti}\n"
            f"Online: {utenti_online}\n"
            f"Offline: {utenti_offline}"
        )
        return risposta
    elif info_type == 3:
        return get_info_server()
    elif info_type == 4:
        return "CLIENT_HANDLE_INFO_4"
    elif info_type == 5:
        data = carica_utenti()
        utenti_online = [u['username'] for u in data['users'] if 'ultimo_accesso' in u]
        if not utenti_online:
            return "Nessun utente disponibile per chat al momento."
        risposta = "Utenti disponibili per chat:\n" + "\n".join(f"  - {username}" for username in utenti_online)
        return risposta
    else:
        return f"Errore: Type {info_type} non valido. Usare un valore tra 1 e 5."

def autenticazione(mio_socket, client_address, log_filename):
    """
    Gestisce l'autenticazione del client
    Restituisce: (True, username) se successo, (False, None) altrimenti
    """
    try:
        # Chiedi se ha già un account
        mio_socket.send("AUTH_REQUEST|Hai già un account? (SI/NO): ".encode('utf-8'))
        risposta = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip().upper()
        
        if risposta == "SI":
            # LOGIN
            for tentativo in range(3):
                mio_socket.send("AUTH_USERNAME|Username: ".encode('utf-8'))
                username = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip()
                
                mio_socket.send("AUTH_PASSWORD|Password: ".encode('utf-8'))
                password = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip()
                
                if verifica_credenziali(username, password):
                    # Verifica se utente già connesso
                    with utenti_lock:
                        if username in utenti_connessi:
                            mio_socket.send("AUTH_FAIL|Utente già connesso da un altro client!".encode('utf-8'))
                            log_to_xml(log_filename, "WARNING", "AUTH",
                                      f"Tentativo login con utente già connesso: {username}",
                                      username=username,
                                      client_ip=client_address[0])
                            return False, None
                    
                    aggiorna_ultimo_accesso(username)
                    mio_socket.send(f"AUTH_SUCCESS|Benvenuto {username}!".encode('utf-8'))
                    
                    log_to_xml(log_filename, "INFO", "AUTH",
                              f"Login effettuato: {username}",
                              username=username,
                              client_ip=client_address[0],
                              client_port=client_address[1])
                    
                    aggiorna_stats('login_successo')
                    return True, username
                else:
                    tentativi_rimasti = 2 - tentativo
                    if tentativi_rimasti > 0:
                        mio_socket.send(f"AUTH_RETRY|Credenziali errate! {tentativi_rimasti} tentativi rimasti".encode('utf-8'))
                    else:
                        mio_socket.send("AUTH_FAIL|Credenziali errate! Accesso negato".encode('utf-8'))
                    
                    log_to_xml(log_filename, "WARNING", "AUTH",
                              f"Tentativo login fallito per username: {username}",
                              username=username,
                              client_ip=client_address[0])
            
            return False, None
            
        elif risposta == "NO":
            # REGISTRAZIONE
            while True:
                mio_socket.send("REG_USERNAME|Scegli un username (univoco lunghezza min. 3): ".encode('utf-8'))
                username = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip()
                
                if not username or len(username) < 3:
                    mio_socket.send("REG_RETRY|Username troppo corto (minimo 3 caratteri)".encode('utf-8'))
                    continue
                
                if username_esiste(username):
                    mio_socket.send("REG_RETRY|Username già esistente, scegline un altro".encode('utf-8'))
                    continue
                
                break
            
            mio_socket.send("REG_PASSWORD|Scegli una password (lunghezza min. 4): ".encode('utf-8'))
            password = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip()
            
            if len(password) < 4:
                mio_socket.send("REG_FAIL|Password troppo corta (minimo 4 caratteri)".encode('utf-8'))
                return False, None
            
            # Registra utente
            registra_utente(username, password, client_address[0], client_address[1])
            mio_socket.send(f"REG_SUCCESS|Account creato! Benvenuto {username}!".encode('utf-8'))
            
            log_to_xml(log_filename, "INFO", "REGISTRATION",
                      f"Nuovo utente registrato: {username}",
                      username=username,
                      client_ip=client_address[0],
                      client_port=client_address[1])
            
            aggiorna_stats('registrazioni')
            return True, username
        else:
            mio_socket.send("AUTH_FAIL|Risposta non valida".encode('utf-8'))
            return False, None
            
    except Exception as e:
        log_to_xml(log_filename, "ERROR", "AUTH_ERROR",
                  f"Errore durante autenticazione: {e}",
                  client_ip=client_address[0],
                  exception_type=type(e).__name__)
        return False, None

def gestisci_client(mio_socket, client_address, log_filename):
    """Gestisce la comunicazione con un singolo client"""
    client_id = f"{client_address[0]}:{client_address[1]}"
    
    # AUTENTICAZIONE
    auth_ok, username = autenticazione(mio_socket, client_address, log_filename)
    
    if not auth_ok:
        log_to_xml(log_filename, "WARNING", "AUTH_FAILED",
                  f"Autenticazione fallita per {client_id}",
                  client_ip=client_address[0],
                  client_port=client_address[1])
        mio_socket.close()
        return
    
    # Aggiungi alla lista utenti connessi
    with utenti_lock:
        utenti_connessi[username] = (mio_socket, client_address)
    
    log_to_xml(log_filename, "INFO", "CONNECTION", 
               f"Utente {username} connesso da {client_id}",
               username=username,
               client_ip=client_address[0],
               client_port=client_address[1])
    
    aggiorna_stats('totale_connessioni')
    aggiorna_stats('connessioni_attive')
    
    try:
        while server_running:
            data = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip()
            if data:
                comandi_validi = ["TIME", "NAME", "STATS", "EXIT", "INFO"]
                comando_upper = data.upper()
                print(f"[CLIENT {username}] Messaggio: {data}")
            
            if not data:
                log_to_xml(log_filename, "INFO", "DISCONNECTION",
                          f"Utente {username} ha chiuso la connessione",
                          username=username,
                          reason="socket_closed")
                break
                
            log_to_xml(log_filename, "INFO", "REQUEST",
                      f"Richiesta '{data}' da {username}",
                      username=username,
                      command=data)

            comando = data.upper()
            
            if comando == "TIME":
                current_time = datetime.now().strftime("%H:%M:%S")
                risposta = f"Ora corrente: {current_time}"
                mio_socket.send(risposta.encode('utf-8'))
                aggiorna_stats('comandi_time')
                
            elif comando == "NAME":
                hostname = socket.gethostname()
                risposta = f"Hostname server: {hostname}"
                mio_socket.send(risposta.encode('utf-8'))
                aggiorna_stats('comandi_name')
                
            elif comando == "EXIT":
                risposta = f"Disconnessione in corso..."
                mio_socket.send(risposta.encode('utf-8'))
                log_to_xml(log_filename, "INFO", "EXIT_REQUEST",
                          f"EXIT richiesto da {username}",
                          username=username)
                aggiorna_stats('comandi_exit')
                break
                
            elif comando == "STATS":
                with stats_lock:
                    risposta = (f"STATISTICHE SERVER | "
                              f"Tot.Conn: {statistiche['totale_connessioni']} | "
                              f"Attive: {statistiche['connessioni_attive']} | "
                              f"TIME: {statistiche['comandi_time']} | "
                              f"NAME: {statistiche['comandi_name']} | "
                              f"Registrazioni: {statistiche['registrazioni']}")
                mio_socket.send(risposta.encode('utf-8'))
                
            elif comando.startswith("INFO"):
                risposta = gestisci_comando_info(data, client_address, username)
                mio_socket.send(risposta.encode('utf-8'))
                aggiorna_stats('comandi_info')
                
            else:
                risposta = f"Comando '{data}' non riconosciuto. Comandi: TIME, NAME, INFO, STATS, EXIT"
                mio_socket.send(risposta.encode('utf-8'))
                aggiorna_stats('comandi_invalidi')
                
    except ConnectionResetError:
        log_to_xml(log_filename, "WARNING", "CONNECTION_ERROR",
                  f"{Colori.ROSSO}Connessione interrotta da {username}",
                  username=username,
                  error_type="ConnectionResetError")
    except Exception as e:
        log_to_xml(log_filename, "ERROR", "EXCEPTION",
                  f"{Colori.ROSSO}Errore con utente {username}: {e}",
                  username=username,
                  exception_type=type(e).__name__)
    finally:
        # Rimuovi dalla lista utenti connessi
        with utenti_lock:
            if username in utenti_connessi:
                del utenti_connessi[username]
        
        try:
            mio_socket.close()
        except:
            pass
        aggiorna_stats('connessioni_attive', -1)
        
        log_to_xml(log_filename, "INFO", "THREAD_CLOSE",
                  f"Chiusura thread per {username}",
                  username=username,
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

# Gestione signal per CTRL+C
signal_handler_called = False
def signal_handler(sig, frame):
    global server_running, signal_handler_called
    if not signal_handler_called:
        print(f"\n{Colori.GIALLO}CTRL+C ricevuto - Chiusura server in corso...{Colori.RESET}")
        server_running = False
        signal_handler_called = True


def discovery_listener():
    """
    Thread che ascolta richieste UDP di discovery
    Risponde solo se riceve il token corretto
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        # Ascolta su TUTTE le interfacce di rete
        udp_socket.bind(('', DISCOVERY_PORT))
        print(f"{Colori.VERDE}Discovery listener attivo su porta {DISCOVERY_PORT}{Colori.RESET}")
        
        while server_running:
            try:
                # Aspetta massimo 1 secondo per un messaggio
                udp_socket.settimeout(1.0)
                data, client_addr = udp_socket.recvfrom(1024)
                
                # Decodifica il messaggio ricevuto
                messaggio = data.decode('utf-8', errors='ignore').strip()
                
                # Verifica se è una richiesta valida con il nostro token
                if messaggio == f"DISCOVER|{SECRET_TOKEN}":
                    # Prepara la risposta con: hostname e porta TCP
                    hostname = socket.gethostname()
                    risposta = f"FOUND|{SECRET_TOKEN}|{hostname}|12345"
                    
                    # Invia risposta al client
                    udp_socket.sendto(risposta.encode('utf-8'), client_addr)
                    
                    print(f"{Colori.CIANO}[DISCOVERY] Richiesta da {client_addr[0]} - Risposta inviata{Colori.RESET}")
                else:
                    # Token errato o messaggio invalido - ignora silenziosamente
                    print(f"{Colori.GRIGIO}[DISCOVERY] Richiesta ignorata da {client_addr[0]} (token errato){Colori.RESET}")
                    
            except socket.timeout:
                # Nessun messaggio ricevuto, continua il loop
                continue
            except Exception as e:
                if server_running:  # Mostra errore solo se il server è ancora attivo
                    print(f"{Colori.ROSSO}[DISCOVERY] Errore: {e}{Colori.RESET}")
                    
    except Exception as e:
        print(f"{Colori.ROSSO}Errore fatale discovery listener: {e}{Colori.RESET}")
    finally:
        udp_socket.close()
        print(f"{Colori.GIALLO}Discovery listener chiuso{Colori.RESET}")

if __name__ == "__main__":
    print("=" * 60)
    print("AVVIO SERVER TCP")
    print("=" * 60)
    
    setup_config()
    log_filename = setup_xml_log()
    print(f"Log XML: {log_filename}")
    print(f"Config utenti: {CONFIG_FILE}")
    print(f"Token Discovery: {SECRET_TOKEN}")
    
    log_to_xml(log_filename, "INFO", "SERVER_START",
               "Server TCP avviato con sistema autenticazione",
               port=12345,
               host="0.0.0.0")
    
    mio_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mio_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    porta = 12345
    mio_server.bind(("0.0.0.0", porta))
    mio_server.listen(5)
    
    print(f"Server TCP in ascolto su porta {porta}")
    print("Sistema di autenticazione attivo")

    # Avvia thread discovery UDP
    discovery_thread = threading.Thread(target=discovery_listener, daemon=True)
    discovery_thread.start()

    print("Premi CTRL+C per fermare il server")
    print("-" * 60)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        while server_running:
            mio_server.settimeout(1.0)
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