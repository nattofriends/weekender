# -*- coding: utf-8 -*-
from collections import namedtuple
from datetime import timedelta
from datetime import date, time, datetime
from json import loads
import itertools
import operator
import re

from lxml import html
import cachetools
import cssselect
import requests

from config import config
from util import flatten
from util import meridian
from util import tomorrow


class FlightInfo(namedtuple("FlightInfo", [
    "origin",
    "destination",
    "depart_date",
    "carrier",
    "booking_link",
    "is_early",
    "depart_time",
    "arrive_time",
    "flight_no",
    "fare"
])):
    pass

class Weekender:
    def __init__(self):
        self.config = config
        self.ar = AirlineRegistry
        self.ar.instantiate(config)

        self.leave_after = self._parse_time(config['general']['leave_after'])
        self.leave_before = self._parse_time(config['general']['leave_before'])

    def _parse_time(self, time_string):
        hour, minute = time_string.split(":")
        return time(hour=int(hour), minute=int(minute))

    @cachetools.ttl_cache()
    def request_with_next(self, date, reverse=False):
        day = self.request(date, operator.gt, self.leave_after, reverse=reverse, early=False)
        day_after = self.request(date + timedelta(days=1), operator.lt, self.leave_before, reverse=reverse, early=True)

        return flatten([day, day_after])

    def request(self, date, cmp, filter_bound, reverse=False, early=False):
        result = self.ar.request_all(date, reverse=reverse, early=early)

        result = [fi for fi in result if cmp(fi.depart_time, filter_bound)]

        return result

class AirlineRegistry(type):
    classes = []
    airlines = []
    done = False

    def __new__(cls, name, bases, attrs):
        new_cls = type.__new__(cls, name, bases, attrs)

        if bases is not ():
            cls.classes.append(new_cls)

        return new_cls

    @classmethod
    def instantiate(cls, config):
        if cls.done:
            return

        cls.airlines = [airline(config) for airline in cls.classes]
        cls.done = True

    @classmethod
    def request_single(cls, origin, destination, date):
        results = [airline.request_single(origin, destination, date) for airline in cls.airlines]
        return flatten(results)

    @classmethod
    def request_all(cls, date, reverse=False, early=False):
        results = [airline.request_all(date, reverse=reverse, early=early) for airline in cls.airlines]
        return flatten(results)

class AirlineBase(metaclass=AirlineRegistry):
    def __init__(self, config):
        self.config = config
        self.s = requests.session()

        # Just in case
        self.s.headers['User-Agent'] = "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.91 Safari/537.36"
        self.s.headers['Referer'] = self.endpoint

    def resp_to_html(self, resp):
        return html.fromstring(resp.text)

    def elem_sel_to_text(self, elem, sel, sep=''):
        return sep.join([sub.text_content() for sub in elem.cssselect(sel)])

    @property
    def origins(self):
        return (self.config[self.__class__.__name__]['origins'].split(',')
                if self.__class__.__name__ in self.config
                else [])

    @property
    def destinations(self):
        return (self.config[self.__class__.__name__]['destinations'].split(',')
                if self.__class__.__name__ in self.config
                else [])

    def request_all(self, date, reverse=False, early=False):
        if reverse:
            product = itertools.product(self.destinations, self.origins)
        else:
            product = itertools.product(self.origins, self.destinations)

        results = [
            self.request_single(origin, destination, date, early=early)
            for origin, destination
            in product
        ]

        return flatten(results)

    def request_single(self, origin, destination, date, early):
        formatted_date = date.strftime(self.date_format)

        data = self.fixed_data.copy()
        data.update({
            self.dynamic_fields['origin']: origin,
            self.dynamic_fields['destination']: destination,
            self.dynamic_fields['formatted_date']: formatted_date,
        })

        rows = self._request_single(origin, destination, date, early, data)

        flightinfos = [self.extract_row_to_flightinfo(row, origin, destination, date, early) for row in rows]
        flightinfos = [fi for fi in flightinfos if fi is not None]

        return flightinfos

    def _request_single(self, origin, destination, date, early):
        """Each subclass should implement this."""
        raise NotImplementedError

    def _google_flights_link(self, origin, destination, date, carrier, flight_no):
        return 'https://www.google.com/flights/#search;f={origin};t={destination};d={date};tt=o;sel={origin}{destination}0{carrier}{flight_no}'.format(
            origin=origin,
            carrier=carrier,
            flight_no=flight_no,
            destination=destination,
            date=date.strftime('%Y-%m-%d'),
        )

    def _parse_time_string(self, time_string):
        numbers, indicator = time_string.split(" ")
        hour, minute = numbers.split(":")
        hour = int(hour)
        minute = int(minute)

        hour = meridian(hour, indicator)

        return time(hour=hour, minute=minute)

    def _parse_iso_datetime_string(self, datetime_string):
        """Parse ISO8601 with strptime because lol."""
        return datetime.strptime(re.sub(r'(\d{2}):(\d{2})$', r'\1\2', datetime_string), '%Y-%m-%dT%H:%M:%S%z')

