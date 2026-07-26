"""
Serveur de callback pour l'appel vocal (IVR).

Quand diffusion_quotidienne.py declenche un appel via voice.call(...),
Africa's Talking appelle le producteur, et des que celui-ci decroche,
leurs serveurs envoient une requete POST a l'URL que Christian aura
configuree dans son tableau de bord Africa's Talking (rubrique Voice ->
Callback URL). Ce petit serveur repond avec le texte a lire a voix
haute, dans un format XML propre a Africa's Talking (balise <Say>).

A deployer quelque part d'accessible publiquement (Render, Railway,
PythonAnywhere ou un petit VPS suffisent ; pas besoin d'un gros serveur).
Ne PAS heberger ca sur Colab : Colab n'a pas d'adresse publique stable.
"""

from flask import Flask, request, Response
import json

app = Flask(__name__)

# Le texte a lire pour chaque numero est prepare a l'avance par
# diffusion_quotidienne.py et stocke ici (fichier partage ou petite base
# de donnees). Pour ce prototype, un simple fichier JSON suffit.
FICHIER_MESSAGES_EN_ATTENTE = "messages_vocaux_en_attente.json"


def lire_message_pour(numero):
    try:
        with open(FICHIER_MESSAGES_EN_ATTENTE, encoding='utf-8') as f:
            messages = json.load(f)
        return messages.get(numero, "Bonjour. Ici Agro Prédict. Aucun message disponible pour le moment.")
    except FileNotFoundError:
        return "Bonjour. Ici Agro Prédict. Aucun message disponible pour le moment."


@app.route("/callback_ivr", methods=["POST"])
def callback_ivr():
    numero_appelant = request.form.get("callerNumber", "")
    texte = lire_message_pour(numero_appelant)

    reponse_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="woman" playBeep="false">{texte}</Say>
</Response>"""

    return Response(reponse_xml, mimetype="text/xml")


"""
Serveur de callback pour l'appel vocal (IVR).

Quand diffusion_quotidienne.py declenche un appel via voice.call(...),
Africa's Talking appelle le producteur, et des que celui-ci decroche,
leurs serveurs envoient une requete POST a l'URL que Christian aura
configuree dans son tableau de bord Africa's Talking (rubrique Voice ->
Callback URL). Ce petit serveur repond avec le texte a lire a voix
haute, dans un format XML propre a Africa's Talking (balise <Say>).

A deployer quelque part d'accessible publiquement (Render, Railway,
PythonAnywhere ou un petit VPS suffisent ; pas besoin d'un gros serveur).
Ne PAS heberger ca sur Colab : Colab n'a pas d'adresse publique stable.
"""

from flask import Flask, request, Response
import json

app = Flask(__name__)

# Le texte a lire pour chaque numero est prepare a l'avance par
# diffusion_quotidienne.py et stocke ici (fichier partage ou petite base
# de donnees). Pour ce prototype, un simple fichier JSON suffit.
FICHIER_MESSAGES_EN_ATTENTE = "messages_vocaux_en_attente.json"


def lire_message_pour(numero):
    try:
        with open(FICHIER_MESSAGES_EN_ATTENTE, encoding='utf-8') as f:
            messages = json.load(f)
        return messages.get(numero, "Bonjour. Ici Agro Prédict. Aucun message disponible pour le moment.")
    except FileNotFoundError:
        return "Bonjour. Ici Agro Prédict. Aucun message disponible pour le moment."


@app.route("/callback_ivr", methods=["POST"])
def callback_ivr():
    numero_appelant = request.form.get("callerNumber", "")
    texte = lire_message_pour(numero_appelant)

    reponse_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="woman" playBeep="false">{texte}</Say>
</Response>"""

    return Response(reponse_xml, mimetype="text/xml")


if __name__ == '__main__':
    # Render (et la plupart des hebergeurs) assignent eux-memes le port a
    # ecouter via la variable d'environnement PORT, et exigent un service
    # accessible sur 0.0.0.0 (toutes les interfaces), pas seulement
    # 127.0.0.1 (localhost, invisible depuis l'exterieur du conteneur).
    # En local sur ton PC, PORT n'existe pas, donc ca retombe sur 5000.
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
