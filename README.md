# STP BOM Generator

Dieses Projekt stellt ein kleines Python-Werkzeug bereit, das aus einer STEP/STP-Datei eine Stückliste (Bill of Materials, BOM) ermittelt. Die App analysiert die Baugruppenstruktur über `NEXT_ASSEMBLY_USAGE_OCCURRENCE`-Beziehungen und zählt alle Komponenten rekursiv.

## Installation

```
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Verwendung

Eine Tabelle wird standardmäßig auf der Konsole ausgegeben:

```
stp-bom path/zur/datei.stp
```

Optionen:


- `--root`: Identifiziert das gewünschte Top-Level-Produkt (Part-Nummer, Name oder `#ID`). Wird weggelassen, versucht das Tool automatisch das Wurzelprodukt zu finden.
- `--format {table,csv,json}`: Ausgabeformat (Standard: `table`).
- `--output <pfad>`: Speichert die Stückliste in eine Datei statt auf der Konsole.
- `--include-assemblies`: Berücksichtigt auch Zwischenbaugruppen in der Stückliste.

## Tests

```
pip install -e .[test]
pytest
```

## Einschränkungen

- Der Parser unterstützt hauptsächlich Baugruppenbeziehungen über `NEXT_ASSEMBLY_USAGE_OCCURRENCE`.
- Mengen werden durch die Anzahl der Vorkommen berechnet; explizite Mengenangaben innerhalb der STEP-Datei werden derzeit nicht ausgewertet.

## Beispiel

Eine kleine Beispielbaugruppe befindet sich unter `examples/simple_assembly.stp`.
Führen Sie `stp-bom examples/simple_assembly.stp` aus, um eine Beispiel-Stückliste zu erzeugen.
