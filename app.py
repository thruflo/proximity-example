import os
import model

from weblayer import Bootstrapper, RequestHandler, WSGIApplication

class Index(RequestHandler):
    """Handle requests to `/` by rendering `index.tmpl`."""
    
    def get(self):
        return self.render('index.tmpl')
        
    
    

class Query(RequestHandler):
    """Handle requests to `/query` by querying the database for messages,
      filtered by proximity and sorted by most recent.
    """
    
    limit = 50
    
    def get(self):
        """Returns JSON data with results list and distance value."""
        
        # Get a query for all `Message`s.
        query = model.Message.query
        
        # Get the query parameters (in this example from a `request` object).
        params = self.request.params
        lat = float(params['latitude'])
        lng = float(params['longitude'])
        distance = float(params.get('distance', 0))
        
        # Filter by `within` clause.
        if not distance:
            distance = model.Message.get_distance(query, lat, lng)
        within = model.Message.within(lat, lng, distance)
        query = query.filter(within)
        
        # Sort the results so the most recent come first.
        query = query.order_by(model.Message.c.desc())
        results = query.limit(self.limit).all()
        
        # Return results list and distance (data will be coerced to JSON).
        return {
            'results': [item.content for item in results],
            'distance': distance
        }
        
    
    

class Static(RequestHandler):
    """Silly static files serving class, provided in lieu of a proper file
      server to keep the example simple.
    """
    
    def get(self, file_name):
        static_file = os.path.join(self.settings['static_files_path'], file_name)
        sock = open(static_file)
        text = sock.read()
        sock.close()
        return text
        
    
    


mapping = [
    (r'/', Index), 
    (r'/query', Query),
    (r'/static/(.*)', Static)
]

# Below here is just `weblayer <>`_ WSGI app boilerplate.
here = os.path.dirname(__file__)
config = {
    'cookie_secret': '...',
    'static_files_path': here,
    'template_directories': [here]
}
bootstrapper = Bootstrapper(settings=config, url_mapping=mapping)
application = WSGIApplication(*bootstrapper())

def main():
    from wsgiref.simple_server import make_server
    make_server('', 8080, application).serve_forever()
    

if __name__ == '__main__':
    main()
