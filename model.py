import code
import math
import logging

from datetime import datetime, timedelta

from sqlalchemy import create_engine, event
from sqlalchemy import Column, DateTime, Float, Integer, MetaData, UnicodeText
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declared_attr, declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

import geoalchemy
from geoalchemy.postgis import PGComparator

# Edit to reflect the db name, user and password to connect to your
# postgis database.
DB_SETTINGS = dict(
    db_name = 'spaces',
    db_user = 'dev',
    db_password = 'password',
    db_host = 'localhost',
    db_port = 5432
)

def engine_factory():
    """Creates the database engine."""
    
    settings = DB_SETTINGS
    postgresql_path = 'postgresql://%s:%s@%s:%s/%s' % (
        settings['db_user'],
        settings['db_password'],
        settings['db_host'],
        settings['db_port'],
        settings['db_name']
    )
    return create_engine(postgresql_path)

engine = engine_factory()

Session = scoped_session(sessionmaker(bind=engine))
SQLModel = declarative_base()

max_radius_of_earth = 6500 * 1000 # metres
max_sqrt_distance = math.sqrt(max_radius_of_earth * 0.95)
min_sqrt_distance = math.sqrt(100)

class Geography(geoalchemy.Geometry):
    """Subclass of ``Geometry`` that stores a `Geography Type`_.
      
      Defaults to storing a point.  Call with ``specific=False`` if you don't
      want to define the geography type it stores, or specify using
      ``geography_type='POLYGON'``, etc.
      
      _`Geography Type`: http://postgis.refractions.net/docs/ch04.html#PostGIS_Geography
    """
    
    @property
    def name(self):
        if not self.kwargs.get('specific', True):
            return 'GEOGRAPHY'
        geography_type = self.kwargs.get('geography_type', 'POINT')
        srid = self.kwargs.get('srid', 4326)
        return 'GEOGRAPHY(%s,%d)' % (geography_type, srid)
        
    
    

class BaseMixin(object):
    """Provides ``id``, ``v`` for version, ``c`` for created and ``m`` for
      modified columns and a scoped ``self.query`` property.
    """
    
    id =  Column(Integer, primary_key=True)
    
    v = Column(Integer, default=1)
    c = Column(DateTime, default=datetime.utcnow)
    m = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    query = Session.query_property()
    