class Southwest(AirlineBase):
    carrier = 'WN'
    endpoint = "https://www.southwest.com/flight/select-flight.html"
    date_format = '%m/%d/%y'

    # Damn all these fields!
    fixed_data = {
        "selectedOutboundTrip": "",
        "selectedInboundTrip": "",
        "awardCertificateProductId": "",
        "returnAirport": "",
        "promoCode": "",

        "promoCertSelected": "false",
        "transitionalAwardSelected": "false",
        "showAwardToggle": "false",
        "awardCertificateToggleSelected": "false",
        "oneWayCertificateOrAward": "false",
        "swaBizDiscountSearch": "false",

        "modifySearchSubmitButton": "Search",

        # Actually interesting fixed data
        "adultPassengerCount": 1,
        "seniorPassengerCount": 0,
        "outboundTimeOfDay": "ANYTIME",
        "returnTimeOfDay": "ANYTIME",
        "bugFareType": "DOLLARS",
        "fareType": "DOLLARS",

        # Not really true, but it doesn't seem to mind.
        "originAirport_displayed": "",
        "destinationAirport_displayed": "",
    }

    dynamic_fields = {
        'origin': 'originAirport',
        'destination': 'destinationAirport',
        'formatted_date': 'outboundDateString',
    }

    def _request_single(self, origin, destination, date, early, data):
        r = self.s.post(self.endpoint, data=data)
        doc = self.resp_to_html(r)
        rows = doc.cssselect(".searchResultsTable > tbody > tr")

        return rows

    def extract_row_to_flightinfo(self, row, origin, destination, date, is_early):
        # Depart, arrive, flight number, Wanna Get Away fare
        to_extract = {
            0: self._col_time,
            1: self._col_time,
            2: self._col_flight,
            7: self._col_fare,
        }

        # Only top level td
        cols = row.xpath("td")

        if len(cols) < 8:  # Wanna Get Away <td> isn't there at all. All fares are sold out
            return None

        row_extracted_data = [to_extract[i](col) for i, col in enumerate(cols) if i in to_extract.keys()]

        interested_cols = \
            [origin, destination, date, self.carrier, self._google_flights_link(origin, destination, date, self.carrier, row_extracted_data[2]), is_early] + \
            row_extracted_data

        fi = FlightInfo(*interested_cols)

        if fi.fare is None:
            return None

        return fi

    def _col_time(self, col):
        time_string = self.elem_sel_to_text(col, ".time")
        indicator = self.elem_sel_to_text(col, ".indicator")

        return self._parse_time_string(time_string + ' ' + indicator)

    def _col_flight(self, col):
        return self.elem_sel_to_text(col, ".bugLinkText", sep='/').replace(' (opens popup)', '')

    def _col_fare(self, col):
        fare = self.elem_sel_to_text(col, ".product_price").strip(' \n\t$')

        if fare == '':
            return None

        return int(fare)

class JetBlue(AirlineBase):
    carrier = 'B6'
    endpoint = "https://book.jetblue.com/B6/webqtrip.html"
    ajax_endpoint = "https://book.jetblue.com/B6/AirLowFareSearchExt.do"
    second_endpoint = "https://book.jetblue.com/B6/AirFareFamiliesFlexibleForward.do"
    date_format = '%Y-%m-%d'

    fixed_data = {
        "searchType": "NORMAL",
        "returnDate": "",
        "numAdults": 1,
        "numChildren": 0,
        "numInfants": 0,
        "adult_count": 1,
        "kid_count": 0,
        "infant_count": 0,
        "journeySpan": "OW",
        "flight_type": "one_way",
        "fareFamily": "LOWESTFARE",
        "fareDisplay": "lowest",
        "fare_display": "lowest",
    }

    dynamic_fields = {
        'origin': 'origin',
        'destination': 'destination',
        'formatted_date': 'departureDate',
    }

    def _request_single(self, origin, destination, date, early, data):
        r = self.s.post(self.endpoint, data=data)
        r = self.s.post(self.ajax_endpoint, data={'ajaxAction': 'true'})
        r = self.s.get(self.second_endpoint)

        # Thanks for nothing, JetBlue.
        m = re.search(
            r'tdGroupData\[0\] =(.*?});',
            r.text.replace('\n', ''),
        )

        # ``Escaping'', they said!
        json_text = m.group(1).replace("\\'", "'")

        fares = [
            html.fromstring(fare_html)
            for fare_html
            in list(loads(json_text).values())
        ]

        return fares

    def extract_row_to_flightinfo(self, row, origin, destination, date, is_early):
        # Ignore non-nonstop?
        if len(row.getchildren()) != 1:
            return

        depart_time = self._parse_time_string(
            self.elem_sel_to_text(row, ".colDepart .time")
        )

        arrive_time = self._parse_time_string(
            self.elem_sel_to_text(row, ".colArrive .time")
        )

        flight_number = self.elem_sel_to_text(row, '.flightCode').replace('Flight number ', '')

        fare = int(
            row.cssselect(".colPrice")[0].text_content().strip(' \r\n\t$')
        )

        # TODO: Need more checks here
        fi = FlightInfo(
            origin,
            destination,
            date,
            self.carrier,
            self._google_flights_link(
                origin, destination, date, self.carrier, flight_number,
            ),
            is_early,
            depart_time,
            arrive_time,
            flight_number,
            fare,
        )

        return fi

