"""
Génère, pour un producteur donné, un message court prêt à être diffusé par
SMS ou par voix (IVR). Réutilise exactement les fonctions déjà présentes
dans app.py (AGRO_PREDICT_V2) : rien de nouveau n'est recalculé, ce module
se contente de traduire les résultats en une phrase courte.

Langues : seul le français est activé ici. L'anglais peut être ajouté de
la même façon. Le fulfulde, l'arabe choa et le kotoko restent des
brouillons non validés (mémoire, chap. 5) : les envoyer tel quel à un vrai
producteur serait risqué, donc ce module refuse de les utiliser tant
qu'ils n'ont pas été validés par un locuteur natif.
"""

from datetime import datetime

# Langues actuellement branchées dans la diffusion. Ne pas confondre
# "disponible" et "validé" : l'arabe choa est ici une approximation en
# arabe standard (même convention que app.py), pas la variante dialectale
# exacte parlée à Kousseri. Ce n'est PAS un blocage : le mémoire (chap. 5)
# recommande une validation par un locuteur natif avant un déploiement de
# masse, donc ce statut doit rester visible dans les journaux/tests tant
# que cette relecture n'a pas eu lieu.
LANGUES_DISPONIBLES = ["Français", "Arabe Choa"]
STATUT_LANGUE = {
    "Français": "validé",
    "Arabe Choa": "brouillon (arabe standard, à valider par un locuteur natif)",
}

# --- Copié depuis app.py, pour rester rigoureusement cohérent avec le
#     tableau de bord web (mêmes seuils, mêmes fonctions). ---

CULTURES = {
    "Sorgho": {"duree": 120, "pluie_min": 300, "nom_ar": "الذرة الرفيعة"},
    "Mil": {"duree": 100, "pluie_min": 200, "nom_ar": "الدخن"},
    "Maïs": {"duree": 100, "pluie_min": 400, "nom_ar": "الذرة الصفراء"},
    "Niébé": {"duree": 75, "pluie_min": 250, "nom_ar": "اللوبيا"},
    "Arachide": {"duree": 100, "pluie_min": 350, "nom_ar": "الفول السوداني"},
    "Manioc": {"duree": 365, "pluie_min": 600, "nom_ar": "المانيوك"},
    "Riz": {"duree": 130, "pluie_min": 800, "nom_ar": "الأرز"},
    "Oignon": {"duree": 90, "pluie_min": 150, "nom_ar": "البصل"},
    "Tomate": {"duree": 90, "pluie_min": 400, "nom_ar": "الطماطم"},
}

CALENDRIER_VACCINAL = {
    1: {"action": "Vaccination PPCB", "priorite": "Haute", "action_ar": "التلقيح ضد مرض PPCB", "priorite_ar": "أولوية عالية"},
    4: {"action": "Déparasitage", "priorite": "Moyenne", "action_ar": "إزالة الطفيليات", "priorite_ar": "أولوية متوسطة"},
    7: {"action": "Vaccination FMD", "priorite": "Haute", "action_ar": "التلقيح ضد الحمى القلاعية", "priorite_ar": "أولوية عالية"},
    10: {"action": "Contrôle général", "priorite": "Normale", "action_ar": "فحص عام", "priorite_ar": "أولوية عادية"},
}

