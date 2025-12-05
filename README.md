# SmartOrder: Repository Codice
### Anno Accademico 2025/2026

---

## 1. Informazioni Generali

- **Progetto:** SmartOrder - Analisi Multimodale per la Creazione Automatica di Ordini
- **Corso:** Ingegneria del Software
- **Corso di Laurea:** Informatica (L-31)
- **Università:** Università degli Studi di Padova
- **Anno Accademico:** 2025/2026
- **Gruppo di Lavoro:** NightPRO
- **Email:** [swe.nightpro@gmail.com](mailto:swe.nightpro@gmail.com)
- **Organizzazione GitHub:** [https://github.com/swenightpro](https://github.com/swenightpro)


## 2. Descrizione del Progetto

SmartOrder è una piattaforma intelligente progettata per automatizzare la ricezione e l'elaborazione di ordini di acquisto provenienti da canali molteplici. L'obiettivo del progetto è trasformare dati non strutturati in ordini cliente completi e normalizzati, pronti per l'inserimento in database aziendali e sistemi ERP.

Il sistema analizza input multimodali provenienti da clienti – attualmente focalizzati su **testo e audio** – estraendo automaticamente le informazioni rilevanti (articoli, quantità, preferenze) e mappandole ai codici prodotto presenti nei cataloghi aziendali. Grazie all'integrazione di tecniche avanzate di intelligenza artificiale e natural language processing (NLP), il sistema riduce drasticamente l'intervento umano nelle fasi ripetitive, migliorando la produttività e permettendo al personale di concentrarsi su attività strategiche.

Per ulteriori dettagli sulla visione del progetto, l'architettura proposta e i requisiti completi, si rimanda alla [documentazione del progetto](https://github.com/swenightpro/Documentazione).


## 3. Architettura del Sistema

Il sistema è progettato come una pipeline modulare articolata nei seguenti layer:

1. **Layer di Raccolta Input**: acquisizione di dati da canali diversi (testo, audio)
2. **Layer di Pre-processing**: normalizzazione e pulizia dei dati raccolti
3. **Layer di Estrazione Feature / Embedding**: trasformazione dei dati in rappresentazioni vettoriali
4. **Fusione Multimodale**: combinazione degli embedding in una rappresentazione integrata
5. **Modulo di Interpretazione Semantica**: mapping su entità del catalogo aziendale
6. **Validazione e Arricchimento Dati**: verifica di integrità, coerenza e completezza
7. **Output e Integrazione Database**: trasformazione in ordini strutturati pronti per sistemi gestionali
8. **Monitoraggio e Feedback**: logging e feedback continuo per il retraining del sistema

Per una visualizzazione completa dell'architettura, consultare la documentazione tecnica del progetto.


## 4. Struttura Organizzativa

Il progetto è articolato su tre repository distinti, ospitati all'interno dell'organizzazione del gruppo:
- [Documentazione](https://github.com/swenightpro/Documentazione)
- [SmartOrder-Poc](https://github.com/swenightpro/SmartOrder-PoC)
- [SmartOrder-MVP](https://github.com/swenightpro/SmartOrder-PoC)


## 5. Componenti del Gruppo

Il gruppo di lavoro NightPRO è composto dai seguenti membri:

| Cognome         | Nome            | Matricola |
| :-------------- | :-------------- | :-------- |
| Biasuzzi        | Davide          | 2111000   |
| Bilato          | Leonardo        | 2071084   |
| Zanella         | Francesco       | 2116442   |
| Romascu         | Mihaela-Mariana | 2079726   |
| Ogniben         | Michele         | 2042325   |
| Perozzo         | Samuele         | 2110989   |
| Ponso           | Giovanni        | 2000558   |


## 6. Contatti e Supporto

Per informazioni, chiarimenti o supporto tecnico relativi al progetto:

- **Referente Aziendale Principale:** Gianluca Carlesso (carlesso@ergon.it)
- **Contatti Organizzativi:** Anna Tieppo (tieppo.a@ergon.it)
- **Email del Gruppo:** swe.nightpro@gmail.com

## 7. Licenza

Informazioni sulla licenza del progetto saranno comunicate in una fase successiva dello sviluppo.

---

