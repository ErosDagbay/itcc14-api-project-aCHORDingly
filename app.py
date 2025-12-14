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



if __name__ == '__main__':
    app.run(debug=True)

    