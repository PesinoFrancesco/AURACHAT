import socket
from datetime import datetime
import os
import sys
import time
import platform
from colorama import Fore, Style, init

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

SECRET_TOKEN = "AURACHAT"  # PAROLA CHIAVE IDENTIFICATORE DISCOVERY
DISCOVERY_PORT = 9999
DISCOVERY_TIMEOUT = 5  # Secondi da aspettare per risposte


def mostra_menu():
    """Mostra menu comandi disponibili"""
    print("\n" + "=" * 50)
    print("COMANDI DISPONIBILI:")
    print("=" * 50)
    print("  TIME   → Richiedi ora corrente del server")
    print("  NAME   → Richiedi hostname del server")
    print("  INFO [type] → Richiedi informazioni specifiche")
    print("                1: Client collegati al server")
    print("                2: Utenti nel database")
    print("                3: Info rete del server")
    print("                4: Info rete del client")
    print("                5: Lista utenti per chat")
    print("  EXIT   → Disconnetti e chiudi client")
    print("  HELP   → Mostra questo menu")
    print("=" * 50)


def autenticazione(mio_socket):
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
                print(f"{Colori.ROSSO}✗ {msg_text}{Colori.RESET}")
                
            # REG_RETRY - Riprova registrazione
            elif msg_type == "REG_RETRY":
                print(f"{Colori.GIALLO}✗ {msg_text}{Colori.RESET}")
                
            # AUTH_SUCCESS - Login riuscito
            elif msg_type == "AUTH_SUCCESS":
                print(f"{Colori.VERDE}✓ {msg_text}{Colori.RESET}")
                # Estrai username dal messaggio
                username = msg_text.split("Benvenuto ")[1].rstrip("!")
                return username
                
            # REG_SUCCESS - Registrazione riuscita
            elif msg_type == "REG_SUCCESS":
                print(f"{Colori.VERDE}✓ {msg_text}{Colori.RESET}")
                username = msg_text.split("Benvenuto ")[1].rstrip("!")
                return username
                
            # AUTH_FAIL / REG_FAIL - Fallimento
            elif msg_type in ["AUTH_FAIL", "REG_FAIL"]:
                print(f"{Colori.ROSSO}✗ {msg_text}{Colori.RESET}")
                return None
                
    except Exception as e:
        print(f"{Colori.ROSSO}Errore durante autenticazione: {e}{Colori.RESET}")
        return None


def discover_server():
    """
    Cerca il server sulla rete locale usando UDP broadcast
    Restituisce: (IP, porta) del server se trovato, None altrimenti
    """
    print(f"\n{Colori.CIANO}🔍 Ricerca server sulla rete locale...{Colori.RESET}")
    
    # Crea socket UDP
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        # Abilita modalità BROADCAST (permette di inviare a tutti)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Imposta timeout per le risposte
        udp_socket.settimeout(1.0)
        
        # Prepara il messaggio di discovery
        messaggio = f"DISCOVER|{SECRET_TOKEN}"
        
        server_trovato = None
        fine_ricerca = time.time() + DISCOVERY_TIMEOUT
        tentativi = 0
        
        # Continua a cercare fino al timeout
        while time.time() < fine_ricerca:
            try:
                tentativi += 1
                print(f"  Tentativo {tentativi}...", end='\r')
                
                # Invia broadcast a tutta la rete sulla porta 9999
                udp_socket.sendto(messaggio.encode('utf-8'), ('<broadcast>', DISCOVERY_PORT))
                
                # Aspetta risposta (max 1 secondo)
                try:
                    data, server_addr = udp_socket.recvfrom(1024)
                    risposta = data.decode('utf-8', errors='ignore').strip()
                    
                    # Analizza la risposta: FOUND|TOKEN|HOSTNAME|PORTA
                    parti = risposta.split('|')
                    
                    # Verifica che la risposta sia valida
                    if len(parti) == 4 and parti[0] == "FOUND" and parti[1] == SECRET_TOKEN:
                        server_ip = server_addr[0]
                        server_hostname = parti[2]
                        server_porta = int(parti[3])
                        
                        print(f"\n{Colori.VERDE}✓ Server trovato!{Colori.RESET}")
                        print(f"   IP: {Colori.BLU}{server_ip}{Colori.RESET}")
                        print(f"   Hostname: {Colori.BLU}{server_hostname}{Colori.RESET}")
                        print(f"   Porta: {Colori.BLU}{server_porta}{Colori.RESET}")
                        
                        server_trovato = (server_ip, server_porta)
                        break
                    else:
                        # Risposta con token errato - ignora
                        print(f"\n{Colori.GRIGIO}⚠ Risposta ignorata da {server_addr[0]} (token non valido){Colori.RESET}")
                        
                except socket.timeout:
                    # Nessuna risposta in questo secondo, riprova
                    time.sleep(0.5)
                    continue
                    
            except Exception as e:
                print(f"\n{Colori.ROSSO}Errore durante discovery: {e}{Colori.RESET}")
                time.sleep(0.5)
                continue
        
        # Fine ricerca
        if not server_trovato:
            print(f"\n{Colori.ROSSO}✗ Nessun server trovato dopo {DISCOVERY_TIMEOUT} secondi{Colori.RESET}")
            print(f"   {Colori.GIALLO}Verifica che:{Colori.RESET}")
            print(f"   - Il server sia avviato")
            print(f"   - Sia sulla stessa rete")
            print(f"   - Il firewall permetta UDP porta {DISCOVERY_PORT}")
        
        return server_trovato
        
    except Exception as e:
        print(f"\n{Colori.ROSSO}Errore fatale durante discovery: {e}{Colori.RESET}")
        return None
    finally:
        udp_socket.close()


