# Sämtliche Datenbanklogik

import psycopg2
import streamlit as st

# Konfiguration der DB-Verbindung
DB_CONFIG = {
    "dbname": "", 
    "user": "postgres",
    "password": "",
    "host": "localhost",
    "port": "5432"
}

# Herstellung der DB-Verbindung
def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        st.error(f"Datenbank-Verbindungsfehler: {e}")

# Wählt eine bestimmte Anzahl an Orten abhängig vom Spielmodus  
def fetch_random_locations(table_name, count, difficulty):
    conn = get_db_connection()
    if not conn:
        return []

    cur = conn.cursor()
    
    # Bei Bergen und Gebäuden wird die Höhe mit abgefragt
    if table_name in ["berge", "gebaeude"]:
        query = f"""
        SELECT name, latitude, longitude, hoehe, info, difficulty, clue
        FROM {table_name}
        WHERE difficulty = %s
        ORDER BY RANDOM()
        LIMIT %s;
        """

        data = []
        try:
            cur.execute(query, (difficulty, count))
            results = cur.fetchall()
            for res in results:
                data.append({
                    "name": res[0],
                    "lat": float(res[1]),
                    "lon": float(res[2]),
                    "hoehe": res[3],
                    "info": res[4],
                    "difficulty": res[5],
                    "clue": res[6]
                })
        except Exception as e:
            st.error(f"SQL Fehler: {e}")
        finally:
            conn.close()
    
    # Bei Städten und Ländern wird keine Höhe abgefragt
    else:
        query = f"""
            SELECT name, latitude, longitude, info, difficulty, clue
            FROM {table_name} 
            WHERE difficulty = %s
            ORDER BY RANDOM()
            LIMIT %s;
        """

        data = []
        try:
            cur.execute(query, (difficulty, count))
            results = cur.fetchall()
            for res in results:
                data.append({
                    "name": res[0],
                    "lat": float(res[1]),
                    "lon": float(res[2]),
                    "info": res[3],
                    "difficulty": res[4],
                    "clue": res[5]
                })
        except Exception as e:
            st.error(f"SQL Fehler: {e}")
        finally:
            conn.close()

    return data

# Berechnung der Distanz zwischen Tipp und Land in PostgreSQL
def calculate_dist_to_country(guess, country):
    conn = get_db_connection()
    if not conn: return None
    
    guess_lat, guess_lon = guess

    cur = conn.cursor()
    try:
        query = """
            SELECT ST_Distance(
                geom::geography, 
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
            ) AS distance_meters 
            FROM countries 
            WHERE name = %s
        """
        cur.execute(query, (guess_lon, guess_lat, country))

        result = cur.fetchone()

        if result and result[0] is not None:
            distance_m = result[0]
            distance_km = distance_m / 1000
            return distance_km
        else:
            return None
        
    except Exception as e:
        st.error(f"SQL Fehler: {e}")
        return None
    finally:
        cur.close()
        conn.close()

# Abfrage der Länder Geometrie als Geojson
def get_country_geojson(country_name):
    conn = get_db_connection()
    if not conn: return None
    
    cur = conn.cursor()
    try:
        query = "SELECT ST_AsGeoJSON(geom) FROM countries WHERE name = %s"
        cur.execute(query, (country_name,))
        
        result = cur.fetchone()
        
        if result and result[0]:
            return result[0]
        return None

    except Exception as e:
        st.error(f"SQL Fehler (GeoJSON): {e}")
        return None
    finally:
        cur.close()
        conn.close()

# Speichern des Scores
def save_score_to_db(score, rounds, game_mode, player_id):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO game_history (game_mode, score, rounds, player) VALUES (%s, %s, %s, %s)", (game_mode, score, rounds, player_id,))
            cur.execute("UPDATE players SET played_games = played_games + 1 WHERE id = %s",(player_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            st.error(f"SQL Fehler: {e}")

# Abfrage der letzten 10 Spiele
def get_last_games(player_id):
    conn = get_db_connection()
    if not conn: return []
    cur = conn.cursor()
    cur.execute("SELECT game_mode, score, rounds, to_char(played_at, 'DD.MM. HH24:MI') FROM game_history WHERE player = %s ORDER BY played_at DESC LIMIT 10;", (player_id,))
    rows = cur.fetchall()
    if not rows: is_empty = True
    else: is_empty = False
    conn.close()
    return rows, is_empty

# Anmeldung mit Spielernamen
def log_in(player_name):
    conn = get_db_connection()
    if not conn: return []
    cur = conn.cursor()

    cur.execute("SELECT id FROM players WHERE name = %s", (player_name,))
    result = cur.fetchone()

    if result:
        player_id = result[0]

    else:
        cur.execute("INSERT INTO players (name, played_games) VALUES (%s, 0)", (player_name,))
        conn.commit()
        cur.execute("SELECT id FROM players WHERE name = %s", (player_name,))
        result = cur.fetchone()
        player_id = result[0]
    
    conn.close()
    
    return player_id