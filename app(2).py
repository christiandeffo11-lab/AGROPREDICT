
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import requests
import os
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Anthropic & Folium handling
try:
    import anthropic
    ANTHROPIC_OK = True
except ImportError:
    ANTHROPIC_OK = False

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_OK = True
except ImportError:
    FOLIUM_OK = False

try:
    from streamlit_js_eval import get_geolocation
    GEOLOC_OK = True
except ImportError:
    GEOLOC_OK = False

# --- CONFIG GLOBALE ---
st.set_page_config(page_title="AGRO-PREDICT V2", page_icon="🌾", layout="wide")
DOSSIER = os.path.dirname(os.path.abspath(__file__))
MOIS_FR = ["","Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
MOIS_NOM = ["","Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]

# --- LANGUES DE L'INTERFACE ---
# Français et anglais : traductions completes et fiables.
# Fulfulde, Arabe Choa, Kotoko : brouillons a valider avec des locuteurs natifs
# (mémoire, chap. 5 et discussion — recommandation OMM/WMO 2019 de co-production
# linguistique) avant tout déploiement réel. L'Arabe Choa est ici rendu en arabe
# standard (compréhensible par la plupart des locuteurs de ce dialecte régional),
# pas dans la variante dialectale exacte. Le Kotoko n'a pas pu être traduit de
# façon fiable ici : le français reste affiché en repli en attendant validation.
LANGUES_DISPO = ["Français", "English", "Fulfulde", "Arabe Choa", "Kotoko"]

TRADUCTIONS = {
    "onglet_meteo":       {"Français": "🌡️ Météo", "English": "🌡️ Weather", "Arabe Choa": "🌡️ الطقس"},
    "onglet_agriculture": {"Français": "🌱 Agriculture", "English": "🌱 Farming", "Fulfulde": "🌱 Ndema", "Arabe Choa": "🌱 الزراعة"},
    "onglet_elevage":     {"Français": "🐄 Élevage", "English": "🐄 Livestock", "Fulfulde": "🐄 Na'i", "Arabe Choa": "🐄 الثروة الحيوانية"},
    "onglet_sanitaire":   {"Français": "🦠 Sanitaire & Carte", "English": "🦠 Health & Map", "Arabe Choa": "🦠 الصحة والخريطة"},
    "conditions_actuelles": {"Français": "Conditions actuelles", "English": "Current conditions", "Arabe Choa": "الأحوال الحالية"},
    "prevision_j7":         {"Français": "Prévision à court terme (J+1 à J+7)", "English": "Short-term forecast (Day 1 to Day 7)", "Arabe Choa": "توقعات قصيرة المدى"},
    "tendance_saisonniere": {"Français": "Tendance mensuelle / saisonnière (modèle Prophet)", "English": "Monthly / seasonal trend (Prophet model)", "Arabe Choa": "الاتجاه الشهري والموسمي"},
    "risque_secheresse":    {"Français": "Risque sécheresse (10 derniers jours)", "English": "Drought risk (last 10 days)", "Arabe Choa": "خطر الجفاف"},
    "vigilance_ndvi":       {"Français": "Vigilance NDVI (dernière détection disponible)", "English": "NDVI vigilance (latest detection available)", "Arabe Choa": "مراقبة صحة النبات"},
    "agents_pathogenes":    {"Français": "Agents pathogènes à surveiller sur votre parcelle", "English": "Pathogens to monitor on your plot", "Arabe Choa": "الآفات الواجب مراقبتها"},
    "superficie":           {"Français": "Superficie de la parcelle (ha)", "English": "Plot size (ha)", "Arabe Choa": "مساحة الحقل (هكتار)"},
    "calendrier_vaccinal":  {"Français": "Calendrier vaccinal saisonnier", "English": "Seasonal vaccination calendar", "Fulfulde": "Kalenndeer lekki na'i", "Arabe Choa": "التقويم التلقيحي الموسمي"},
    "recommandation_deplacement": {"Français": "Recommandation de déplacement", "English": "Movement recommendation", "Arabe Choa": "توصية بالتنقل"},
    "risque_phyto":         {"Français": "Risque phytosanitaire (prévision 5 jours)", "English": "Plant health risk (5-day forecast)", "Arabe Choa": "خطر صحة النبات"},
    "carte":                {"Français": "Carte", "English": "Map", "Fulfulde": "Karte", "Arabe Choa": "الخريطة"},
    "culture":              {"Français": "Culture", "English": "Crop", "Arabe Choa": "المحصول"},
    "localisation":         {"Français": "📍 Localisation", "English": "📍 Location", "Arabe Choa": "📍 الموقع"},
}

def T(cle):
    # Traduit une clé selon la langue choisie ; repli automatique sur le français
    # si la traduction n'est pas encore disponible pour cette langue (Kotoko
    # notamment, en attente de validation par un locuteur natif).
    lang = st.session_state.get('langue', 'Français')
    entree = TRADUCTIONS.get(cle, {})
    return entree.get(lang) or entree.get('Français', cle)

# --- DATABASES ---
CULTURES = {
    "Sorgho": {"semis":[6,7], "duree":120, "eau":"Modérée", "pluie_min":300, "pluie_opt":500, "pathogenes":["Mildiou","Charbon du sorgho","Striga","Chenilles légionnaires"]},
    "Mil": {"semis":[6,7], "duree":100, "eau":"Faible", "pluie_min":200, "pluie_opt":350, "pathogenes":["Mildiou","Pucerons","Charbon du mil"]},
    "Maïs": {"semis":[5,6,7], "duree":100, "eau":"Élevée", "pluie_min":400, "pluie_opt":700, "pathogenes":["Chenilles légionnaires","Rouille commune","Charbon de l'épi"]},
    "Niébé": {"semis":[6,7,8], "duree":75, "eau":"Faible", "pluie_min":250, "pluie_opt":400, "pathogenes":["Pucerons","Thrips","Rosette arachide"]},
    "Arachide": {"semis":[5,6,7], "duree":100, "eau":"Modérée", "pluie_min":350, "pluie_opt":550, "pathogenes":["Cercosporiose","Rosette arachide","Pucerons"]},
    "Manioc": {"semis":[4,5,6], "duree":365, "eau":"Faible", "pluie_min":600, "pluie_opt":1000, "pathogenes":["Cochenille farineuse","Mosaïque manioc"]},
    "Riz": {"semis":[6,7,8], "duree":130, "eau":"Très élevée", "pluie_min":800, "pluie_opt":1200, "pathogenes":["Pyriculariose","Helminthosporiose","Bactériose"]},
    "Oignon": {"semis":[10,11,12], "duree":90, "eau":"Modérée", "pluie_min":150, "pluie_opt":300, "pathogenes":["Mildiou","Thrips","Pourriture blanche"]},
    "Tomate": {"semis":[10,11], "duree":90, "eau":"Élevée", "pluie_min":400, "pluie_opt":600, "pathogenes":["Fusariose","Alternariose","Virus TYLCV"]},
}

# --- UTILS ---
def proba_semis(culture, mois):
    info = CULTURES[culture]
    semis = info["semis"]
    if mois in semis:
        return {"proba": 90, "statut": "FAVORABLE", "d_semis": datetime.now(), "d_recolte": datetime.now()+timedelta(days=info['duree']), "duree": info['duree']}
    return {"proba": 5, "statut": "DÉFAVORABLE", "d_semis": datetime.now(), "d_recolte": datetime.now()+timedelta(days=info['duree']), "duree": info['duree'], "prochaines": [MOIS_NOM[semis[0]]]}

def get_meteo_api(lat, lon):
    # Conditions actuelles (temperature, humidite, vent, pression, precipitation) - Open-Meteo, gratuit.
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,surface_pressure"
               f"&timezone=Africa%2FLagos")
        return requests.get(url, timeout=10).json().get("current", {})
    except: return {}

def get_prevision_j7(lat, lon):
    # Previsions numeriques J+1 a J+7 (Open-Meteo daily forecast, gratuit, sans cle API).
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max"
               f"&forecast_days=7&timezone=Africa%2FLagos")
        d = requests.get(url, timeout=10).json().get("daily", {})
        return pd.DataFrame(d) if d else pd.DataFrame()
    except:
        return pd.DataFrame()

