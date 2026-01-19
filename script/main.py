# Main Script

import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import pandas as pd
import database_connection as db
import math 

# Berechnet eine gebogene Linie auf der Kart
def get_geodesic_path(start, end, n=100):
    lat1, lon1 = math.radians(start[0]), math.radians(start[1])
    lat2, lon2 = math.radians(end[0]), math.radians(end[1])
    d = 2 * math.asin(math.sqrt(math.sin((lat2 - lat1) / 2) ** 2 +
                                math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2))
    if d == 0: return [start, end]
    path = []
    for i in range(n + 1):
        f = i / n
        a = math.sin((1 - f) * d) / math.sin(d)
        b = math.sin(f * d) / math.sin(d)
        x = a * math.cos(lat1) * math.cos(lon1) + b * math.cos(lat2) * math.cos(lon2)
        y = a * math.cos(lat1) * math.sin(lon1) + b * math.cos(lat2) * math.sin(lon2)
        z = a * math.sin(lat1) + b * math.sin(lat2)
        lat = math.atan2(z, math.sqrt(x**2 + y**2))
        lon = math.atan2(y, x)
        path.append([math.degrees(lat), math.degrees(lon)])
    return path

# Berechnet die Punkte basierend auf der Distanz zum tatsächlichen Standort
def calculate_score(distance_km):
    limit_km = 1000.0
    max_points = 10.0
    if distance_km >= limit_km:
        return 0
    points = (1 - (distance_km / limit_km)) * max_points
    return int(round(points))

# --- SPIELZUSTAND MANAGEMENT ---

def reset_game():
    st.session_state.total_score = 0
    st.session_state.round = 1
    st.session_state.game_started = False
    st.session_state.turn_over = False
    st.session_state.last_click = None
    st.session_state.current_round_score = 0
    st.session_state.score_saved = False
    st.session_state.rounds_per_game = 5
    st.session_state.location_list = []
    st.session_state.current_dist = 0

def start_game():
    st.session_state.game_started = True

    # Bestimmt den Tabellennamen in der Datenbank
    mode = st.session_state.game_mode
    match mode:
        case "Städte": table_name = "cities"
        case "Länder": table_name = "countries"
        case "Berge": table_name = "berge"
        case "Gebäude": table_name = "gebaeude"
        case _:
            st.error("Unbekannter Spielmodus!")
            return

    # Mapping für Schwierigkeit
    diff_map = {"Leicht": "easy", "Mittel": "medium", "Schwer": "hard"}
    db_diff = diff_map[st.session_state.difficulty_selection]

    # Fragt Daten (Städte, Länder, Gebäude, etc) aus der Datenbnak ab
    try:
        st.session_state.location_list = db.fetch_random_locations(
            table_name, 
            st.session_state.rounds_per_game,
            db_diff
        )

        if not st.session_state.location_list:
            st.error("Keine Daten gefunden! Prüfe die Datenbank oder Kategorie.")

    except Exception as e:
        st.error(f"Datenbankfehler: {e}")
        st.session_state.location_list = []

def next_round():
    st.session_state.round += 1
    st.session_state.turn_over = False
    st.session_state.last_click = None
    st.session_state.current_dist = 0

def set_player_name():
    input_value = st.session_state.player_input_key
    if input_value.strip():
        st.session_state.player_name = input_value.strip()

    st.session_state.player_id = db.log_in(st.session_state.player_name)


# App Start

st.set_page_config(page_title="City Guesser", layout="wide")

if 'player_name' not in st.session_state:
    st.session_state.player_name = ""
    st.session_state.player_id = None

if 'total_score' not in st.session_state:
    reset_game()

if 'score_saved' not in st.session_state:
    st.session_state.score_saved = False

if 'current_dist' not in st.session_state:
    st.session_state.current_dist = 0


