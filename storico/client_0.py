import socket
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import os
import sys
import time

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

# Statistiche client
statistiche = {
    'messaggi_inviati': 0,
    'messaggi_ricevuti': 0,
    'comandi_time': 0,
    'comandi_name': 0,
    'errori': 0
}

def setup_xml_log():
    """Configura il file XML di log per il client"""
    Path("logs").mkdir(exist_ok=True)
    log_filename = f"logs/client_{datetime.now().strftime('%Y-%m-%d')}.xml"
    
    if not os.path.exists(log_filename):
        root = ET.Element("log")
        root.set("client_name", socket.gethostname())
        root.set("date", datetime.now().strftime('%Y-%m-%d'))
        
        session = ET.SubElement(root, "session")
        session.set("start_time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(log_filename, encoding='utf-8', xml_declaration=True)
    
    return log_filename

def log_to_xml(log_filename, level, log_type, message, **extra_data):
    """Scrive un'entry nel file XML di log"""
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
            
        if log_type in ["CONNECTION", "ERROR", "DISCONNECTION", "AUTH"]:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level_colored}] {msg_colored}")
        
    except Exception as e:
        print(f"Errore scrittura XML log: {e}")

def mostra_menu():
    """Mostra menu comandi disponibili"""
    print("\n" + "=" * 50)
    print("COMANDI DISPONIBILI:")
    print("=" * 50)
    print("  TIME   → Richiedi ora corrente del server")
    print("  NAME   → Richiedi hostname del server")
    print("  STATS  → Mostra statistiche server")
    print("  EXIT   → Disconnetti e chiudi client")
    print("  HELP   → Mostra questo menu")
    print("=" * 50)

def mostra_statistiche():
    """Mostra statistiche client"""
    print("\n" + "=" * 50)
    print("STATISTICHE SESSIONE CLIENT")
    print("=" * 50)
    for chiave, valore in statistiche.items():
        print(f"  {chiave.replace('_', ' ').title()}: {valore}")
    print("=" * 50)