def get_precip_recente(lat, lon, jours=10):
    # Cumul des precipitations observees sur les X derniers jours (past_days, Open-Meteo).
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&daily=precipitation_sum&past_days={jours}&forecast_days=1&timezone=Africa%2FLagos")
        d = requests.get(url, timeout=10).json().get("daily", {})
        vals = d.get("precipitation_sum", [])[:jours]
        return float(np.nansum(vals)) if vals else None
    except:
        return None

def risque_secheresse(culture, precip_10j_mm):
    # Seuil du memoire (Recommandations, tableau VII) : deficit > 30 % sur 10 jours.
    # Besoin quotidien approxime = pluie_min (cycle complet) / duree du cycle.
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

def get_risque_phyto(lat, lon):
    # Critere phytosanitaire du memoire (Recommandations) : HR > 80% et T 25-30 C, 5 jours.
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&hourly=temperature_2m,relative_humidity_2m&forecast_days=5&timezone=Africa%2FLagos")
        d = requests.get(url, timeout=10).json().get("hourly", {})
        if not d: return None, 0
        dfh = pd.DataFrame(d)
        dfh['time'] = pd.to_datetime(dfh['time'])
        dfh['jour'] = dfh['time'].dt.date
        agg = dfh.groupby('jour').agg(hr_moy=('relative_humidity_2m','mean'), t_moy=('temperature_2m','mean')).reset_index()
        jours_risque = agg[(agg['hr_moy']>80) & (agg['t_moy']>=25) & (agg['t_moy']<=30)]
        return agg, len(jours_risque)
    except:
        return None, 0