class United(AirlineBase):
    carrier = 'UA'
    endpoint = "https://mobile.united.com/Booking/OneWaySearch"
    date_format = "%a., %b. %d, %Y"

    fixed_data = {
        "SearchType": "OW",
        "DepartTime": "0000",
        "NumberOfAdults": "1",
        "Cabin": "Coach",
        "SearchBy": "P",
        "NonstopOnly": "true",

        # Yes, it works fine without FromCode and ToCode.
    }

    # If you observe the actual requests, these are formatted
    # locations, i.e. "San Francisco, CA (SFO)" yet they are used (and
    # must be correct) to do routing. Why, United, why?
    dynamic_fields = {
        'origin': 'From',
        'destination': 'To',
        'formatted_date': 'DepartDate',
    }

    def _request_single(self, origin, destination, date, early, data):
        r = self.s.post(self.endpoint, data=data, cookies={'AspxAutoDetectCookieSupport': '1'})

        doc = self.resp_to_html(r)
        rows = doc.cssselect("ul[data-role='listview']")[:-1]

        # More pages?
        next_page = doc.cssselect("a[href*='DisplayNextFlights']")
        while next_page:
            next_page, = next_page
            r = self.s.get('https://mobile.united.com' + next_page.attrib['href'])
            doc = self.resp_to_html(r)
            rows +=  doc.cssselect("ul[data-role='listview']")[:-1]
            next_page = doc.cssselect("a[href*='/Booking/DisplayNextFlights']")

        return rows

    def _extract_time_for_label(self, row, label):
        # This is disgusting.
        info = row.xpath(".//label[@for='{}']/../following-sibling::div".format(label))[0].text_content()
        time_string, _, _ = [text.strip() for text in info.strip('\t\r\n').split('\r\n')]
        return self._parse_time_string(time_string)

    def extract_row_to_flightinfo(self, row, origin, destination, date, is_early):
        _, flight_number = row.xpath(".//img[@alt='carrier logo']/..")[0].text_content().strip().split(' ')

        depart_time = self._extract_time_for_label(row, 'DepartureAirportName')
        arrive_time = self._extract_time_for_label(row, 'ArrivalAirportName')

        fare_button = row.cssselect('#btnPickTrip')[0].attrib['value']
        m = re.search("\$(\d+)", fare_button)
        fare = int(m.group(1))

        # TODO: What is error checking? Hello? Bueller?
        fi = FlightInfo(
            origin,
            destination,
            date,
            self.carrier,
            self._google_flights_link(
                origin, destination, date, self.carrier, flight_number,
            ),
            is_early,
            depart_time,
            arrive_time,
            flight_number,
            fare,
        )

        return fi

class VirginAmerica(AirlineBase):
    carrier = 'VX'
    endpoint = "https://www.virginamerica.com/api/v0/booking/search"
    date_format = '%Y-%m-%d'

    fixed_data = {
        "numOfAdults": 1,
        "bookingType": "DOLLAR"
    }

    dynamic_fields = {
        'origin': 'origin',
        'destination': 'dest',
        'formatted_date': 'departureDate',
    }

    def _request_single(self, origin, destination, date, early, data):
        data['returningDate'] = data['departureDate']
        r = self.s.post(self.endpoint, json={'roundTrip': data})
        d = r.json()
        if d['status']['status'] != 'SUCCESS':
            return []
        if not d['response']['departingFlightsInfo']['flightList']:
            return []

        return d['response']['departingFlightsInfo']['flightList']['NON_STOP']

    def extract_row_to_flightinfo(self, row, origin, destination, date, is_early):
        # Virgin breaks down all the fare types so let's use the cheapest here.
        fare = round(min([x['dollarFare']['totalFare']
                          for x in row['fareList'].values()
                          if 'dollarFare' in x]))

        seg = row['flightSegment']

        depart_time = self._parse_iso_datetime_string(seg['departureDateTime']).time()
        arrive_time = self._parse_iso_datetime_string(seg['arrivalDateTime']).time()

        return FlightInfo(
            origin,
            destination,
            date,
            self.carrier,
            self._google_flights_link(
                origin, destination, date, self.carrier, seg['flightNum'],
            ),
            is_early,
            depart_time,
            arrive_time,
            seg['flightNum'],
            fare,
        )


if __name__ == '__main__':
    from datetime import date
    ua = United(config)
    print(len(ua.request_single('SFO', 'SNA', date(2016, 8, 19), early=False)))