def connetti_al_server(host="127.0.0.1", porta=12345, tentativi=3):
    """Tenta di connettersi al server con retry automatico"""
    for tentativo in range(1, tentativi + 1):
        try:
            print(f"{Colori.CIANO}Tentativo {tentativo}/{tentativi} di connessione a {host}:{porta}...{Colori.RESET}")
            
            mio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            mio_socket.settimeout(5)
            mio_socket.connect((host, porta))
            
            print(f"{Colori.VERDE}✓ Connesso al server {host}:{porta}{Colori.RESET}")
            return mio_socket
            
        except socket.timeout:
            print(f"{Colori.ROSSO}✗ Timeout connessione (tentativo {tentativo}/{tentativi}){Colori.RESET}")
        except ConnectionRefusedError:
            print(f"{Colori.ROSSO}✗ Server non raggiungibile su {host}:{porta} (tentativo {tentativo}/{tentativi}){Colori.RESET}")
        except Exception as e:
            print(f"{Colori.ROSSO}✗ Errore connessione: {e} (tentativo {tentativo}/{tentativi}){Colori.RESET}")
        
        if tentativo < tentativi:
            print(f"{Colori.GIALLO}Riprovo tra 2 secondi...{Colori.RESET}")
            time.sleep(2)
    
    print(f"{Colori.ROSSO}✗ Impossibile connettersi al server dopo tutti i tentativi{Colori.RESET}")
    return None


def get_info_client(mio_socket):
    """Restituisce informazioni di rete del client in formato semplice"""
    hostname = socket.gethostname()
    try:
        ip_address = socket.gethostbyname(hostname)
    except:
        ip_address = "N/A"
    try:
        local_addr = mio_socket.getsockname()
        remote_addr = mio_socket.getpeername()
        local_port = local_addr[1]
        server_ip = remote_addr[0]
        server_port = remote_addr[1]
    except:
        local_port = "N/A"
        server_ip = "N/A"
        server_port = "N/A"
    sistema = platform.system()
    versione = platform.version()
    info = (
        f"CLIENT INFO:\n"
        f"  Hostname: {hostname}\n"
        f"  IP Locale: {ip_address}\n"
        f"  Porta Locale: {local_port}\n"
        f"  Server IP: {server_ip}\n"
        f"  Server Porta: {server_port}\n"
        f"  Sistema: {sistema}\n"
        f"  Versione: {versione[:40]}"
    )
    return info


