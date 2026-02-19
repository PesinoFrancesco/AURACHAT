import authenticator
import logger
import socket
import threading
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import time
import os
from colorama import Fore, Style, init
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

SECRET_TOKEN = "AURACHAT"  # TOKEN SEGRETO PER DISCOVERY
DISCOVERY_PORT = 9999  # Porta UDP per discovery

# Flag per shutdown controllato
server_running = True


def get_info_server():
    """Restituisce informazioni di rete del server in formato semplice"""
    hostname = socket.gethostname()
    try:
        
        ip_address = socket.gethostbyname(hostname)
    except:
        ip_address = "N/A"
    sistema = platform.system()
    versione = platform.version()
    # Sanifica i dati per il logging XML (rimuove < > che causano errori)
    versione_safe = versione[:40].replace("<", "[").replace(">", "]")
    info = (
        f"SERVER INFO:\n"
        f"  Hostname: {hostname}\n"
        f"  IP Address: {ip_address}\n"
        f"  Porta: 12345\n"
        f"  Sistema: {sistema}\n"
        f"  Versione: {versione_safe}"
    )
    return info

def gestisci_comando_info(comando_completo):
    """
    Gestisce il comando INFO e le sue varianti, risposta semplice senza grafiche
    Sanifica i dati prima del logging per evitare errori XML
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
        num_client = len(authenticator.utenti_connessi)
        risposta = (
            f"Client collegati: {num_client}"
        )
        return risposta
    elif info_type == 2:
        data = authenticator.carica_utenti()
        num_utenti = len(data['users'])
        risposta = (
            f"Utenti nel DB: {num_utenti}"
        )
        return risposta
    elif info_type == 3:
        return get_info_server()
    elif info_type == 4:
        return "CLIENT_HANDLE_INFO_4"
    elif info_type == 5:
        data = authenticator.carica_utenti()
        utenti_online = [u['username'] for u in data['users']]
        if not utenti_online:
            return "Nessun utente disponibile per chat al momento."
        # Sanifica usernames prima di loggare
        utenti_safe = [u.replace("<", "[").replace(">", "]") for u in utenti_online]
        risposta = "Utenti disponibili per chat:\n" + "\n".join(f"  - {username}" for username in utenti_safe)
        return risposta
    else:
        return f"Errore: Type {info_type} non valido. Usare un valore tra 1 e 5."

def autenticazione(mio_socket, client_address, server_log_filename):
    """
    Gestisce l'autenticazione del client
    Restituisce: (True, username, client_log_filename) se successo, (False, None, None) altrimenti
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
                
                if authenticator.verifica_credenziali(username, password):
                    # Verifica se utente già connesso
                    with authenticator.utenti_lock:
                        if username in authenticator.utenti_connessi:
                            mio_socket.send("AUTH_FAIL|Utente già connesso da un altro client!".encode('utf-8'))
                            logger.log_to_xml(server_log_filename, "WARNING", "AUTH", f"Tentativo login con utente già connesso: {username}")
                            return False, None
                    
                    authenticator.aggiorna_ultimo_accesso(username)
                    mio_socket.send(f"AUTH_SUCCESS|Benvenuto {username}!".encode('utf-8'))
                    
                    # Crea log specifico per questo client
                    client_log_filename = logger.setup_client_log(username, client_address)
                    
                    logger.log_to_xml(server_log_filename, "INFO", "AUTH", f"Login effettuato: {username}")
                    logger.log_to_xml(client_log_filename, "INFO", "AUTH", f"Login effettuato da {client_address[0]}:{client_address[1]}")
                    
                    return True, username, client_log_filename
                else:
                    tentativi_rimasti = 2 - tentativo
                    if tentativi_rimasti > 0:
                        mio_socket.send(f"AUTH_RETRY|Credenziali errate! {tentativi_rimasti} tentativi rimasti".encode('utf-8'))
                    else:
                        mio_socket.send("AUTH_FAIL|Credenziali errate! Accesso negato".encode('utf-8'))
                    
                    logger.log_to_xml(server_log_filename, "WARNING", "AUTH", f"Tentativo login fallito per username: {username}")
            
            return False, None
            
        elif risposta == "NO":
            # REGISTRAZIONE
            while True:
                mio_socket.send("REG_USERNAME|Scegli un username (univoco lunghezza min. 3): ".encode('utf-8'))
                username = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip()
                
                if not username or len(username) < 3:
                    mio_socket.send("REG_RETRY|Username troppo corto (minimo 3 caratteri)".encode('utf-8'))
                    continue
                
                if authenticator.username_esiste(username):
                    mio_socket.send("REG_RETRY|Username già esistente, scegline un altro".encode('utf-8'))
                    continue
                
                break
            
            mio_socket.send("REG_PASSWORD|Scegli una password (lunghezza min. 4): ".encode('utf-8'))
            password = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip()
            
            if len(password) < 4:
                mio_socket.send("REG_FAIL|Password troppo corta (minimo 4 caratteri)".encode('utf-8'))
                return False, None
            
            # Registra utente
            authenticator.registra_utente(username, password, client_address[0], client_address[1])
            mio_socket.send(f"REG_SUCCESS|Account creato! Benvenuto {username}!".encode('utf-8'))

            # Crea log specifico per questo client
            client_log_filename = logger.setup_client_log(username, client_address)
            
            logger.log_to_xml(server_log_filename, "INFO", "REGISTRATION", f"Nuovo utente registrato: {username}")
            logger.log_to_xml(client_log_filename, "INFO", "REGISTRATION", f"Account creato da {client_address[0]}:{client_address[1]}")
            
            return True, username, client_log_filename
        else:
            mio_socket.send("AUTH_FAIL|Risposta non valida".encode('utf-8'))
            return False, None, None

    except Exception as e:
        logger.log_to_xml(server_log_filename, "ERROR", "AUTH_ERROR", f"Errore durante autenticazione: {e}")
        return False, None, None
    

