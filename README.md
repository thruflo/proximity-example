This is an example application demonstrating an adequate-result-volume
algorithm for filtering real time data by proximity.  It's written in
[Python][] and [CoffeeScript][] using [SQLAlchemy][].

There's a fairly long write up on [my blog][] explaining the thinking behind
it at [thruflo.com/post/13978467678/filter-by-proximity][].

To use it, you'll need to go through the non trivial step of setting up 
[a spatially enabled SQL database][].  Once you have that up and running,
clone the repo:

    git clone git@github.com:thruflo/proximity-example.git
    cd proximity-example

Install the dependencies:

    easy_install sqlalchemy geoalchemy weblayer

Bootstrap the db (creating 500 randomly located `Message`s):

    python model.py

Run the app:

    python app.py

And play with it on [http://localhost:8080][].

[a spatially enabled SQL database]: http://geoalchemy.readthedocs.org/en/latest/tutorial.html
[coffeescript]: http://jashkenas.github.com/coffee-script/
[http://localhost:8080]: http://localhost:8080
[my blog]: http://thruflo.com
[python]: http://python.org/
[sqlalchemy]: http://www.sqlalchemy.org/docs/orm/tutorial.html
[thruflo.com/post/13978467678/filter-by-proximity]: http://thruflo.com/post/13978467678/filter-by-proximity
