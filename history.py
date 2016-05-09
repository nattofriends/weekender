from datetime import date, datetime, timedelta
from itertools import repeat

from sqlalchemy import create_engine, Boolean, Column, DateTime, Integer, Numeric, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from airline import Weekender
from config import config
from util import bound_weekend
from util import flatten


Base = declarative_base()


class Sample(Base):
    __tablename__ = 'samples'

    id = Column(Integer, primary_key=True)
    sample_time = Column(DateTime)
    target_weekend = Column(DateTime)

    origin = Column(String)
    destination = Column(String)
    departure = Column(DateTime)
    carrier = Column(String)
    is_early = Column(Boolean)
    flight_no = Column(String)
    fare = Column(Numeric)  # USD

if __name__ == "__main__":
    engine = create_engine(config['general']['db_url'])
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    weekender = Weekender()

    now = datetime.now()
    day = date.today()

    sampling_min = day + timedelta(
        days=((11 - day.weekday()) % 7) + 1,  # :math:
    )
    sampling_sats = [
        sampling_min + timedelta(weeks=weeks)
        for weeks in range(int(config['general']['sampling_horizon']))
    ]
    sampling_intervals = [
        (sat, bound_weekend(sat, config))
        for sat in sampling_sats
    ]
    sampling_results = flatten([
        zip(
            repeat(sat),
            flatten([
                weekender.request_with_next(origin_day)
                for origin_day in origin_days
            ]) +
            flatten([
                weekender.request_with_next(return_day, reverse=True)
                for return_day in return_days
            ]),
        )
        for sat, (origin_days, return_days) in sampling_intervals
    ])

    for sat, result in sampling_results:
        sample = {
            'sample_time': now,
            'target_weekend': sat,
            'departure': datetime.combine(result.depart_date, result.depart_time),
        }

        sample.update(
            {
                k: v for k, v in result._asdict().items()
                if k not in ('booking_link', 'depart_date', 'depart_time', 'arrive_time')
            }
        )

        sample = Sample(**sample)
        session.add(sample)

    session.commit()
