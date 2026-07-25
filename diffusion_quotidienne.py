"""
Diffusion quotidienne AGRO-PREDICT : SMS + appel vocal (IVR).

A executer une fois par jour (cron sur un serveur, ou tache planifiee
Colab / Google Cloud Scheduler). Pour chaque producteur enregistre dans
producteurs.csv :
  1. recupere sa situation (secheresse, phyto, NDVI, vaccination) via
     les memes fonctions que le tableau de bord web,
  2. construit un message court (SMS) et un message vocal (IVR),
  3. les envoie via Africa's Talking.

Pourquoi Africa's Talking plutot que Twilio : c'est l'operateur le plus
utilise pour le SMS et la voix en Afrique centrale et de l'Ouest, avec
une tarification locale et une compatibilite eprouvee avec les reseaux
camerounais (Orange, MTN). Twilio fonctionne aussi mais coute nettement
plus cher pour un numero camerounais.

MODE_TEST = False (par defaut) : rien n'est reellement envoye, tout est
juste affiche a l'ecran. A ne passer sur False qu'apres avoir verifie
le contenu des messages et configure de vrais identifiants API.
"""

import os
import csv
import time
from datetime import datetime

from generer_message import generer_messages_producteur

# ⚠️ Ne jamais ecrire les vraies cles ici en dur : les lire depuis des
# variables d'environnement (sur Colab : utiliser userdata.get(...)).
AT_USERNAME = os.environ.get("AT_USERNAME", "sandbox")
AT_API_KEY = os.environ.get("AT_API_KEY", "")

MODE_TEST = False
FICHIER_PRODUCTEURS = "producteurs.csv"

# Les memes fonctions d'acces aux donnees que dans app.py (copiees ici a
# l'identique pour ne pas dupliquer la logique metier de calcul).
import requests
import numpy as np


def get_precip_recente(lat, lon, jours=10):
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&daily=precipitation_sum&past_days={jours}&forecast_days=1&timezone=Africa%2FLagos")
        d = requests.get(url, timeout=10).json().get("daily", {})
        vals = d.get("precipitation_sum", [])[:jours]
        return float(np.nansum(vals)) if vals else None
    except Exception:
        return None


def get_risque_phyto_jours(lat, lon):
    try:
        import pandas as pd
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&hourly=temperature_2m,relative_humidity_2m&forecast_days=5&timezone=Africa%2FLagos")
        d = requests.get(url, timeout=10).json().get("hourly", {})
        if not d:
            return 0
        dfh = pd.DataFrame(d)
        dfh['time'] = pd.to_datetime(dfh['time'])
        dfh['jour'] = dfh['time'].dt.date
        agg = dfh.groupby('jour').agg(hr_moy=('relative_humidity_2m', 'mean'),
                                       t_moy=('temperature_2m', 'mean')).reset_index()
        jours_risque = agg[(agg['hr_moy'] > 80) & (agg['t_moy'] >= 25) & (agg['t_moy'] <= 30)]
        return len(jours_risque)
    except Exception:
        return 0


def envoyer_sms(numero, texte):
    if MODE_TEST:
        print(f"  [TEST] SMS -> {numero} : {texte}")
        return True
    import africastalking
    africastalking.initialize(AT_USERNAME, AT_API_KEY)
    sms = africastalking.SMS
    try:
        reponse = sms.send(texte, [numero])
        print(f"  SMS envoye a {numero} : {reponse}")
        return True
    except Exception as e:
        print(f"  ECHEC SMS a {numero} : {e}")
        return False


def envoyer_appel_vocal(numero, texte):
    """
    L'API Voice d'Africa's Talking fonctionne par callback : on declenche
    l'appel, et quand le producteur decroche, leur serveur interroge une
    URL que Christian doit heberger (meme un petit serveur Flask suffit),
    qui repond avec le texte a lire en syntaxe XML "Say". Ici, on montre
    le declenchement de l'appel ; le serveur de callback est a part
    (voir callback_ivr.py).
    """
    if MODE_TEST:
        print(f"  [TEST] APPEL VOCAL -> {numero} : {texte}")
        return True
    import africastalking
    africastalking.initialize(AT_USERNAME, AT_API_KEY)
    voice = africastalking.Voice
    try:
        reponse = voice.call("+237XXXXXXXXX", [numero])
        print(f"  Appel declenche vers {numero} : {reponse}")
        return True
    except Exception as e:
        print(f"  ECHEC appel vers {numero} : {e}")
        return False


def executer_diffusion():
    mois_courant = datetime.now().month
    print(f"=== Diffusion AGRO-PREDICT du {datetime.now().strftime('%d/%m/%Y')} "
          f"(mode {'TEST' if MODE_TEST else 'REEL'}) ===\n")

    with open(FICHIER_PRODUCTEURS, newline='', encoding='utf-8') as f:
        producteurs = list(csv.DictReader(f))

    for profil in producteurs:
        lat, lon = float(profil['lat']), float(profil['lon'])
        print(f"- {profil['prenom']} {profil['nom']} ({profil['type_u']}, {profil.get('culture') or 'pas de culture renseignee'})")

        precip_10j = get_precip_recente(lat, lon)
        nb_jours_phyto = get_risque_phyto_jours(lat, lon)
        alerte_ndvi = "Normal"  # a brancher sur load_alertes_ndvi() si un point NDVI existe pour cette position

        try:
            sms, vocal, avertissement = generer_messages_producteur(profil, precip_10j, nb_jours_phyto, alerte_ndvi, mois_courant)
        except ValueError as e:
            print(f"  IGNORE : {e}")
            continue

        if avertissement:
            print(f"  ATTENTION : {avertissement}")

        envoyer_sms(profil['telephone'], sms)
        envoyer_appel_vocal(profil['telephone'], vocal)
        time.sleep(0.5)  # eviter de saturer l'API en cas de gros volume
        print()

    print("=== Diffusion terminee ===")


if __name__ == '__main__':
    executer_diffusion()
