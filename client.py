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
    
    # Se il file non esiste, crea la struttura base
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
    """
    Scrive un'entry nel file XML di log
    
    Args:
        log_filename: percorso file XML
        level: INFO, WARNING, ERROR
        log_type: CONNECTION, SEND, RECEIVE, ERROR, etc.
        message: messaggio principale
        **extra_data: dati aggiuntivi da includere
    """
    try:
        # Leggi il file XML esistente
        tree = ET.parse(log_filename)
        root = tree.getroot()
        
        # Trova l'ultima sessione
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
            msg_colored = message.replace(str(client_name), client_name_colored)
        else:
            msg_colored = message
        # Stampa anche su console (solo per log importanti)
        if log_type in ["CONNECTION", "ERROR", "DISCONNECTION"]:
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

def aggiungi_statistiche_finali(log_filename):
    """Aggiunge le statistiche finali nel file XML"""
    try:
        tree = ET.parse(log_filename)
        root = tree.getroot()
        
        sessions = root.findall("session")
        if sessions:
            current_session = sessions[-1]
            current_session.set("end_time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # Aggiungi statistiche finali
            stats_elem = ET.SubElement(current_session, "final_statistics")
            for key, value in statistiche.items():
                stat = ET.SubElement(stats_elem, key.replace('_', '-'))
                stat.text = str(value)
            
            ET.indent(tree, space="  ")
            tree.write(log_filename, encoding='utf-8', xml_declaration=True)
    except Exception as e:
        print(f"❌ Errore scrittura statistiche finali: {e}")

def connetti_al_server(log_filename, host="127.0.0.1", porta=12345, tentativi=3):
    """
    Tenta di connettersi al server con retry automatico
    Restituisce: (socket connesso o None, nome_client o None)
    """
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
            
            # Ricevi il nome identificativo dal server subito dopo la connessione
            try:
                client_name = mio_socket.recv(128).decode('utf-8').strip()
            except Exception:
                client_name = None
            
            log_to_xml(log_filename, "INFO", "CONNECTION",
                      f"Connesso al server {host}:{porta}",
                      server_host=host,
                      server_port=porta,
                      client_name=client_name)
            
            return mio_socket, client_name
            
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
                      exception_type=type(e).__name__,
                      exception_message=str(e))
        
        if tentativo < tentativi:
            print(f"Riprovo tra 2 secondi...")
            time.sleep(2)
    
    log_to_xml(log_filename, "ERROR", "CONNECTION_FAILED",
               "Impossibile connettersi al server dopo tutti i tentativi",
               total_attempts=tentativi)
    return None, None

def main():
    """Funzione principale del client"""
    print("=" * 60)
    print("AVVIO CLIENT TCP (Log XML)")
    print("=" * 60)
    
    # Setup log XML
    log_filename = setup_xml_log()
    print(f"Log XML: {log_filename}")
    
    log_to_xml(log_filename, "INFO", "CLIENT_START",
               "Client TCP avviato")
    
    # Connessione al server con retry
    mio_socket, client_name = connetti_al_server(log_filename)
    if not mio_socket:
        print("\nERRORE: Impossibile connettersi al server!")
        print("Verifica che il server sia in esecuzione su porta 12345")
        log_to_xml(log_filename, "ERROR", "STARTUP_FAILED",
                   "Avvio client fallito: impossibile connettersi")
        sys.exit(1)
    
    # Rimuovi timeout dopo connessione
    mio_socket.settimeout(None)
    
    # Mostra menu iniziale
    mostra_menu()
    
    try:
        while True:
            # Input utente
            print("\n" + "-" * 50)
            messaggio = input(f"[{client_name}] Inserisci comando (HELP per aiuto): ").strip()
            
            # Comando locale HELP
            if messaggio.upper() == "HELP":
                mostra_menu()
                continue
            
            # Valida input vuoto
            if not messaggio:
                print("Inserisci un comando valido!")
                continue
            
            # Invia messaggio al server
            try:
                mio_socket.send(messaggio.encode('utf-8'))
                statistiche['messaggi_inviati'] += 1
                
                log_to_xml(log_filename, "INFO", "SEND",
                          f"Inviato comando: {messaggio}",
                          command=messaggio,
                          client_name=client_name)
                
                # Incrementa contatore comandi specifici
                cmd = messaggio.upper()
                if cmd == "TIME":
                    statistiche['comandi_time'] += 1
                elif cmd == "NAME":
                    statistiche['comandi_name'] += 1
                
            except Exception as e:
                log_to_xml(log_filename, "ERROR", "SEND_ERROR",
                          f"Errore invio messaggio: {e}",
                          command=messaggio,
                          client_name=client_name,
                          exception_type=type(e).__name__)
                statistiche['errori'] += 1
                break

            # Ricezione risposta
            try:
                data = mio_socket.recv(1024).decode('utf-8', errors='ignore')
                
                if not data:
                    log_to_xml(log_filename, "WARNING", "SERVER_DISCONNECTED",
                              "Server ha chiuso la connessione",
                              client_name=client_name)
                    print("\nServer disconnesso")
                    break
                
                statistiche['messaggi_ricevuti'] += 1
                
                log_to_xml(log_filename, "INFO", "RECEIVE",
                          f"Ricevuta risposta dal server",
                          response=data,
                          client_name=client_name)
                
                print(f"\nRisposta server: {data}")
                
            except Exception as e:
                log_to_xml(log_filename, "ERROR", "RECEIVE_ERROR",
                          f"Errore ricezione risposta: {e}",
                          client_name=client_name,
                          exception_type=type(e).__name__)
                statistiche['errori'] += 1
                break
            
            # Gestione comando EXIT
            if messaggio.upper() == "EXIT":
                log_to_xml(log_filename, "INFO", "EXIT",
                          "Comando EXIT inviato - Chiusura client",
                          client_name=client_name)
                print("\nDisconnessione in corso...")
                break

    except KeyboardInterrupt:
        log_to_xml(log_filename, "INFO", "USER_INTERRUPT",
                   "Client chiuso da utente (CTRL+C)",
                   client_name=client_name)
        print("\nInterruzione utente")
    except Exception as e:
        log_to_xml(log_filename, "ERROR", "UNEXPECTED_ERROR",
                   f"Errore imprevisto: {e}",
                   client_name=client_name,
                   exception_type=type(e).__name__,
                   exception_message=str(e))
        statistiche['errori'] += 1
    finally:
        # Chiusura connessione
        try:
            mio_socket.close()
            log_to_xml(log_filename, "INFO", "DISCONNECTION",
                      "Socket chiuso correttamente",
                      client_name=client_name)
        except:
            pass
        
        # Salva statistiche finali
        aggiungi_statistiche_finali(log_filename)
        
        # Mostra statistiche
        mostra_statistiche()
        print("\nConnessione chiusa dal client")

if __name__ == "__main__":
    main()