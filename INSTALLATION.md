# GitHub Setup für Entwickler

## 1. Repository erstellen auf GitHub

1. Gehe zu https://github.com/new
2. Name: `heishamon-homeassistant-lutarym`
3. Description: "Home Assistant Integration for Panasonic Aquarea Heat Pumps via Heishamon (HTTP API)"
4. Public
5. "Add .gitignore" → skip (haben wir bereits)
6. "Choose a license" → MIT
7. Create Repository

## 2. Lokal hochladen

```bash
cd heishamon-homeassistant-lutarym

git init
git add .
git commit -m "Initial commit - v0.1.0"
git branch -M main
git remote add origin https://github.com/Lutarym/heishamon-homeassistant-lutarym.git
git push -u origin main
```

## 3. Tags für Releases

```bash
git tag -a v0.1.0 -m "Initial release"
git push origin v0.1.0
```

## 4. Releases auf GitHub erstellen

1. Gehe zu https://github.com/Lutarym/heishamon-homeassistant-lutarym/releases
2. Klick "Draft a new release"
3. Tag: v0.1.0
4. Title: "Heishamon by Lutarym v0.1.0"
5. Description:
```
# Heishamon by Lutarym v0.1.0

Initial release featuring:
- Full support for all 143 Heishamon MQTT topics
- Direct HTTP API access (no MQTT broker required)
- Flexible modes: Listening-Only or Full Control
- Multi-language support (DE, EN, FR, NL, IT)
- Native Home Assistant entities

## Installation

1. Download the `heishamon_lutarym.zip` below
2. Extract to `~/.homeassistant/custom_components/`
3. Restart Home Assistant
4. Add integration in Einstellungen > Geräte und Dienste

## Features

- Sensors for all 143 topics
- Number entities for temperature/settings control
- Switches for on/off control
- Select entities for mode selection
- Climate integration for zone control
```
6. Upload ZIP file (nächster Schritt)
7. "Publish release"

## 5. ZIP für Download vorbereiten

Die ZIP wird im nächsten Schritt erstellt und hochgeladen.