def invia_file_log(socket_dest, nome_file, tipo_log, numero_log=0):
    if not os.path.exists(nome_file):
        return 

    with open(nome_file, "r", encoding="utf-8") as f:
        contenuto = f.read()

    da_inviare = ""
    
    # Capiamo il formato direttamente dall'estensione del file (.xml o altro)
    is_xml = nome_file.lower().endswith(".xml")

    # --- SE E' XML ---
    if is_xml:
        if numero_log == 0:
            da_inviare = contenuto # Se vuole tutto, mando tutto così com'è
        else:
            # 1. Trova dove inizia la prima <entry>
            idx = contenuto.find("<entry")
            
            if idx != -1:
                # HEADER: Prendo tutto quello che c'è prima (Root + Session start)
                header = contenuto[:idx] 
                
                # CORPO: Prendo il resto e lo spezzo usando la chiusura del tag
                resto_del_file = contenuto[idx:]
                blocchi = resto_del_file.split('</entry>')
                
                # Ricostruisco i blocchi validi (rimettendo </entry> che lo split toglie)
                entries = [b + "</entry>" for b in blocchi if "<entry" in b]
                
                # Prendo solo gli ultimi N richiesti
                ultime_entries = entries[-numero_log:]
                
                # 2. Unisco: Header + Entries Scelte + Chiusura Tag Root e Session
                da_inviare = header + "\n".join(ultime_entries) + "\n  </session>\n</log>"
            else:
                da_inviare = contenuto # Caso raro: file senza entry

    # --- SE E' CSV o TXT ---
    else:
        righe = contenuto.splitlines(keepends=True)
        if numero_log == 0 or numero_log >= len(righe):
            da_inviare = contenuto
        else:
            # Header (riga 0) + Ultime N righe
            header = righe[0] 
            body = righe[-numero_log:]
            da_inviare = header + "".join(body)

    # --- INVIO SUL SOCKET ---
    if da_inviare:
        dati_bytes = da_inviare.encode('utf-8')
        dimensione = len(dati_bytes)
        
        header = f"FILE_START:{tipo_log}:{dimensione}"
        
        socket_dest.send(header.encode('utf-8'))
        
        # Aspetto pronto
        ack = socket_dest.recv(1024).decode('utf-8')
        if ack.strip() == "READY":
            socket_dest.sendall(dati_bytes)
        else:
            print(f"Errore: Client non pronto. Ha risposto: {ack}")