def load_previsions_saisonnieres():
    # Charge previsions.csv, genere par la cellule Prophet du notebook (historique ERA5 1975-2025).
    ch = os.path.join(DOSSIER, 'previsions.csv')
    if os.path.exists(ch):
        try:
            return pd.read_csv(ch, index_col=0)
        except:
            return None
    return None

def load_alertes_ndvi():
    # Charge la derniere observation de vigilance sanitaire (detection d'anomalie NDVI, cellule C8).
    ch = os.path.join(DOSSIER, 'ndvi_alertes.csv')
    if os.path.exists(ch):
        try:
            dfa = pd.read_csv(ch)
            dfa['date'] = pd.to_datetime(dfa['date'])
            return dfa.sort_values('date').iloc[-1]
        except:
            return None
    return None

# --- MODULE ÉLEVAGE (calendrier vaccinal + déplacement — mémoire, chap. 5.4) ---
CALENDRIER_VACCINAL = {
    1:  {"action": "Vaccination PPCB",   "priorite": "Haute"},
    4:  {"action": "Déparasitage",       "priorite": "Moyenne"},
    7:  {"action": "Vaccination FMD",    "priorite": "Haute"},
    10: {"action": "Contrôle général",   "priorite": "Normale"},
}

def prochaine_echeance_vaccinale(mois):
    mois_futurs = [m for m in CALENDRIER_VACCINAL if m >= mois]
    m_cible = min(mois_futurs) if mois_futurs else min(CALENDRIER_VACCINAL)
    return m_cible, CALENDRIER_VACCINAL[m_cible]

def recommandation_deplacement(mois):
    # Saison des pluies (juin-septembre) : remontée vers les pâturages du nord.
    # Saison sèche (octobre-mai) : repli vers les zones de décrue au sud.
    if mois in [6, 7, 8, 9]:
        return "Nord", "Pâturages de saison des pluies"
    return "Sud", "Zones de décrue (saison sèche)"

