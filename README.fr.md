# Heishamon by Lutarym

[English](README.md) · [Deutsch](README.de.md) · **Français** · [日本語](README.ja.md)

Intégration Home Assistant pour les pompes à chaleur Panasonic Aquarea via HeishaMon, sans MQTT, directement par l'interface HTTP.

Version 1.2.0

## Ce que fait l'intégration

Elle lit `http://<ip>/json` et crée une entité pour chacun des 144 topics HeishaMon. Les commandes d'écriture passent par `http://<ip>/command?Commande=Valeur`.

Tous les noms de topics et toutes les commandes SET proviennent directement du code source du micrologiciel HeishaMon (`decode.h`, `commands.h`), ils ne sont pas devinés.

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
| Compteur électrique externe | facultatif, capteur de puissance pour la pompe à chaleur seule, par exemple un Shelly PM |

L'intervalle, le mode de commande, le lissage et le compteur électrique peuvent être modifiés ensuite via "Configurer", sans recréer l'entrée.

## Entités

Un appareil, contenant :

- 137 capteurs, un par topic, `sensor.heishamon_<adresse>_top0` à `..._top143`
- 7 consignes en Number, seulement si "Lecture seule" est désactivée
- 16 interrupteurs et 4 listes de sélection, également seulement si la commande est activée
- COP chauffage et COP eau chaude, `sensor.heishamon_<adresse>_cop_heating` et `..._cop_dhw`
- Sélection Source du COP, `select.heishamon_<adresse>_cop_source`, seulement avec un compteur électrique externe, aussi en lecture seule

Les noms affichés suivent la langue de Home Assistant. Sont disponibles l'allemand, l'anglais, le français et le japonais. Si la langue n'en fait pas partie, l'anglais est utilisé. L'ID d'entité contient l'adresse de la carte et le numéro TOP et reste indépendant de la langue, les automatisations ne cassent donc pas lors d'un changement de langue. Avec plusieurs cartes HeishaMon, chaque ID reste ainsi unique.

Exemple pour le topic TOP5 à l'adresse 192.168.1.50 (`sensor.heishamon_192_168_1_50_top5`) :

| Langue | Nom affiché |
|---|---|
| Allemand | TOP5 Ruecklauftemperatur |
| Anglais | TOP5 Return water temperature |
| Français | TOP5 Temperature retour d'eau |
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

### Consignes modifiables

| Topic | Commande | Plage |
|---|---|---|
| TOP9 | SetDHWTemp | 40 à 75 |
| TOP27 | SetZ1HeatRequestTemperature | -5 à 50 |
| TOP28 | SetZ1CoolRequestTemperature | -5 à 20 |
| TOP34 | SetZ2HeatRequestTemperature | -5 à 50 |
| TOP35 | SetZ2CoolRequestTemperature | -5 à 20 |
| TOP77 | SetHeatingOffOutdoorTemp | 5 à 35 |
| TOP78 | SetHeaterOnOutdoorTemp | -15 à 20 |

## Limitations connues

- Les zones sont représentées par Number et Select, il n'y a pas d'entité Climate.
- Les sections `1wire` et `s0` sont lues, mais aucune entité fixe n'est définie pour elles.
- Les plages des consignes proviennent de la documentation HeishaMon et peuvent varier selon le modèle de pompe à chaleur.
- Les traductions française et japonaise n'ont pas été vérifiées par des locuteurs natifs.

## Licence

MIT, 2026 Lutarym