class LocationMixin(object):
    """Provides ``self.latitude`` and ``self.longitude`` attributes and a 
      ``self.update_location()`` method which updates ``self.location``, 
      which is stored as a geography type in latlng projection.
      
      You can keep self.location uptodate automatically by binding to 
      ``before_insert`` and ``before_update`` events using, e.g.::
      
          class MyGeoModel(SQLModel, LocationMixin):
              pass
          
          handler = lambda mapper, connection, target: target.update_location()
          for event_name in 'before_insert', 'before_update':
              event.listen(MyGeoModel, event_name, handler)
          
      Also provides classmethods that return clauses to filter by ``within``,
      ``within_area`` and order by ``nearest``.  So, for example, to filter
      by within 10km of a latlng point, you can use::
      
          class MyGeoModel(SQLModel, BaseMixin, LocationMixin):
              pass
          
          latitude = 51.51333
          longitude = -0.0889469999
          
          within = MyGeoModel.within(latitude, longitude, 10 * 1000)
          query = MyGeoModel.query.filter(within)
      
      And to order the results nearest to the location::
      
          nearest = MyGeoModel.within(latitude, longitude)
          query.order_by(nearest)
      
    """
    
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    @declared_attr
    def location(self):
        return geoalchemy.GeometryColumn(
            Geography(), 
            comparator=PGComparator
        )
        
    
    def update_location(self):
        """Update ``self.location`` with a point value derived from 
          ``self.latitude`` and ``self.longitude``.  Note that the point will
          be `autocast`_ to geography type on saving:
          
          > Standard geometry type data will autocast to geography if it is of 
            SRID 4326.
          
          _`autocast`: http://postgis.refractions.net/docs/ch04.html#Geography_Basics
        """
        
        self.location = "POINT(%0.8f %0.8f)" % (self.longitude, self.latitude)
        
    
    
    @classmethod
    def within(cls, latitude, longitude, distance):
        """Return a within clause that explicitly casts the ``latitude`` and 
          ``longitude`` provided to geography type.  Note that `ST_DWithin`_ 
          will use a spatial index to filter out rows that are not within the
          boundary box before doing a sequential scan of the remaining rows.
          
          > This function call will automatically include a bounding box comparison 
            that will make use of any indexes that are available on the geometries.
          
          _`ST_DWithin`: http://postgis.refractions.net/docs/ST_DWithin.html
        """
        
        attr = '%s.location' % cls.__tablename__
        
        point = 'POINT(%0.8f %0.8f)' % (longitude, latitude)
        location = "ST_GeographyFromText(E'SRID=4326;%s')" % point
        
        return 'ST_DWithin(%s, %s, %d)' % (attr, location, distance)
        
    
    @classmethod
    def within_area(cls, area):
        """Return a within clause that explicitly casts the ``area`` polygon
          provided to geography type.
        """
        
        attr = '%s.location' % cls.__tablename__
        location = "ST_GeographyFromText(E'SRID=4326;%s')" % area
        return 'ST_DWithin(%s, %s, %d)' % (attr, location, 1)
        
    
    @classmethod
    def nearest(cls, latitude, longitude):
        """Return an order by `ST_Distance`_ clause to sort results by proximity.
        """
        
        attr = '%s.location' % cls.__tablename__
        
        point = 'POINT(%0.8f %0.8f)' % (longitude, latitude)
        location = "ST_GeographyFromText(E'SRID=4326;%s')" % point
        
        return 'ST_Distance(%s, %s)' % (attr, location)
        
    
    @classmethod
    def get_distance(
            cls, 
            base_query, 
            latitude,
            longitude,
            target_range=None, 
            too_few_results=45,
            too_many_results=75, 
            too_close=6.0
        ):
        """Recursive left-node-right algorithm for finding a distance that
          yields an acceptable number of results.
          
          Stops looking when it either finds an acceptable number of results
          or when it gets to ``min_sqrt_distance`` or ``max_sqrt_distance``.
        """
        
        if target_range is None:
            target_range = (0, math.sqrt(max_radius_of_earth))
        
        #logging.info('get_distance(%s, %s)' % (target_range[0], target_range[1]))
        
        # Get the mid point in the range and expand into the actual distance
        # in metres (the range is in sqrt because we're dealing with an area).
        mid = (target_range[0] + target_range[1]) / 2.0
        distance = mid * mid
        
        # If the range is too narrow, let's stop wasting our own resources.
        diff = target_range[1] - target_range[0]
        if diff < 0: diff = 0 - diff # should never happen!
        if diff < too_close or diff/mid*100 < too_close:
            #logging.info('too close')
            return distance
        
        # Count how many results are within that distance.
        within = cls.within(latitude, longitude, distance)
        distance_query = base_query.filter(within)
        count = distance_query.count()
        
        logging.info('count = %s' % count)
        
        # If there are too many results, try again with the bottom half of the range.
        # If too few, try again with the top half of the range.
        new_range = None
        if count > too_many_results and mid > min_sqrt_distance:
            #logging.info('too many')
            new_range = (target_range[0], mid)
        elif count < too_few_results and mid < max_sqrt_distance:
            #logging.info('too few')
            new_range = (mid, target_range[1])
        if new_range:
            return cls.get_distance(
                base_query, 
                latitude,
                longitude,
                target_range=new_range,
                too_few_results=too_few_results,
                too_many_results=too_many_results,
                too_close=too_close
            )
        
        # Otherwise we've found an acceptable distance.
        return distance
        
    
    

class Message(SQLModel, BaseMixin, LocationMixin):
    """Encapsulates a message."""
    
    __tablename__ = 'example_messages'
    
    content = Column(UnicodeText)
    
    def __repr__(self):
        return u'<Message id="%s" content="%s">' % (
            self.id, 
            self.snip('content', 20)
        )
        
    
    


# Bind locatable class before insert or update events to ``target.update_location()``.
handler = lambda mapper, connection, target: target.update_location()
for event_name in 'before_insert', 'before_update':
    event.listen(Message, event_name, handler)

SQLModel.metadata.create_all(engine)

def reset_db():
    """ Drop all and create afresh.
    """
    
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    
    

def populate_db():
    """ Populate the database.
    """
    
    import random
    
    session = Session()
    messages = []
    t1 = datetime.now()
    for i in range(1, 500):
        latitude = random.randrange(-900,900) * 0.1
        longitude = random.randrange(-1800,1800) * 0.1
        message = Message(
            content=u'I am message %d' % i,
            c=t1-timedelta(500 - i),
            latitude=latitude,
            longitude=longitude
        )
        messages.append(message)
    session.add_all(messages)
    try:
        session.commit()
    except IntegrityError, err:
        logging.error(err)
        session.rollback()
    finally:
        session.close()
    

def bootstrap():
    """Populate the database from scratch."""
    
    reset_db()
    populate_db()
    


if __name__ == '__main__':
    bootstrap()
    # code.interact(local=locals())
    