# --- SESSION & IDENTIFICATION ---
if 'auth' not in st.session_state: st.session_state['auth'] = False

if not st.session_state['auth']:
    st.title('👤 Identification AGRO-PREDICT')
    with st.form('login_form'): # Renommé pour éviter le conflit avec la clé 'auth'
        prenom = st.text_input('Prénom')
        nom = st.text_input('Nom')
        type_u = st.radio('Activité', ['🌱 Agriculteur', '🐄 Éleveur', '🔀 Mixte'])
        if st.form_submit_button('Accéder au Tableau de Bord'):
            if prenom and nom:
                st.session_state['auth'] = True
                st.session_state['profil'] = {'prenom': prenom, 'nom': nom, 'type_u': type_u, 'arr': 'Kousseri'}
                st.rerun()
    st.stop()

# --- MAIN INTERFACE ---
P = st.session_state['profil']
st.sidebar.success(f"Connecté : {P['prenom']} {P['nom']}")
mois_n = datetime.now().month

# --- LANGUE DE L'INTERFACE ---
with st.sidebar:
    st.subheader("🌐 Langue / Language")
    langue_choisie = st.selectbox("", LANGUES_DISPO, index=LANGUES_DISPO.index(st.session_state.get('langue', 'Français')), label_visibility="collapsed")
    st.session_state['langue'] = langue_choisie
    if langue_choisie in ["Fulfulde", "Arabe Choa", "Kotoko"]:
        st.caption("🔧 Traduction en brouillon — à valider avec des locuteurs natifs avant déploiement (mémoire, recommandations).")
    if langue_choisie == "Kotoko":
        st.caption("Traduction kotoko pas encore disponible ici : affichage en français en attendant.")

# --- LOCALISATION (automatique via GPS navigateur, avec repli manuel) ---
if 'lat' not in st.session_state:
    st.session_state['lat'] = 12.0754
    st.session_state['lon'] = 15.0314
    st.session_state['loc_source'] = "Position par défaut (centre de Kousseri)"

with st.sidebar:
    st.subheader(T('localisation'))
    if GEOLOC_OK:
        loc = get_geolocation()
        if loc and isinstance(loc, dict) and 'coords' in loc:
            st.session_state['lat'] = loc['coords']['latitude']
            st.session_state['lon'] = loc['coords']['longitude']
            st.session_state['loc_source'] = "Position GPS détectée automatiquement"
    else:
        st.caption("Géolocalisation automatique indisponible (module streamlit-js-eval non chargé).")

    st.caption(st.session_state['loc_source'])
    with st.expander("Corriger la position manuellement"):
        st.session_state['lat'] = st.number_input("Latitude", value=float(st.session_state['lat']), format="%.4f")
        st.session_state['lon'] = st.number_input("Longitude", value=float(st.session_state['lon']), format="%.4f")
        if st.button("Utiliser cette position"):
            st.session_state['loc_source'] = "Position saisie manuellement"
            st.rerun()

LAT, LON = st.session_state['lat'], st.session_state['lon']

t1, t2, t3, t4 = st.tabs([T('onglet_meteo'), T('onglet_agriculture'), T('onglet_elevage'), T('onglet_sanitaire')])