def gestisci_client(mio_socket, client_address, server_log_filename):
    """Gestisce la comunicazione con un singolo client"""
    client_id = f"{client_address[0]}:{client_address[1]}"
    
    # AUTENTICAZIONE
    auth_ok, username, client_log_filename = autenticazione(mio_socket, client_address, server_log_filename)
    
    if not auth_ok:
        logger.log_to_xml(server_log_filename, "WARNING", "AUTH_FAILED", f"Autenticazione fallita per {client_id}")
        mio_socket.close()
        return
    
    # Aggiungi alla lista utenti connessi
    with authenticator.utenti_lock:
        authenticator.utenti_connessi[username] = (mio_socket, client_address)

    logger.log_to_xml(server_log_filename, "INFO", "CONNECTION", f"Utente {username} connesso da {client_id}")
    logger.log_to_xml(client_log_filename, "INFO", "CONNECTION", f"Connesso al server")
    try:
        while server_running:
            data = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip()
            if data:
                print(f"[CLIENT {username}] Messaggio: {data}")
            
            if not data:
                logger.log_to_xml(server_log_filename, "INFO", "DISCONNECTION", f"Utente {username} ha chiuso la connessione")
                logger.log_to_xml(client_log_filename, "INFO", "DISCONNECTION", "Connessione chiusa")
                break
                
            comando = data.upper()
            
            if comando == "TIME":
                current_time = datetime.now().strftime("%H:%M:%S")
                risposta = f"Ora corrente: {current_time}"
                mio_socket.send(risposta.encode('utf-8'))
                logger.log_to_xml(client_log_filename, "INFO", "RESPONSE", f"Risposta TIME ricevuta")

                
            elif comando == "NAME":
                hostname = socket.gethostname()
                risposta = f"Hostname server: {hostname}"
                mio_socket.send(risposta.encode('utf-8'))
                logger.log_to_xml(client_log_filename, "INFO", "RESPONSE", f"Risposta NAME ricevuta")
                
            
            
            elif comando == "EXIT":
                risposta = f"Disconnessione in corso..."
                mio_socket.send(risposta.encode('utf-8'))
                logger.log_to_xml(server_log_filename, "INFO", "EXIT_REQUEST", f"EXIT richiesto da {username}")
                logger.log_to_xml(client_log_filename, "INFO", "EXIT", "Comando EXIT eseguito")
                break
                
            elif comando.startswith("INFO"):
                risposta = gestisci_comando_info(data)
                mio_socket.send(risposta.encode('utf-8'))
                logger.log_to_xml(client_log_filename, "INFO", "RESPONSE", f"Risposta INFO ricevuta")
            
            elif comando.startswith("LOG"):
                    parti = comando.split()
                    # Se non metti la data, usa quella di oggi
                    data_log = datetime.now().strftime('%Y-%m-%d')
                    if len(parti) > 1:
                        data_log = parti[1]
                    
                    nome_file_xml = f"logs/client_{username}_{data_log}.xml"
                    
                    if os.path.exists(nome_file_xml):
                        nome_file_txt = logger.converti_xml_in_txt(nome_file_xml)
                        with open(nome_file_txt, "r", encoding="utf-8") as f:
                            testo_log = f.read()
                        
                        # MANDIAMO UN SEGNALE DI INIZIO SPECIALE
                        mio_socket.send("START_DISPLAY_LOG".encode('utf-8'))
                        time.sleep(0.2) # Piccolo delay per non fondere i pacchetti
                        
                        # Inviamo il testo (il client lo riceverà un pezzo alla volta)
                        mio_socket.sendall(testo_log.encode('utf-8'))
                        time.sleep(0.2) # Piccolo delay per non fondere i pacchetti

                        # MANDIAMO IL SEGNALE DI FINE (riutilizziamo quello che hai già)
                        mio_socket.send("FINE_INVIO".encode('utf-8'))
                        
                        if os.path.exists(nome_file_txt): os.remove(nome_file_txt)
                    else:
                        mio_socket.send(f"ERRORE: Nessun log trovato per la data {data_log}".encode('utf-8'))

            elif comando.startswith("EX"):
                    parti = comando.split()
    
                    # 1. IMPOSTAZIONE DEFAULT (Sempre eseguiti)
                    numero = 0       # 0 significa "tutti"
                    target = "tutti" # può essere "client", "server" o "tutti"
                    formato = "xml"  # Formato base
                    
                    # 2. PARSING (Eseguito solo se ci sono parametri)
                    if len(parti) >= 2:
                        formato = parti[1].lower() # xml, csv, txt

                        # Analizza i parametri extra (es: EX csv 10 server)
                        for p in parti[2:]:
                            if p.isdigit():
                                numero = int(p)      # È il numero di log
                            elif p.lower() in ["client", "server"]:
                                target = p.lower()   # È il target

                    # 3. SELEZIONE E CONVERSIONE FILE (Sempre eseguita)
                    file_c = client_log_filename
                    file_s = server_log_filename
                    
                    if formato == "csv":
                        file_c = logger.converti_xml_in_csv(client_log_filename)
                        file_s = logger.converti_xml_in_csv(server_log_filename)
                    elif formato == "txt":
                        file_c = logger.converti_xml_in_txt(client_log_filename)
                        file_s = logger.converti_xml_in_txt(server_log_filename)

                    # 4. ESECUZIONE INVIO (Sempre eseguita)
                    # Se il target è "client" o "tutti"
                    if target == "client" or target == "tutti":
                        if file_c:
                            invia_file_log(mio_socket, file_c, "CLIENT", numero)
                        
                    # Se il target è "server" o "tutti"
                    if target == "server" or target == "tutti":
                        if file_s:
                            invia_file_log(mio_socket, file_s, "SERVER", numero)

                    # 5. SEGNALE DI CHIUSURA (Fondamentale per non bloccare il client)
                    mio_socket.send("FINE_INVIO".encode('utf-8'))

            else:
                # Gestione comandi non riconosciuti
                risposta = f"Comando '{comando}' non riconosciuto. Comandi: TIME, NAME, INFO, LOG, EX, EXIT"
                mio_socket.send(risposta.encode('utf-8'))
                logger.log_to_xml(client_log_filename, "WARNING", "UNKNOWN_COMMAND", f"Comando non riconosciuto: {comando}")

    except ConnectionResetError:
        logger.log_to_xml(server_log_filename, "WARNING", "CONNECTION_ERROR", f"{Colori.ROSSO}Connessione interrotta da {username}")
        logger.log_to_xml(client_log_filename, "WARNING", "CONNECTION_ERROR", "Connessione interrotta improvvisamente")
    except Exception as e:
        logger.log_to_xml(server_log_filename, "ERROR", "EXCEPTION", f"{Colori.ROSSO}Errore con utente {username}: {e}")
        logger.log_to_xml(client_log_filename, "ERROR", "EXCEPTION", f"Errore: {e}")
    finally:
        # Rimuovi dalla lista utenti connessi
        with authenticator.utenti_lock:
            if username in authenticator.utenti_connessi:
                del authenticator.utenti_connessi[username]
        
        try:
            mio_socket.close()
        except:
            pass
        
        logger.log_to_xml(server_log_filename, "INFO", "THREAD_CLOSE", f"Chiusura thread per {username}")
        logger.log_to_xml(client_log_filename, "INFO", "SESSION_END", "Sessione terminata")
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
                if (messaggio == f"DISCOVER|{SECRET_TOKEN}"):
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

def main():
    print("=" * 60)
    print("AVVIO SERVER TCP")
    print("=" * 60)

    authenticator.setup_config()
    server_log_filename = logger.setup_xml_log()
    print(f"Log SERVER: {server_log_filename}")
    print(f"Config utenti: {authenticator.CONFIG_FILE}")
    print(f"Token Discovery: {SECRET_TOKEN}")
    
    logger.log_to_xml(server_log_filename, "INFO", "SERVER_START", "Server TCP avviato con sistema autenticazione")
    
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
                    args=(mio_socket, client_address, server_log_filename),
                    daemon=True
                )
                thread_client.start()
                
                print(f"Thread attivi: {threading.active_count() - 1}")
            except socket.timeout:
                continue
    
    except Exception as e:
        print(f"ERRORE FATALE: {e}")
        logger.log_to_xml(server_log_filename, "ERROR", "FATAL_ERROR", f"Errore fatale server: {e}")
    finally:
        mio_server.close()
        logger.log_to_xml(server_log_filename, "INFO", "SERVER_SHUTDOWN", "Server chiuso correttamente")
        print(f"{Colori.VERDE}Server chiuso correttamente{Colori.RESET}")

main()
