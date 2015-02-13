# -*- coding: utf-8 -*-
from configparser import ConfigParser
import json

from flask import Flask
from flask import jsonify
from flask import render_template
from flask import request

from util import WeekenderEncoder
from util import bound_weekend
from util import parse_date
import airline


app = Flask(__name__)
app.json_encoder = WeekenderEncoder

weekender = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/flights')
def flights():
    selected = request.args.get('selected', None)
    selected = parse_date(selected)

    begin, end = bound_weekend(selected)

    if not selected or not begin:
        return json.dumps({
            'error': 'Invalid date',
        })

    begin_results = weekender.request_with_next(begin)
    end_results = weekender.request_with_next(end, reverse=True)

    data = {
        'begin': begin_results,
        'end': end_results,
    }

    return jsonify(data)

def create():
    global weekender

    config_file = 'config.ini'

    config = ConfigParser()
    config.read(config_file)

    weekender = airline.Weekender(config)

    return app

if __name__ == '__main__':
    create()

    app.run(host='0.0.0.0', debug=True)