with t1:
    st.subheader(T('conditions_actuelles'))
    meteo = get_meteo_api(LAT, LON)
    if meteo:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Température", f"{meteo.get('temperature_2m','N/A')} °C")
        c2.metric("Humidité", f"{meteo.get('relative_humidity_2m','N/A')} %")
        c3.metric("Vent", f"{meteo.get('wind_speed_10m','N/A')} km/h")
        c4.metric("Pression", f"{meteo.get('surface_pressure','N/A')} hPa")
        st.caption(f"Précipitation (heure en cours) : {meteo.get('precipitation','N/A')} mm — source Open-Meteo.")
    else:
        st.warning("Données temps réel indisponibles (Open-Meteo).")

    st.subheader(T('prevision_j7'))
    df_j7 = get_prevision_j7(LAT, LON)
    if not df_j7.empty:
        df_aff = df_j7.copy()
        df_aff['time'] = pd.to_datetime(df_aff['time']).dt.strftime('%d/%m')
        df_aff = df_aff.rename(columns={
            'time': 'Jour', 'temperature_2m_max': 'T max (°C)', 'temperature_2m_min': 'T min (°C)',
            'precipitation_sum': 'Précip. (mm)', 'wind_speed_10m_max': 'Vent max (km/h)'})
        st.dataframe(df_aff, hide_index=True, use_container_width=True)
        st.caption("Source : API Open-Meteo (prévision numérique gratuite, mise à jour horaire).")
    else:
        st.info("Prévision J+1 à J+7 indisponible pour le moment.")

    st.subheader(T('tendance_saisonniere'))
    df_prev = load_previsions_saisonnieres()
    if df_prev is not None:
        df_aff2 = df_prev.rename(columns={
            'journalier': 'Demain', 'hebdomadaire': 'Semaine',
            'mois_1': 'Mois 1', 'mois_2': 'Mois 2', 'mois_3': 'Mois 3'})
        st.dataframe(df_aff2.round(1), use_container_width=True)
        st.caption("Modèle Prophet entraîné sur l'historique ERA5 1975-2025 (cellule Prophet du notebook). "
                   "Tendance indicative, non substituable à un bulletin saisonnier officiel (DMN).")
    else:
        st.info("Fichier previsions.csv introuvable — exécuter la cellule Prophet du notebook pour le générer.")

with t2:
    if 'Agriculteur' in P['type_u'] or 'Mixte' in P['type_u']:
        cu = st.selectbox(T('culture'), list(CULTURES.keys()))
        res = proba_semis(cu, mois_n)
        st.write(f"Statut semis : **{res['statut']}** ({res['proba']} %)")

        st.subheader(T('risque_secheresse'))
        precip_10j = get_precip_recente(LAT, LON, jours=10)
        statut_sech, deficit = risque_secheresse(cu, precip_10j)
        if deficit is not None:
            st.metric(f"Déficit pluviométrique estimé — {cu}", f"{deficit:.0f} %",
                      help="Seuil d'alerte du mémoire (Recommandations) : déficit > 30 % sur 10 jours")
            msg = f"{statut_sech} — cumul observé {precip_10j:.0f} mm sur 10 jours"
            if statut_sech == "RISQUE ÉLEVÉ": st.error(msg)
            elif statut_sech == "VIGILANCE": st.warning(msg)
            else: st.success(msg)
        else:
            st.info("Données de précipitations récentes indisponibles.")

        st.subheader(T('vigilance_ndvi'))
        alerte_ndvi = load_alertes_ndvi()
        if alerte_ndvi is not None:
            st.write(f"Dernière observation exploitable : {alerte_ndvi['date'].strftime('%d/%m/%Y')}")
            niveau = alerte_ndvi['alerte']
            if 'ALERTE' in niveau: st.error(niveau)
            elif 'VIGILANCE' in niveau or 'ATTENTION' in niveau: st.warning(niveau)
            else: st.success(niveau)
            st.caption("Basé sur la détection d'anomalies spectrales NDVI (cellule C8 du notebook, imagerie Landsat/Sentinel-2). "
                       "Observation la plus récente disponible dans l'historique traité, pas une image en temps réel.")
        else:
            st.info("Aucune détection NDVI disponible — exécuter la cellule d'analyse spectrale (C8) du notebook.")

        st.subheader(T('agents_pathogenes'))
        superficie_ha = st.number_input(T('superficie'), min_value=0.1, value=2.0, step=0.5)
        pathogenes_culture = CULTURES[cu].get('pathogenes', [])
        agg_phyto, nb_jours_risque_cu = get_risque_phyto(LAT, LON)
        if pathogenes_culture:
            liste_path = ", ".join(pathogenes_culture)
            if nb_jours_risque_cu >= 3:
                st.error(f"Conditions climatiques favorables au développement fongique détectées {nb_jours_risque_cu}/5 jours "
                         f"à votre position — surveillance renforcée conseillée sur vos {superficie_ha:.1f} ha de {cu} : {liste_path}")
            elif nb_jours_risque_cu >= 1:
                st.warning(f"Conditions partiellement favorables ({nb_jours_risque_cu}/5 jours) — restez vigilant sur vos "
                           f"{superficie_ha:.1f} ha de {cu} pour : {liste_path}")
            else:
                st.success(f"Conditions actuellement peu favorables. Agents pathogènes recensés pour le {cu} à surveiller "
                           f"malgré tout au fil de la saison : {liste_path}")
            st.caption("Liste des agents pathogènes associés à cette culture (mémoire, Tableau VI). Le niveau de vigilance "
                       "s'appuie sur le critère climatique HR > 80 % / 25-30 °C (prévision 5 jours à votre position), pas sur "
                       "une détection directe du pathogène sur le terrain — une confirmation visuelle ou par un technicien reste nécessaire.")
        else:
            st.info(f"Aucun agent pathogène recensé pour le {cu} dans la base actuelle.")