# Seitenleiste
with st.sidebar:
    # Prüft und handelt Anmeldung
    if st.session_state.player_name:
        st.subheader(f"👤 Angemeldet als: **{st.session_state.player_name}**")
    else:
        st.subheader("👤 Nicht angemeldet.")

    if not st.session_state.game_started:
        st.text_input(
            label = "Name eingeben oder ändern", 
            max_chars = 20,
            key = "player_input_key", 
            value = st.session_state.player_name if st.session_state.player_name else ""
        )

        st.button(
            "Name speichern", 
            on_click=set_player_name,
            type="secondary"
        )

    # Anzeige der aktuellen Runde und des Punktstand 
    if st.session_state.game_started:
        st.header("Aktuelles Spiel")
        display_round = min(st.session_state.round, st.session_state.rounds_per_game)
        st.subheader(f"Runde {display_round} / {st.session_state.rounds_per_game}")
        st.progress(min(st.session_state.round / st.session_state.rounds_per_game, 1.0))
        st.metric("Gesamtpunkte", st.session_state.total_score)
        st.button("Neustart (Abbruch)", on_click=reset_game)
        st.divider()
    
    # Zeigt die Historie (letzten 10 Spiele) an, falls der Spieler angemeldet ist
    if st.session_state.player_name:
        st.header("Historie")
        try:
            history_data, is_empty = db.get_last_games(st.session_state.player_id)
            if is_empty:
                st.caption(f"Noch keine Spiele gespielt als {st.session_state.player_name}.")
            else:
                formatted_hist = [[gm, f"{sc}/{r*10}", dt] for gm, sc, r, dt in history_data]
                st.subheader("📜 Letzte 10 Spiele")
                st.dataframe(pd.DataFrame(formatted_hist, columns = ["Modus", "Punkte", "Zeitpunkt"]), hide_index=True) 

        except Exception as e:
            st.error(f"Datenbankfehler aufgetreten: {e}")


# Hauptbereich
st.title("🌍 City Guesser Quiz")

# Startmenü mit Einstellungen (gesuchte Objekte, Spielmodus, Schwierigkeitsgrad und Anzahl der Runden)
if not st.session_state.game_started:
    st.markdown("### Einstellungen")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.game_mode = st.radio("Was suchen wir?", ["Städte", "Länder", "Berge", "Gebäude"])
        st.session_state.quiz_type = st.radio("Spielweise", ["Klassisch (Name)", "Rätsel (Umschreibung)"])
    with c2:
        st.session_state.difficulty_selection = st.select_slider("Schwierigkeit", ["Leicht", "Mittel", "Schwer"], value="Mittel")
        
        if st.session_state.game_mode in ["Berge", "Gebäude"]:
            max_rounds = 10
        else:
            max_rounds = 20

        st.session_state.rounds_per_game = st.slider(
            "Anzahl Runden",
            min_value=1,
            max_value=max_rounds,
            value=min(st.session_state.get("rounds_per_game", 5), max_rounds)
        )
    st.markdown("<br>", unsafe_allow_html=True)
    st.button("Spiel starten", type="primary", on_click=start_game)