MOIS_NOM = ["", "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def risque_secheresse(culture, precip_10j_mm):
    """Identique à app.py : seuil du mémoire, déficit > 30 % sur 10 jours."""
    info = CULTURES[culture]
    besoin_jour = info['pluie_min'] / info['duree']
    attendu_10j = besoin_jour * 10
    if precip_10j_mm is None or attendu_10j <= 0:
        return "Indéterminé", None
    deficit_pct = max(0.0, (attendu_10j - precip_10j_mm) / attendu_10j * 100)
    if deficit_pct > 30:
        return "RISQUE ÉLEVÉ", deficit_pct
    elif deficit_pct > 15:
        return "VIGILANCE", deficit_pct
    return "Normal", deficit_pct


def prochaine_echeance_vaccinale(mois):
    """Identique à app.py."""
    mois_futurs = [m for m in CALENDRIER_VACCINAL if m >= mois]
    m_cible = min(mois_futurs) if mois_futurs else min(CALENDRIER_VACCINAL)
    return m_cible, CALENDRIER_VACCINAL[m_cible]


def construire_alertes(profil, precip_10j_mm, nb_jours_risque_phyto, alerte_ndvi_texte, mois_courant, langue):
    """
    Construit la liste des alertes actives pour ce producteur, classées par
    priorité décroissante. Ne renvoie QUE ce qui dépasse le seuil de
    vigilance : pas de bruit inutile dans un SMS.
    """
    alertes = []
    culture = profil.get('culture')
    type_u = profil.get('type_u', '')
    fr = (langue == "Français")

    nom_culture = culture
    if not fr and culture in CULTURES:
        nom_culture = CULTURES[culture]["nom_ar"]

    if culture and ('Agriculteur' in type_u or 'Mixte' in type_u):
        statut_sech, deficit = risque_secheresse(culture, precip_10j_mm)
        if statut_sech == "RISQUE ÉLEVÉ":
            if fr:
                alertes.append((1, f"Sécheresse: déficit de {deficit:.0f}% sur {culture} depuis 10 jours"))
            else:
                alertes.append((1, f"الجفاف: نقص بنسبة {deficit:.0f}% في {nom_culture} منذ عشرة أيام"))
        elif statut_sech == "VIGILANCE":
            if fr:
                alertes.append((3, f"Vigilance pluie sur {culture}, déficit {deficit:.0f}%"))
            else:
                alertes.append((3, f"تنبيه بخصوص الأمطار على {nom_culture}, نقص {deficit:.0f}%"))

        if nb_jours_risque_phyto is not None and nb_jours_risque_phyto >= 3:
            if fr:
                alertes.append((2, f"Risque phytosanitaire élevé sur {culture} ({nb_jours_risque_phyto}/5 jours)"))
            else:
                alertes.append((2, f"خطر مرتفع على صحة النبات في {nom_culture} ({nb_jours_risque_phyto}/5 أيام)"))
        elif nb_jours_risque_phyto is not None and nb_jours_risque_phyto >= 1:
            if fr:
                alertes.append((4, f"Vigilance phytosanitaire sur {culture}"))
            else:
                alertes.append((4, f"تنبيه بخصوص صحة النبات في {nom_culture}"))

        if alerte_ndvi_texte and 'ALERTE' in alerte_ndvi_texte.upper():
            if fr:
                alertes.append((1, f"Alerte végétation détectée sur {culture}"))
            else:
                alertes.append((1, f"تم الكشف عن تنبيه نباتي في {nom_culture}"))

    if 'Éleveur' in type_u or 'Mixte' in type_u:
        m_cible, info_vacc = prochaine_echeance_vaccinale(mois_courant)
        if m_cible == mois_courant:
            if fr:
                alertes.append((2, f"{info_vacc['action']} recommandée ce mois-ci (priorité {info_vacc['priorite']})"))
            else:
                alertes.append((2, f"يُنصح بـ {info_vacc['action_ar']} هذا الشهر ({info_vacc['priorite_ar']})"))

    alertes.sort(key=lambda x: x[0])
    return [texte for _, texte in alertes]


def construire_message_sms(profil, alertes, langue):
    """SMS : 160 caractères maximum, donc une seule alerte, la plus urgente."""
    prenom = profil.get('prenom', '')
    if langue == "Français":
        if not alertes:
            return f"AGRO-PREDICT: {prenom}, aucune alerte particulière aujourd'hui. RAS."
        texte = f"AGRO-PREDICT: {prenom}, {alertes[0]}."
    else:
        if not alertes:
            texte = f"أگرو-بريديكت: {prenom}, لا توجد أي تنبيهات خاصة اليوم."
        else:
            texte = f"أگرو-بريديكت: {prenom}, {alertes[0]}."
    if len(texte) > 160:
        texte = texte[:157] + "..."
    return texte


def construire_message_vocal(profil, alertes, langue):
    """
    IVR : message parlé, un peu plus long que le SMS car on a le temps
    d'écouter. Jusqu'à deux alertes maximum pour ne pas surcharger l'appel.
    """
    prenom = profil.get('prenom', '')
    if langue == "Français":
        if not alertes:
            return f"Bonjour {prenom}. Ici Agro Prédict. Aucune alerte particulière aujourd'hui pour votre exploitation."
        phrases = [f"Bonjour {prenom}. Ici Agro Prédict."]
        for a in alertes[:2]:
            phrases.append(a + ".")
        phrases.append("Merci de votre attention.")
        return " ".join(phrases)
    else:
        if not alertes:
            return f"مرحباً {prenom}. هنا أگرو-بريديكت. لا توجد أي تنبيهات خاصة اليوم."
        phrases = [f"مرحباً {prenom}. هنا أگرو-بريديكت."]
        for a in alertes[:2]:
            phrases.append(a + ".")
        phrases.append("شكراً لانتباهكم.")
        return " ".join(phrases)


def generer_messages_producteur(profil, precip_10j_mm, nb_jours_risque_phyto, alerte_ndvi_texte, mois_courant=None):
    """
    Point d'entrée unique : renvoie (sms, texte_vocal, avertissement) pour
    un producteur. avertissement est None si la langue est pleinement
    validée, ou un texte à consigner dans les journaux si c'est un
    brouillon (arabe choa actuellement) : on diffuse quand même, mais on
    garde une trace explicite du niveau de confiance de la traduction.
    """
    langue = profil.get('langue', 'Français')
    if langue not in LANGUES_DISPONIBLES:
        raise ValueError(
            f"Langue '{langue}' non branchée dans la diffusion. "
            f"Langues actuellement disponibles : {LANGUES_DISPONIBLES}"
        )
    avertissement = None
    if STATUT_LANGUE[langue] != "validé":
        avertissement = f"Langue '{langue}' : {STATUT_LANGUE[langue]}"

    mois_courant = mois_courant or datetime.now().month
    alertes = construire_alertes(profil, precip_10j_mm, nb_jours_risque_phyto, alerte_ndvi_texte, mois_courant, langue)
    sms = construire_message_sms(profil, alertes, langue)
    vocal = construire_message_vocal(profil, alertes, langue)
    return sms, vocal, avertissement


if __name__ == '__main__':
    # Petit test autonome, sans appel réseau, pour vérifier le texte produit,
    # en français puis en arabe choa (brouillon).
    for langue in ["Français", "Arabe Choa"]:
        profil_test = {"prenom": "Amadou", "type_u": "Agriculteur", "culture": "Mil", "langue": langue}
        sms, vocal, avertissement = generer_messages_producteur(
            profil_test,
            precip_10j_mm=5.0,       # très sec pour du mil -> devrait déclencher RISQUE ÉLEVÉ
            nb_jours_risque_phyto=1,
            alerte_ndvi_texte="Normal",
            mois_courant=7,
        )
        print(f"--- {langue} ---")
        if avertissement:
            print("  ATTENTION :", avertissement)
        print("  SMS   :", sms)
        print("  Vocal :", vocal)
        print()
