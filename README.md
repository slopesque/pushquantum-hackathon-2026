# PushQuantum × Qoro Hackathon 2026

Optimisation de QUBO partitionnés avec [Divi](https://github.com/QoroQuantum/divi) sur deux problèmes
du benchmark [QOBLIB](https://github.com/ZIB-AOPT/QOBLIB) : optimisation de portefeuille (06) et
network design (08).

## Setup

```bash
uv sync                    # Python 3.12 + dépendances (dev incluses)
cp .env.example .env       # puis y mettre sa QORO_API_KEY (https://dash.qoroquantum.net)
uv run pytest              # smoke test : l'arbitre reproduit les références QOBLIB
uv run marimo edit notebooks/   # ou : uv run jupyter lab
```

Sans clé API, tout tourne sur le simulateur local (Maestro).

Contexte du hackathon, structure du repo, conventions : voir [`AGENTS.md`](AGENTS.md).
Kit original de Qoro (notebooks + arbitre) : [`references/`](references/README.md).

## Résultats

| Problème | Instance | Variables | Qubits max | Score | Best known | Gap | Run |
|---|---|---|---|---|---|---|---|
| | | | | | | | |