# Ingame
if st.session_state.game_started:
    
    # Sicherheits-Check, ob Orte geladen wurden
    if not st.session_state.location_list:
        st.error("⚠️ Fehler: Keine Orte geladen.")
        if st.button("Zurück"):
            reset_game()
        st.stop()

    # Spielende
    if st.session_state.round > st.session_state.rounds_per_game:
        st.balloons()
        final = st.session_state.total_score
        max_p = st.session_state.rounds_per_game * 10
        st.metric("Dein Endergebnis", f"{final} / {max_p} Punkten")
        
        if not st.session_state.score_saved and st.session_state.player_id:
            mode = f"{st.session_state.game_mode} ({st.session_state.difficulty_selection})"
            if st.session_state.player_id != None: 
                db.save_score_to_db(final, st.session_state.rounds_per_game, mode, st.session_state.player_id)
                st.session_state.score_saved = True
                st.toast("Gespeichert!", icon="💾")
                
            
        if final >= max_p * 0.9: st.markdown("### 🏆 Legende!")
        elif final >= max_p * 0.6: st.markdown("### 🥈 Sehr gut!")
        else: st.markdown("### 🌍 Weiter üben!")
        
        st.button("Zum Menü", on_click=reset_game)
        st.stop()

    # Wahl der aktuellen Stadt basierend auf der Rundenzahl
    city = st.session_state.location_list[st.session_state.round - 1]
    
    # Anzeige der Fragestellung
    match st.session_state.game_mode:
        case "Berge":
            label = "Berg"
            st.markdown(f"**Höhe:** {city.get('hoehe', '?')} m")
        case "Gebäude":
            label = "Gebäude"
            st.markdown(f"**Höhe:** {city.get('hoehe', '?')} m")
        case "Länder": label = "Land"
        case "Städte": label = "Stadt"
        case _: label = "Objekt"
        
    if st.session_state.quiz_type == "Klassisch (Name)":
        match st.session_state.game_mode:
            case "Städte": st.markdown(f"Wo liegt die {label}: **{city['name']}**?")
            case "Berge": st.markdown(f"Wo liegt der {label}: **{city['name']}**?")
            case _: st.markdown(f"Wo liegt das {label}: **{city['name']}**?") # Bei Ländern und Gebäuden
    else:
        hint = city.get("clue", city["name"])
        st.markdown(f"Gesucht: **{hint}** ({label})")

    # Anzeige der Karte abhängig von der Schwierigkeit
    diff = st.session_state.difficulty_selection
    
    match diff:
        case "Leicht":
            # CartoDB PositronNoLabels: Klare politische Grenzen, grau, keine Namen
            map_tiles = "CartoDB VoyagerNoLabels"
            map_attr = '&copy; OpenStreetMap & CartoDB; Länderpolygone: Natural Earth 1:110m Cultural Vectors. Admin o - Countries.'
    
        case "Mittel":
            # Esri World Physical: Physische Karte (betont Kontinente/Gebirge), 
            # keine politischen Ländergrenzen, keine Namen
            map_tiles = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}"
            map_attr = 'Tiles &copy; Esri &mdash; Source: Esri; Länderpolygone: Natural Earth 1:110m Cultural Vectors. Admin o - Countries.'
            
        case "Schwer": # Schwer
            # Esri WorldImagery: Satellitenbild, keine Grenzen, keine Namen
            map_tiles = "Esri.WorldImagery"
            map_attr = 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community; Länderpolygone: Natural Earth 1:110m Cultural Vectors. Admin o - Countries.'

    # Karte initialisieren 
    m = folium.Map(
        location=[20, 0], 
        zoom_start=2, 
        min_zoom=2,
        max_zoom=6,
        tiles=map_tiles,
        attr=map_attr
    )

    # Marker, Linie und Polygon bei Ländern setzen
    if st.session_state.turn_over and st.session_state.last_click:
        # Marker für den eigenen Tipp
        guess_coord = (st.session_state.last_click['lat'], st.session_state.last_click['lng'])
        actual_coord = (city['lat'], city['lon'])
        folium.Marker(guess_coord, popup="Dein Tipp", icon=folium.Icon(color="red", icon="user")).add_to(m)
 
        # Polylinie (wird nicht gesetzt, wenn der Spielmodus Länder ist und das Land genau getroffen wurde)
        if st.session_state.game_mode != "Länder" or st.session_state.current_dist != 0:
            points = get_geodesic_path(guess_coord, actual_coord)
            folium.PolyLine(points, color="blue", weight=2, opacity=0.8).add_to(m)

        # Polygon bei Ländern
        if st.session_state.game_mode ==  "Länder":
            geo_json_data = db.get_country_geojson(city['name'])
            if geo_json_data:
                gj = folium.GeoJson(geo_json_data, name="Lösung", style_function=lambda x: {'fillColor':'#228B22','color':'#006400','weight':2,'fillOpacity':0.4}, tooltip=city['name']).add_to(m)
                bounds = gj.get_bounds()
                m.fit_bounds([guess_coord, bounds])
            else:
                folium.Marker(actual_coord, popup=city['name'], icon=folium.Icon(color="green", icon="flag")).add_to(m)
        # Marker für den tatsächlichen Standort, wenn keine Länder gesucht werden
        else:
            folium.Marker(actual_coord, popup=city['name'], icon=folium.Icon(color="green", icon="star")).add_to(m)
            m.fit_bounds([guess_coord, actual_coord])


    # Karte rendern
    map_key = f"map_round_{st.session_state.round}_{st.session_state.turn_over}" 
    output = st_folium(m, width="100%", height=600, key=map_key)

    # Klick Verarbeitung
    if output['last_clicked'] and not st.session_state.turn_over:
        st.session_state.last_click = output['last_clicked']
        guess = (st.session_state.last_click['lat'], st.session_state.last_click['lng'])
        
        # Berechnung in Python, wenn Städte, Berge oder Gebäude gesucht werden (Distanz ziwschen 2 Punkten)
        if st.session_state.game_mode in ["Städte", "Berge", "Gebäude"]:
            actual = (city['lat'], city['lon'])
            st.session_state.current_dist = geodesic(guess, actual).kilometers

        # Berechnung in PostgreSQL, wenn Länder gesucht werden (kürzeste Distanz zwischen Punkt und Polygon)
        if st.session_state.game_mode == "Länder":
            st.session_state.current_dist = db.calculate_dist_to_country(guess, city["name"])

        # Berechnung des Scores
        points = calculate_score(st.session_state.current_dist)
        
        st.session_state.current_round_score = points
        st.session_state.total_score += points
        st.session_state.turn_over = True
        st.rerun()

    # Ergebnis & Weiter
    if st.session_state.turn_over:
        c1, c2, c3 = st.columns(3)
        c1.metric("Distanz", f"{int(st.session_state.current_dist)} km")
        c2.metric("Punkte diese Runde", f"+ {st.session_state.current_round_score}")
        c3.metric("Gesamtpunkte", st.session_state.total_score)
        
        st.info(f"✅ Auflösung: **{city['name']}**\n\nℹ️ {city['info']}")
        
        btn_text = "Weiter"
        if st.session_state.round == st.session_state.rounds_per_game:
            btn_text = "Ergebnis ansehen"

        st.button(btn_text, type="primary", on_click=next_round)