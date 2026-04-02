# Password Generation Policy

## Scope
Questo documento descrive come il progetto genera e verifica le password utente nel backend Python.

## Metodo crittografico
Le password non sono mai salvate in chiaro.
Per ogni utente vengono salvati:
- password_hash
- password_salt

Il valore hash viene generato con scrypt.

Formula logica:
- secret_input = password_in_chiaro + pepper
- hash = scrypt(secret_input, salt, N, r, p, dklen)

## Parametri attuali (profilo primario)
I parametri sono configurati in backend/config.py e possono essere sovrascritti via variabili ambiente.

- PASSWORD_HASH_N (default: 16384)
- PASSWORD_HASH_R (default: 8)
- PASSWORD_HASH_P (default: 1)
- PASSWORD_HASH_DKLEN (default: 64)
- PASSWORD_PEPPER (default: stringa vuota)

## Salt
Per ogni password viene generato un salt casuale di 16 byte.

- formato salvato: hex
- lunghezza attesa in DB: 32 caratteri

## Hash
L output di scrypt viene salvato in formato hex.

- lunghezza attesa in DB con dklen=64: 128 caratteri

## Verifica password
In login e change password, il backend:
1. Legge password_hash e password_salt dal DB.
2. Ricalcola scrypt con i parametri correnti.
3. Confronta il risultato con l hash salvato.

Per compatibilita di migrazione sono supportati fallback opzionali:
- Profilo legacy con parametri dedicati (PASSWORD_LEGACY_N/R/P/DKLEN), se valorizzati.
- Fallback senza pepper quando PASSWORD_PEPPER e valorizzata, per non bloccare utenti creati in ambienti senza pepper.

## Parametri legacy opzionali
Se necessari, si possono valorizzare:
- PASSWORD_LEGACY_N
- PASSWORD_LEGACY_R
- PASSWORD_LEGACY_P
- PASSWORD_LEGACY_DKLEN

Se lasciati a 0, il profilo legacy viene ignorato.

## Note su JWT e password
JWT non cambia il metodo di hashing password.
JWT riguarda la sessione/autenticazione del token, non la derivazione dell hash password.

## Reset massivo password
Per aggiornare tutte le password usando il prefisso email (parte prima di @):

- script: backend/scripts/reset_passwords_from_email_prefix.py
- dry-run: python scripts/reset_passwords_from_email_prefix.py
- apply: python scripts/reset_passwords_from_email_prefix.py --apply

Lo script usa esattamente i parametri correnti del backend (incluso eventuale pepper).

## Riferimenti nel codice
- backend/services/auth_service.py
- backend/config.py
- backend/scripts/reset_passwords_from_email_prefix.py