def main():
    """Funzione principale del client"""
    print("=" * 60)
    print("AVVIO CLIENT TCP (Con Autenticazione + Discovery)")
    print("=" * 60)
    print(f"Token Discovery: {SECRET_TOKEN}")
    
    # DISCOVERY: Cerca il server sulla rete
    server_info = discover_server()
    
    if not server_info:
        print(f"\n{Colori.ROSSO}ERRORE: Impossibile trovare il server!{Colori.RESET}")
        
        # Opzione fallback: chiedi IP manualmente
        print(f"\n{Colori.GIALLO}Vuoi inserire l'IP manualmente? (SI/NO): {Colori.RESET}", end='')
        scelta = input().strip().upper()
        
        if scelta == "SI":
            ip_manuale = input(f"{Colori.CIANO}Inserisci IP server: {Colori.RESET}").strip()
            porta_manuale = input(f"{Colori.CIANO}Inserisci porta (default 12345): {Colori.RESET}").strip()
            porta_manuale = int(porta_manuale) if porta_manuale else 12345
            server_info = (ip_manuale, porta_manuale)
        else:
            sys.exit(1)
    
    server_ip, server_porta = server_info
    
    # Connessione al server
    mio_socket = connetti_al_server(host=server_ip, porta=server_porta)
    if not mio_socket:
        print("\nERRORE: Impossibile connettersi al server!")
        print("Verifica che il server sia in esecuzione su porta 12345")
        sys.exit(1)
    
    mio_socket.settimeout(None)
    
    print(f"\n{Colori.BOLD}=== AUTENTICAZIONE ==={Colori.RESET}")
    
    # AUTENTICAZIONE
    username = autenticazione(mio_socket)
    
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

            if messaggio.upper() == "LOG":
                # Invia il comando LOG al server
                try:
                    mio_socket.send(messaggio.encode('utf-8'))
                except Exception as e:
                    print(f"{Colori.ROSSO}✗ Errore invio comando LOG: {e}{Colori.RESET}")
                    continue
                
                try:
                    # Ricevi il contenuto del log in un'unica volta
                    data = mio_socket.recv(65536).decode('utf-8', errors='ignore').strip()
                    
                    if data.startswith("LOG_ERROR|"):
                        errore = data.split('|', 1)[1]
                        print(f"{Colori.ROSSO}✗ Errore: {errore}{Colori.RESET}")
                    else:
                        # Salva il contenuto del log
                        print(f"\n{Colori.CIANO}{'='*60}")
                        print(f"LOG DEL SERVER RICEVUTO")
                        print(f"{'='*60}{Colori.RESET}")
                        
                        log_file = "file_log.xml"
                        with open(log_file, "w", encoding='utf-8') as f:
                            f.write(data)
                        
                        print(f"{Colori.VERDE}✓ Log salvato in: {log_file} ({len(data)} bytes){Colori.RESET}")
                        print(f"{Colori.CIANO}{'='*60}{Colori.RESET}\n")
                
                except Exception as e:
                    print(f"{Colori.ROSSO}✗ Errore durante ricezione log: {e}{Colori.RESET}")
                continue
            
            try:
                mio_socket.send(messaggio.encode('utf-8'))
            except Exception as e:
                print(f"{Colori.ROSSO}✗ Errore invio messaggio: {e}{Colori.RESET}")
                break

            try:
                data = mio_socket.recv(1024).decode('utf-8', errors='ignore')
                
                if not data:
                    print("\nServer disconnesso")
                    break
                
                # Gestione speciale per INFO 4 (info rete del client)
                if data == "CLIENT_HANDLE_INFO_4":
                    info_client = get_info_client(mio_socket)
                    print(f"\n{info_client}")
                else:
                    # Stampa risposta server senza grafiche
                    print(f"\n{Colori.VERDE}Server:{Colori.RESET} {data.replace(chr(9552),'-').replace(chr(9553),'|').replace(chr(9556),'').replace(chr(9559),'').replace(chr(9562),'').replace(chr(9565),'')}")
                
            except Exception as e:
                print(f"{Colori.ROSSO}✗ Errore ricezione risposta: {e}{Colori.RESET}")
                break
            
            if messaggio.upper() == "EXIT":
                print("\nDisconnessione in corso...")
                break

    except KeyboardInterrupt:
        print("\n\nInterruzione utente (CTRL+C)")
    except Exception as e:
        print(f"{Colori.ROSSO}Errore imprevisto: {e}{Colori.RESET}")
    finally:
        try:
            mio_socket.close()
        except:
            pass
        print("\nConnessione chiusa dal client")


if __name__ == "__main__":
    main()