with t3:
    if 'Éleveur' in P['type_u'] or 'Mixte' in P['type_u']:
        st.subheader(T('calendrier_vaccinal'))
        cal_df = pd.DataFrame([
            {"Mois": MOIS_NOM[m], "Action": v["action"], "Priorité": v["priorite"]}
            for m, v in sorted(CALENDRIER_VACCINAL.items())
        ])
        st.table(cal_df)

        m_cible, info_vacc = prochaine_echeance_vaccinale(mois_n)
        st.info(f"Prochaine échéance : **{info_vacc['action']}** en {MOIS_NOM[m_cible]} (priorité {info_vacc['priorite']})")

        st.subheader(T('recommandation_deplacement'))
        direction, motif = recommandation_deplacement(mois_n)
        st.write(f"Mois courant : {MOIS_NOM[mois_n]}")
        st.success(f"Orientation conseillée : **{direction}** — {motif}")
        st.caption(
            "Calendrier construit sur la base des échanges avec les techniciens de la SPRA-Ksr "
            "(mémoire, chap. 5.4) ; à valider par le MINEPIA avant tout déploiement opérationnel."
        )
    else:
        st.info("Ce module s'adresse aux éleveurs et agro-éleveurs. Sélectionnez ce profil à la connexion pour y accéder.")

with t4:
    st.subheader(T('risque_phyto'))
    agg, nb_jours_risque = get_risque_phyto(LAT, LON)
    if agg is not None and len(agg) > 0:
        agg_aff = agg.rename(columns={'jour': 'Jour', 'hr_moy': 'HR moyenne (%)', 't_moy': 'T moyenne (°C)'})
        st.dataframe(agg_aff.round(1), hide_index=True, use_container_width=True)
        if nb_jours_risque >= 3:
            st.error(f"RISQUE ÉLEVÉ — {nb_jours_risque}/5 jours réunissent les conditions HR > 80 % et 25-30 °C "
                     f"(critère du mémoire, Recommandations, tableau VII)")
        elif nb_jours_risque >= 1:
            st.warning(f"VIGILANCE — {nb_jours_risque}/5 jours réunissent les conditions à risque")
        else:
            st.success("Conditions non réunies sur les 5 prochains jours")
        st.caption("Source : prévisions horaires Open-Meteo, agrégées par jour. Critère indicatif à valider par un phytopathologiste avant tout déploiement opérationnel.")
    else:
        st.info("Prévision phytosanitaire indisponible pour le moment.")

    st.subheader(T('carte'))
    if FOLIUM_OK:
        m = folium.Map(location=[LAT, LON], zoom_start=12)
        folium.Marker([LAT, LON], tooltip="Ma position", icon=folium.Icon(color='green')).add_to(m)
        st_folium(m, height=400, use_container_width=True)