def aggiungi_statistiche_finali(log_filename, username):
    """Aggiunge le statistiche finali nel file XML"""
    try:
        tree = ET.parse(log_filename)
        root = tree.getroot()
        
        sessions = root.findall("session")
        if sessions:
            current_session = sessions[-1]
            current_session.set("end_time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            stats_elem = ET.SubElement(current_session, "final_statistics")
            for key, value in statistiche.items():
                stat = ET.SubElement(stats_elem, key.replace('_', '-'))
                stat.text = str(value)
            
            ET.indent(tree, space="  ")
            tree.write(log_filename, encoding='utf-8', xml_declaration=True)
    except Exception as e:
        print(f"❌ Errore scrittura statistiche finali: {e}")

def autenticazione(mio_socket, log_filename):
    """
    Gestisce il processo di autenticazione con il server
    Restituisce: username se successo, None altrimenti
    """
    try:
        while True:
            # Ricevi richiesta dal server
            data = mio_socket.recv(1024).decode('utf-8', errors='ignore')
            
            if not data:
                return None
            
            # Parse del messaggio: TIPO|Messaggio
            if '|' in data:
                msg_type, msg_text = data.split('|', 1)
            else:
                print(data)
                continue
            
            # AUTH_REQUEST - Chiedi se ha account
            if msg_type == "AUTH_REQUEST":
                print(f"\n{Colori.CIANO}{msg_text}{Colori.RESET}", end='')
                risposta = input().strip().upper()
                mio_socket.send(risposta.encode('utf-8'))
                
            # AUTH_USERNAME - Login username
            elif msg_type == "AUTH_USERNAME":
                print(f"{Colori.GIALLO}{msg_text}{Colori.RESET}", end='')
                username = input().strip()
                mio_socket.send(username.encode('utf-8'))
                
            # AUTH_PASSWORD - Login password
            elif msg_type == "AUTH_PASSWORD":
                print(f"{Colori.GIALLO}{msg_text}{Colori.RESET}", end='')
                password = input().strip()
                mio_socket.send(password.encode('utf-8'))
                
            # REG_USERNAME - Registrazione username
            elif msg_type == "REG_USERNAME":
                print(f"{Colori.VERDE}{msg_text}{Colori.RESET}", end='')
                username = input().strip()
                mio_socket.send(username.encode('utf-8'))
                
            # REG_PASSWORD - Registrazione password
            elif msg_type == "REG_PASSWORD":
                print(f"{Colori.VERDE}{msg_text}{Colori.RESET}", end='')
                password = input().strip()
                mio_socket.send(password.encode('utf-8'))
                
            # AUTH_RETRY - Riprova login
            elif msg_type == "AUTH_RETRY":
                print(f"{Colori.ROSSO}⚠ {msg_text}{Colori.RESET}")
                
            # REG_RETRY - Riprova registrazione
            elif msg_type == "REG_RETRY":
                print(f"{Colori.GIALLO}⚠ {msg_text}{Colori.RESET}")
                
            # AUTH_SUCCESS - Login riuscito
            elif msg_type == "AUTH_SUCCESS":
                print(f"{Colori.VERDE}✓ {msg_text}{Colori.RESET}")
                # Estrai username dal messaggio
                username = msg_text.split("Benvenuto ")[1].rstrip("!")
                log_to_xml(log_filename, "INFO", "AUTH",
                          f"Autenticazione riuscita per {username}",
                          username=username)
                return username
                
            # REG_SUCCESS - Registrazione riuscita
            elif msg_type == "REG_SUCCESS":
                print(f"{Colori.VERDE}✓ {msg_text}{Colori.RESET}")
                username = msg_text.split("Benvenuto ")[1].rstrip("!")
                log_to_xml(log_filename, "INFO", "AUTH",
                          f"Registrazione completata per {username}",
                          username=username)
                return username
                
            # AUTH_FAIL / REG_FAIL - Fallimento
            elif msg_type in ["AUTH_FAIL", "REG_FAIL"]:
                print(f"{Colori.ROSSO}✗ {msg_text}{Colori.RESET}")
                log_to_xml(log_filename, "ERROR", "AUTH",
                          f"Autenticazione fallita: {msg_text}")
                return None
                
    except Exception as e:
        print(f"{Colori.ROSSO}Errore durante autenticazione: {e}{Colori.RESET}")
        log_to_xml(log_filename, "ERROR", "AUTH_ERROR",
                  f"Errore autenticazione: {e}",
                  exception_type=type(e).__name__)
        return None

def connetti_al_server(log_filename, host="127.0.0.1", porta=12345, tentativi=3):
    """Tenta di connettersi al server con retry automatico"""
    for tentativo in range(1, tentativi + 1):
        try:
            log_to_xml(log_filename, "INFO", "CONNECTION_ATTEMPT",
                      f"Tentativo {tentativo}/{tentativi} di connessione a {host}:{porta}",
                      attempt=tentativo,
                      max_attempts=tentativi,
                      server_host=host,
                      server_port=porta)
            
            mio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            mio_socket.settimeout(5)
            mio_socket.connect((host, porta))
            
            log_to_xml(log_filename, "INFO", "CONNECTION",
                      f"Connesso al server {host}:{porta}",
                      server_host=host,
                      server_port=porta)
            
            return mio_socket
            
        except socket.timeout:
            log_to_xml(log_filename, "ERROR", "TIMEOUT",
                      f"Timeout connessione (tentativo {tentativo}/{tentativi})",
                      attempt=tentativo,
                      server=f"{host}:{porta}")
        except ConnectionRefusedError:
            log_to_xml(log_filename, "ERROR", "CONNECTION_REFUSED",
                      f"Server non raggiungibile su {host}:{porta} (tentativo {tentativo}/{tentativi})",
                      attempt=tentativo,
                      server=f"{host}:{porta}")
        except Exception as e:
            log_to_xml(log_filename, "ERROR", "CONNECTION_ERROR",
                      f"Errore connessione: {e} (tentativo {tentativo}/{tentativi})",
                      attempt=tentativo,
                      exception_type=type(e).__name__)
        
        if tentativo < tentativi:
            print(f"Riprovo tra 2 secondi...")
            time.sleep(2)
    
    log_to_xml(log_filename, "ERROR", "CONNECTION_FAILED",
               "Impossibile connettersi al server dopo tutti i tentativi",
               total_attempts=tentativi)
    return None

def main():
    """Funzione principale del client"""
    print("=" * 60)
    print("AVVIO CLIENT TCP (Con Autenticazione)")
    print("=" * 60)
    
    log_filename = setup_xml_log()
    print(f"Log XML: {log_filename}")
    
    log_to_xml(log_filename, "INFO", "CLIENT_START",
               "Client TCP avviato")
    
    # Connessione al server
    mio_socket = connetti_al_server(log_filename)
    if not mio_socket:
        print("\nERRORE: Impossibile connettersi al server!")
        print("Verifica che il server sia in esecuzione su porta 12345")
        sys.exit(1)
    
    mio_socket.settimeout(None)
    
    print(f"\n{Colori.BOLD}=== AUTENTICAZIONE ==={Colori.RESET}")
    
    # AUTENTICAZIONE
    username = autenticazione(mio_socket, log_filename)
    
    if not username:
        print(f"\n{Colori.ROSSO}Autenticazione fallita. Chiusura client.{Colori.RESET}")
        mio_socket.close()
        sys.exit(1)
    
    print(f"\n{Colori.VERDE}✓ Sei connesso come: {Colori.BLU}{username}{Colori.RESET}")
    
    # Mostra menu
    mostra_menu()
    
    try:
        while True:
            print("\n" + "-" * 50)
            messaggio = input(f"[{Colori.BLU}{username}{Colori.RESET}] Comando (HELP per aiuto): ").strip()
            
            if messaggio.upper() == "HELP":
                mostra_menu()
                continue
            
            if not messaggio:
                print("Inserisci un comando valido!")
                continue
            
            try:
                mio_socket.send(messaggio.encode('utf-8'))
                statistiche['messaggi_inviati'] += 1
                
                log_to_xml(log_filename, "INFO", "SEND",
                          f"Inviato comando: {messaggio}",
                          command=messaggio,
                          username=username)
                
                cmd = messaggio.upper()
                if cmd == "TIME":
                    statistiche['comandi_time'] += 1
                elif cmd == "NAME":
                    statistiche['comandi_name'] += 1
                
            except Exception as e:
                log_to_xml(log_filename, "ERROR", "SEND_ERROR",
                          f"Errore invio messaggio: {e}",
                          command=messaggio,
                          username=username)
                statistiche['errori'] += 1
                break

            try:
                data = mio_socket.recv(1024).decode('utf-8', errors='ignore')
                
                if not data:
                    log_to_xml(log_filename, "WARNING", "SERVER_DISCONNECTED",
                              "Server ha chiuso la connessione",
                              username=username)
                    print("\nServer disconnesso")
                    break
                
                statistiche['messaggi_ricevuti'] += 1
                
                log_to_xml(log_filename, "INFO", "RECEIVE",
                          f"Ricevuta risposta dal server",
                          response=data,
                          username=username)
                
                print(f"\n{Colori.VERDE}Server:{Colori.RESET} {data}")
                
            except Exception as e:
                log_to_xml(log_filename, "ERROR", "RECEIVE_ERROR",
                          f"Errore ricezione risposta: {e}",
                          username=username)
                statistiche['errori'] += 1
                break
            
            if messaggio.upper() == "EXIT":
                log_to_xml(log_filename, "INFO", "EXIT",
                          "Comando EXIT inviato - Chiusura client",
                          username=username)
                print("\nDisconnessione in corso...")
                break

    except KeyboardInterrupt:
        log_to_xml(log_filename, "INFO", "USER_INTERRUPT",
                   "Client chiuso da utente (CTRL+C)",
                   username=username)
        print("\nInterruzione utente")
    except Exception as e:
        log_to_xml(log_filename, "ERROR", "UNEXPECTED_ERROR",
                   f"Errore imprevisto: {e}",
                   username=username,
                   exception_type=type(e).__name__)
        statistiche['errori'] += 1
    finally:
        try:
            mio_socket.close()
            log_to_xml(log_filename, "INFO", "DISCONNECTION",
                      "Socket chiuso correttamente",
                      username=username)
        except:
            pass
        
        aggiungi_statistiche_finali(log_filename, username)
        mostra_statistiche()
        print("\nConnessione chiusa dal client")

if __name__ == "__main__":
    main()