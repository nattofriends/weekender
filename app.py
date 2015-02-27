# -*- coding: utf-8 -*-
from configparser import ConfigParser
from operator import attrgetter
import json

from flask import Flask
from flask import jsonify
from flask import render_template
from flask import request

from util import WeekenderEncoder
from util import bound_weekend
from util import flatten
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

    origin_days, return_days = bound_weekend(selected, weekender.config)

    if not selected or not origin_days:
        return json.dumps({
            'error': 'Invalid date',
        })

    begin_results = sorted(
        flatten([
            weekender.request_with_next(origin_day)
            for origin_day in origin_days
        ]),
        key=attrgetter('fare'),
    )
    end_results = sorted(
        flatten([
            weekender.request_with_next(return_day, reverse=True)
            for return_day in return_days
        ]),
        key=attrgetter('fare'),
    )

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
