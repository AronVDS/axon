# Axon Orchestrator

De centrale AI-hersenen van Axon. Ontvang een taak in het Nederlands, beslis met llama3 welk agent ingezet wordt, en geef een samenvatting terug.

## Structuur

```
AI-Agents/
├── orchestrator.py          ← startpunt
├── requirements.txt
├── agents/
│   ├── lead_generator.py    ← zoekt bedrijven + genereert/verstuurt emails
│   ├── email_manager.py     ← emails lezen en beantwoorden (stub)
│   ├── task_manager.py      ← taken beheren (stub)
│   └── document_agent.py    ← documenten aanmaken (stub)
└── AILeadGenerator/         ← bestaande lead gen modules
    ├── maps_client.py
    ├── email_generator.py
    ├── gmail_client.py
    └── leads_manager.py
```

## Vereisten

- Python 3.10+
- [Ollama](https://ollama.com) geïnstalleerd en actief met het llama3 model

## Setup

### 1. Ollama installeren

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows: download installer op https://ollama.com/download
```

```bash
# llama3 model downloaden (eenmalig, ~4 GB)
ollama pull llama3

# controleer of Ollama actief is
ollama serve
```

### 2. Python-omgeving

```bash
# vanuit de AI-Agents/ map
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Omgevingsvariabelen (optioneel, alleen voor live emails)

Maak een `.env` bestand aan in `AI-Agents/AILeadGenerator/`:

```env
SENDER_EMAIL=jouw.email@gmail.com
```

Zie `AILeadGenerator/README.md` voor de volledige Gmail OAuth-setup.

## Gebruik

Voer het uit vanuit de `AI-Agents/` map:

```bash
python orchestrator.py "Vind 10 leads in Gent en stuur ze een email"
```

### Voorbeeldtaken

```bash
# Lead generatie (dry-run, geen echte emails)
python orchestrator.py "Zoek 5 marketingbureaus in Antwerpen"

# Lead generatie met limiet
python orchestrator.py "Vind 20 accountantskantoren in Brussel"

# Email beheer (stub — nog niet geïmplementeerd)
python orchestrator.py "Lees mijn ongelezen emails"

# Takenbeheer (stub — nog niet geïmplementeerd)
python orchestrator.py "Voeg een taak toe: offerte versturen naar klant X"

# Documenten (stub — nog niet geïmplementeerd)
python orchestrator.py "Maak een offerte aan voor een websiteproject"
```

## Hoe het werkt

```
Gebruiker
   │  "Vind 10 leads in Gent"
   ▼
orchestrator.py
   │  stuurt taak naar llama3
   ▼
llama3 (Ollama)
   │  geeft terug: { "agent": "lead_generator", "parameters": { ... } }
   ▼
agents/lead_generator.py
   │  roept AILeadGenerator modules aan
   ▼
Resultaat → geprint naar terminal
```

## Beschikbare agents

| Agent            | Status        | Functie                                      |
|------------------|---------------|----------------------------------------------|
| lead_generator   | Actief        | Zoekt bedrijven via OSM + genereert emails   |
| email_manager    | Stub          | Emails lezen en beantwoorden via Gmail API   |
| task_manager     | Stub          | Taken beheren in Notion of lokale database   |
| document_agent   | Stub          | Offertes, rapporten en verslagen aanmaken    |

## Uitbreiden

Voeg een nieuw agent toe in drie stappen:

1. Maak `agents/mijn_agent.py` aan met een `MijnAgent` klasse en een `run(params: dict) -> str` methode.
2. Importeer en registreer de klasse in `orchestrator.py` in de `AGENTS` dict.
3. Voeg een beschrijving toe aan `_SYSTEM_PROMPT` in `orchestrator.py` zodat llama3 weet wanneer het agent ingezet moet worden.
