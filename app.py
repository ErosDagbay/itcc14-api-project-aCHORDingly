from flask import Flask, jsonify, request
from flask import redirect, url_for
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import re
from flasgger import Swagger, swag_from

app = Flask(__name__)

app.config['SWAGGER'] = {
    'title': 'aChordingly',
    'uiversion': 3
}

swagger = Swagger(app,
    config={
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec',
                "route": '/apispec.json',
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/apidocs/"
    },
    template_file="swagger/aChordingly.yaml"
)

uri = "mongodb+srv://20140006519_db_user:LVsTONzfgoLPu2iD@achordingly.tryhkev.mongodb.net/?appName=aChordingly"

# Send a ping to confirm a successful connection
client = MongoClient(uri, server_api=ServerApi('1'))
try:
    client.admin.command('ping')
    print("Connection Successful!")
except Exception as e:
    print("Error:", e)

chords_db = client['Chords_and_Instruments']['chords']
songs_db = client['Songs_with_Chords']['songs']

# Constants for Validation
VALID_INSTRUMENTS = ["guitar", "piano", "ukulele"]
VALID_TUNINGS = ["standard", "dropD", "DADGAD"]
VALID_STYLES = ["minimal", "detailed"]

# Home route
@app.route("/")
def home():
    return redirect("/apidocs")

# Get all chords
@app.route('/chords', methods=['GET'])
def get_all_chords():
    try:
        chords = list(chords_db.find({}, {"_id": 0}))
        return jsonify(chords), 200
    except Exception as e:
        return jsonify({"error": f"Error fetching chords: {str(e)}"}), 500

# Get chords by instrument
@app.route('/chords/<instrument>', methods=['GET'])
def get_chords_by_instrument(instrument):
    try:
        chords = list(chords_db.find({"instrument": instrument}, {"_id": 0}))
        if chords:
            return jsonify(chords), 200
        return jsonify({"error": "No chords found for this instrument"}), 404
    except Exception as e:
        return jsonify({"error": f"Error fetching chords: {str(e)}"}), 500

# Add new chord
@app.route('/chords', methods=['POST'])
def add_chord():
    data = request.get_json()

    if not data or "chord" not in data or "instrument" not in data:
        return jsonify({
            "error": "Provide a chord and instrument",
            "example": {
                "chord": "E minor",
                "instrument": "guitar",
                "tuning": "standard",
                "variants": ["minor"],
                "png": "https://placeholder.com/chord.png"
            }
        }), 400

    # Add PNG placeholder if user did NOT provide one
    if "png" not in data:
        data["png"] = "https://placeholder.com/chord_diagram.png"

    result = chords_db.insert_one(data)
    if result.inserted_id:
        return jsonify({"message": "Chord added successfully!"}), 201
    else:
        return jsonify({"error": "Error adding chord"}), 500

@app.route('/chords/<chord_name>/variants', methods=['GET'])    
def get_chord_variants(chord_name):
    params = {
        "chord": chord_name.lower(),
        "instrument": request.args.get('instrument', 'guitar').lower(),
        "tuning": request.args.get('tuning', 'standard').lower()
    }
    chord_info = chords_db.find_one(params, {"_id": 0, "variants": 1})

    if not chord_info:
        return jsonify({"error": "No variants found for the given parameters"}), 404

    log_usage(params["chord"], params["instrument"])

    return jsonify({"chord": params["chord"], **params, "variants": chord_info["variants"]}), 200


# Analytics tracking
USAGE_ANALYTICS = {"top_chords": {}, "top_instruments": {}}

def log_usage(chord_name, instrument):
    USAGE_ANALYTICS["top_chords"][chord_name] = USAGE_ANALYTICS["top_chords"].get(chord_name, 0) + 1
    USAGE_ANALYTICS["top_instruments"][instrument] = USAGE_ANALYTICS["top_instruments"].get(instrument, 0) + 1

@app.route('/analytics/chord-usage', methods=['GET'])
def get_chord_analytics():
    response = {
        "top_chords": [{"chord": k, "count": v} for k, v in sorted(USAGE_ANALYTICS["top_chords"].items(), key=lambda x: x[1], reverse=True)],
        "top_instruments": [{"instrument": k, "count": v} for k, v in sorted(USAGE_ANALYTICS["top_instruments"].items(), key=lambda x: x[1], reverse=True)]
    }
    return jsonify(response)

# Extract chords from lyrics
def extract_chords(lyrics):
    return list(set(re.findall(r'\[([^\]]+)\]', lyrics)))

@app.route('/chords/generate-from-lyrics', methods=['POST'])
def generate_chords():
    data = request.get_json()

    if not data or "lyrics_with_chords" not in data:
        return jsonify({"error": "'lyrics_with_chords' is required"}), 400

    instrument = data.get("instrument", "guitar")
    tuning = data.get("tuning", "standard")

    if instrument not in VALID_INSTRUMENTS or tuning not in VALID_TUNINGS:
        return jsonify({"error": "Invalid instrument or tuning"}), 400

    chords = extract_chords(data["lyrics_with_chords"])
    response = {"instrument": instrument, "tuning": tuning, "chords": chords}
    return jsonify(response), 200

# Add songs
@app.route('/songs', methods=['POST'])
def add_song():
    try:
        data = request.get_json()

        if not data or "title" not in data or "lyrics_with_chords" not in data:
            return jsonify({"error": "Provide 'title' and 'lyrics_with_chords'"}), 400
        
        # Prevent duplicate song titles
        if songs_db.find_one({"title": data["title"]}):
            return jsonify({"error": "Song with this title already exists"}), 409
        
        # Insert into the database
        songs_db.insert_one(data)
        
        return jsonify({
            "message": "Song added successfully!",
            "song": {
                "title": data["title"],
                "lyrics_with_chords": data["lyrics_with_chords"]
            }
        }), 201

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# Get all available songs
@app.route('/songs', methods=['GET'])
def list_songs():
    songs = list(songs_db.find({}, {"_id": 0, "title": 1}))
    return jsonify({"songs": [song["title"] for song in songs]}), 200

# Update Lyrics in the songs
@app.route('/songs/<song_title>', methods=['PUT'])
def update_song(song_title):
    try:
        data = request.get_json()
        
        if not data or "lyrics_with_chords" not in data and "title" not in data:
            return jsonify({"error": "Provide 'lyrics_with_chords' or 'title' to update"}), 400
        
        song = songs_db.find_one({"title": song_title})
        if not song:
            return jsonify({"error": "Song not found"}), 404
        
        update_fields = {}
        if "lyrics_with_chords" in data:
            update_fields["lyrics_with_chords"] = data["lyrics_with_chords"]
        if "title" in data:
            update_fields["title"] = data["title"]
        
        result = songs_db.update_one({"title": song_title}, {"$set": update_fields})
        if result.modified_count:
            return jsonify({"message": "Song updated successfully!"}), 200
        return jsonify({"message": "No changes made to the song"}), 200

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# Delete Songs
@app.route('/songs/<song_title>', methods=['DELETE'])
def delete_song(song_title):
    try:
        result = songs_db.delete_one({"title": song_title})
        
        if result.deleted_count:
            return jsonify({"message": "Song deleted successfully!"}), 200
        return jsonify({"error": "Song not found"}), 404

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# get a specific songs
@app.route('/songs/<song_title>', methods=['GET'])
def get_song(song_title):
    song = songs_db.find_one({"title": song_title}, {"_id": 0})
    if not song:
        return jsonify({"error": "Song not found"}), 404
    return jsonify(song), 200
    
if __name__ == '__main__':
    app.run(debug=True)

    
