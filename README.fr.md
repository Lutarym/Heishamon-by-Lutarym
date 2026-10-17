# Heishamon by Lutarym

[English](README.md) · [Deutsch](README.de.md) · **Français** · [日本語](README.ja.md)

Intégration Home Assistant pour les pompes à chaleur Panasonic Aquarea via HeishaMon, sans MQTT, directement par l'interface HTTP.

Version 1.3.1

## Ce que fait l'intégration

Elle lit `http://<ip>/json` et crée un capteur pour chacun des 144 topics HeishaMon. Si la carte les fournit, elle ajoute les valeurs de puissance précises (XTOP), les valeurs de la carte optionnelle (OPT), les sondes de température 1-Wire et les compteurs S0. Les commandes d'écriture passent par `http://<ip>/command?Commande=Valeur`.

Tous les noms de topics, commandes, plages de valeurs et codages proviennent du code source et de la documentation du micrologiciel HeishaMon (`decode.h`, `commands.h`, `commands.cpp`, `MQTT-Topics.md`, `OptionalPCB.md` dans [heishamon/HeishaMon](https://github.com/heishamon/HeishaMon)), ils ne sont pas devinés.

## Prérequis

- Home Assistant 2024.11.0 ou plus récent
- Carte HeishaMon accessible sur le réseau

## Installation

### Manuelle

1. Copier le dossier `custom_components/heishamon_lutarym` dans `<config>/custom_components/`
2. Redémarrer Home Assistant
3. Paramètres, Appareils et services, Ajouter une intégration, "Heishamon by Lutarym"

### HACS

Ajouter le projet comme dépôt personnalisé (Custom Repository) avec la catégorie **Integration**, puis l'installer et redémarrer Home Assistant.

## Configuration

| Champ | Signification |
|---|---|
| Adresse IP | adresse de la carte HeishaMon |
| Nom d'utilisateur, mot de passe | seulement si définis sur le HeishaMon |
| Intervalle | intervalle en secondes, défaut 5, plage 1 à 300 |
| Lecture seule | activé : capteurs uniquement. Désactivé : commandes en plus |
| Lissage des valeurs | atténue les sauts des températures en nombres entiers |
| Répétitions requises | combien de fois une nouvelle valeur doit être confirmée, 2 à 20 |
| Compteur électrique externe | facultatif, capteur de puissance pour la pompe à chaleur seule, par exemple un Shelly |

L'intervalle, le mode de commande, le lissage et le compteur électrique peuvent être modifiés ensuite via "Configurer". L'adresse, le nom d'utilisateur et le mot de passe via "Reconfigurer". Si l'adresse change, l'appareil, les entités et l'historique sont conservés.

## Entités

Un appareil, contenant :

| Type | Nombre | Quand |
|---|---|---|
| Capteurs TOP0 à TOP143 | 144 | toujours |
| Capteurs XTOP0 à XTOP5 (puissances précises) | 6 | si la pompe à chaleur les envoie (série K/L et plus récentes) |
| Capteurs OPT0 à OPT6 | 7 | si l'émulation de la carte optionnelle est activée dans HeishaMon |
| Sondes de température 1-Wire | une par sonde | si 1-Wire est activé dans HeishaMon |
| Compteurs S0, puissance et index | deux par port | si S0 est activé dans HeishaMon |
| COP chauffage, COP eau chaude | 2 | toujours |
| Sélection Source du COP | 1 | avec un compteur électrique externe, aussi en lecture seule |
| Valeurs réglables (Number) | 36 | seulement avec commande |
| Interrupteurs | 17 | seulement avec commande |
| Listes de sélection | 11 | seulement avec commande |
| Bouton "Réinitialiser le défaut" | 1 | seulement avec commande |
| Carte optionnelle : 8 valeurs, 2 interrupteurs, 3 sélections | 13 | seulement avec commande et émulation active |

XTOP, OPT, 1-Wire et S0 sont détectés au chargement de l'intégration. S'ils sont ajoutés plus tard, recharger l'intégration.

Les noms affichés suivent la langue de Home Assistant. Sont disponibles l'allemand, l'anglais, le français et le japonais. Si la langue n'en fait pas partie, l'anglais est utilisé. L'ID d'entité contient l'adresse de la carte et le numéro TOP et reste indépendant de la langue, les automatisations ne cassent donc pas lors d'un changement de langue.

Exemple pour le topic TOP5 à l'adresse 192.168.1.50 (`sensor.heishamon_192_168_1_50_top5`) :

| Langue | Nom affiché |
|---|---|
| Allemand | TOP5 Rücklauftemperatur |
| Anglais | TOP5 Return water temperature |
| Français | TOP5 Température retour d'eau |
| Japonais | TOP5 戻り水温度 |

Les noms sont volontairement formulés pour être compréhensibles plutôt que traduits mot à mot. `Ipm_Temp` devient par exemple "Température électronique de puissance", `Sterilization_State` devient "Stérilisation en cours".

La description en clair fournie par HeishaMon est disponible dans l'attribut `beschreibung` de chaque entité.

### COP

Le chauffage et l'eau chaude sont calculés séparément. Le COP est l'énergie thermique divisée par l'énergie électrique du cycle en cours, quelle que soit sa durée. Un cycle commence au démarrage du compresseur et se termine lorsque le compresseur s'arrête ou que la vanne trois voies (TOP20) change de mode. L'état est ensuite "inconnu". Le dégivrage fait partie du cycle, car il consomme de l'électricité et retire de la chaleur à l'eau. Le refroidissement n'est pas pris en compte.

L'énergie est additionnée à chaque interrogation, comme puissance multipliée par le temps écoulé depuis l'interrogation précédente.

La sélection Source du COP détermine l'origine de la valeur affichée. Le changement est immédiat, les deux calculs tournent toujours en arrière-plan. Le choix est conservé après un redémarrage.

| Source du COP | Énergie thermique | Énergie électrique |
|---|---|---|
| Pompe à chaleur | selon la pompe à chaleur | selon la pompe à chaleur |
| Mesuré (compteur électrique) | débit volumique × masse volumique × capacité thermique × (départ − retour) | compteur électrique externe |

La masse volumique et la capacité thermique de l'eau sont tirées de tables à la température moyenne de l'eau. Avec du glycol dans le circuit, le COP mesuré n'est donc pas correct.

Les appareils de la série K/L et plus récents transmettent des valeurs de puissance précises (XTOP0 à XTOP5), qui sont alors utilisées. Les appareils plus anciens ne transmettent la puissance que par paliers de 200 W, le COP selon la pompe à chaleur y est donc approximatif. L'attribut `werte` indique les valeurs utilisées (XTOP ou TOP).

Le compteur électrique doit mesurer uniquement la pompe à chaleur et indiquer la puissance en W, kW, mW ou MW.

Si le COP dépasse la limite de Carnot (maximum théorique issu des températures de départ et extérieure), il est physiquement impossible et s'affiche comme "inconnu".

Attributs du capteur : `quelle`, `waermemenge_kwh`, `strommenge_kwh`, `laufzeit_min`.

## Commande

Important : la carte HeishaMon répond "OK" à chaque commande, même si elle rejette une valeur. L'intégration vérifie donc chaque valeur avant l'envoi et affiche une erreur dans l'interface si elle est hors de la plage valide. Si la carte n'est pas joignable, une erreur s'affiche également.

### Valeurs réglables

| Topic | Commande | Plage |
|---|---|---|
| TOP9 | SetDHWTemp | 40 à 75 °C |
| TOP27, TOP34 | SetZ1/Z2HeatRequestTemperature | voir zones |
| TOP28, TOP35 | SetZ1/Z2CoolRequestTemperature | voir zones |
| TOP77 | SetHeatingOffOutdoorTemp | 5 à 35 °C |
| TOP78 | SetHeaterOnOutdoorTemp | -15 à 20 °C |
| TOP95 | SetMaxPumpDuty | 64 à 254 |
| TOP23 | SetFloorHeatDelta | 1 à 15 K |
| TOP24 | SetFloorCoolDelta | 1 à 15 K |
| TOP22 | SetDHWHeatDelta | -12 à -2 K |
| TOP113 | SetBufferDelta | 0 à 10 K |
| TOP131 | SetBivalentStartTemp | -15 à 35 °C |
| TOP134 | SetBivalentAPStartTemp | -15 à 35 °C |
| TOP135 | SetBivalentAPStopTemp | -15 à 35 °C |
| TOP70 | SetSterilizationTemp | 55 à 75 °C |
| TOP71 | SetSterilizationMaxTime | 5 à 60 min par pas de 5 |
| TOP96 | SetHeaterDelayTime (série J seulement) | 0 à 254 min * |
| TOP97 | SetHeaterStartDelta (série J seulement) | -127 à 127 K * |
| TOP98 | SetHeaterStopDelta (série J seulement) | -127 à 127 K * |
| TOP29 à TOP32, TOP72 à TOP75, TOP82 à TOP89 | SetCurves (courbes de chauffage et de refroidissement, zones 1 et 2) | -127 à 127 °C * |

\* La documentation HeishaMon n'indique aucune plage. Les limites sont celles du codage dans le micrologiciel. Les valeurs acceptées par la pompe à chaleur ne sont pas connues.

Chaque point de courbe est envoyé séparément. La petite carte HeishaMon (ESP8266) ne traite que 128 octets par requête, la courbe entière n'y tient pas.

### Zones

Selon la documentation HeishaMon, la plage valide dépend du fonctionnement de la zone, sur courbe de chauffe ou en température directe. La pompe à chaleur l'indique dans TOP76 (chauffage) et TOP81 (refroidissement). Le réglage adapte sa plage en conséquence.

| | Courbe (décalage) | Température directe |
|---|---|---|
| Chauffage | -5 à 5 | 20 à 75 °C |
| Refroidissement | -5 à 5 | 5 à 20 °C |

Pour le chauffage direct, la documentation indique "20 au maximum". 75 °C est la consigne d'eau la plus haute documentée par HeishaMon. Le maximum réel dépend du modèle.

Selon la documentation HeishaMon, en mode thermostat ou sonde, la température directe ne se règle pas avec ces valeurs, mais avec le point haut de la courbe de chauffe.

### Listes de sélection

| Commande | Options |
|---|---|
| SetOperationMode | Chauffage, refroidissement, auto, eau chaude, chauffage + eau chaude, refroidissement + eau chaude, auto + eau chaude |
| SetQuietMode | Arrêt, niveau 1 à 3 |
| SetPowerfulMode | Arrêt, 30, 60, 90 minutes |
| SetZones | Zone 1, zone 2, les deux |
| SetExternalPadHeater | Désactivé, type A, type B |
| SetBivalentMode | Alternatif, parallèle, parallèle avancé |
| SetHeatingControl | Confort, efficacité |
| SetSmartDHW | Variable, standard |
| SetQuietModePriority | Bruit, capacité |
| SetPumpFlowrateMode | Delta T, débit maximal |
| SetDHWSensorSelection | Haut, milieu (série K/L All-in-One seulement) |

La pompe à chaleur indique aussi les modes "Auto (froid)" et "Auto (froid) + eau chaude". Ils sont affichés comme auto et auto + eau chaude.

### Interrupteurs et bouton

17 interrupteurs, dont marche/arrêt de la pompe à chaleur, eau chaude forcée, dégivrage forcé, lancement de la stérilisation, chauffage de secours, mode vacances, programmation, ballon tampon, commandes externes, régulation bivalente et les résistances d'appoint pour le chauffage et l'eau chaude.

Le bouton "Réinitialiser le défaut" acquitte une erreur en cours de la pompe à chaleur (par exemple H72), comme la touche de réinitialisation de la télécommande.

### Carte optionnelle

Seulement si l'émulation de la carte optionnelle est activée dans HeishaMon. Selon la documentation HeishaMon, elle est expérimentale, et la pompe à chaleur passe en veille avec l'erreur H74 si la carte cesse d'émettre pendant environ 40 secondes. Lire d'abord [OptionalPCB.md](https://github.com/heishamon/HeishaMon/blob/master/OptionalPCB.md).

| Commande | Type |
|---|---|
| SetSmartGridMode | Sélection : normal, capacité 1, pompe à chaleur et eau chaude arrêtées, capacité 2 |
| SetExternalThermostat1State, SetExternalThermostat2State | Sélection : aucune demande, refroidissement, chauffage, les deux |
| SetHeatCoolMode, SetCompressorState | Interrupteur |
| SetDemandControl | Valeur 43 à 234 (selon la documentation 5 % à 100 %) |
| SetPoolTemp, SetBufferTemp, SetZ1RoomTemp, SetZ1WaterTemp, SetZ2RoomTemp, SetZ2WaterTemp, SetSolarTemp | Température -78 à 120 °C |

La carte ne renvoie pas ces valeurs. La dernière valeur réglée est affichée et conservée après un redémarrage. `SetOptPCBByte9` n'est pas intégré, la documentation ne décrit pas sa signification.

## Limitations connues

- Les zones sont représentées par Number et Select, il n'y a pas d'entité Climate.
- La section OpenTherm de la carte n'est pas exploitée.
- Les plages de valeurs proviennent de la documentation HeishaMon et peuvent varier selon le modèle de pompe à chaleur.
- Les commandes de la carte optionnelle et la correspondance SmartGrid suivent la documentation HeishaMon mais n'ont pas été testées sur une pompe à chaleur.
- Les traductions française et japonaise n'ont pas été vérifiées par des locuteurs natifs.

## Licence

MIT, 2026 Lutarym
