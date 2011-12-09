# This is a `CoffeeScript <http://jashkenas.github.com/coffee-script/>`_ file
# that gets compiled into JavaScript before it is executed by the browser.
# 
# As it happens, I've used a bunch of libraries to make coding the example
# quicker, including `jQuery Mobile <http://jquerymobile.com/>`_ for the slider
# widget and `Backbone.js <http://documentcloud.github.com/backbone/>`_ as a
# base class for our two view components.  However, there's no real reason
# other than speed of coding: you could quite easily implement the same logic
# and pattern without them.
# 
# Starting with `$ ->` means the code is executed after the dom ready event.
$ ->
  
  # `LocationBar` applies dynamic behaviour to a jQuery Mobile slider widget,
  # notifying when the slider position changes in response to user input
  # and updating the slider position whenever its distance value changes.
  # 
  # N.b.: we use a very very exponential curve so that at low distance values,
  # a few pixels corresponds to a few hundred meters, while at high values
  # a few pixels corresponds to many kilometers.  This makes the slider
  # "feel right" for users, as when you're filtering very near by, a few
  # you want to be more accurate than when you're filtering large ranges.
  class LocationBar extends Backbone.View
    
    # The first number in the `n` value equation must be the maximum distance
    # value in `km`, in this case, it's half way round the world.
    n: 64999 / 100000000000000
    # The `p` value is the exponential power, i.e.: in this case the curve is
    # to the power of eight.
    p: 8
    
    # Convert a slider value to a distance in meters.
    _toDistance: (value) ->
      @n * Math.pow value, @p
    
    # Convert a distance in meters to a slider value.
    _toValue: (distance) ->
      Math.pow distance/@n, 1/@p
    
    
    # Display a distance value (number in metres) as an (english) human
    # friendly string.  So 100 would be "100m", 1200 would be "1.2km" and 
    # 160000 would be "160km".
    displayDistance: (d) =>
      if d >= 10000
        km = d / 1000
        txt = "#{Math.round(km/10)*10}km"
      else if d >= 1000 # 1234m yields 1.2km
        km = d / 1000
        txt = "#{Math.round(km*10)/10}km"
      else # 123m yields 100m
        txt = "#{Math.round(d/100)*100}m"
      @label.text txt
    
    
    # `notify()` handles `@slider` move events by setting the value of
    # `@distance` to the distance corresponding to the slider position,
    # which will trigger a 'change' event that the `IndexView` picks up on.
    notify: =>
      v = @slider.val()
      d = @_toDistance v
      #console.log "notify: slider value #{parseInt v}, distance #{parseInt d}m"
      @model.set value: d
      @displayDistance(d)
      true
    
    # `update()` handles `@distance` change events by moving the slider to
    # the right position and updating the label.
    update: =>
      d = @model.get 'value'
      v = @_toValue d
      #console.log "update: distance #{parseInt d}m, slider value #{parseInt v}"
      @slider.val(v).slider 'refresh'
      @displayDistance(d)
      true
    
    
    # When `LocationBar` is initialized, we initialize the jQuery Mobile
    # slider, bind `@distance` change events to `@update()` and `@slider`
    # move events to `@notify()`.
    initialize: ->
      @slider = @$ '.location-slider'
      @slider.slider theme: 'c'
      @slider.css display: 'none'
      @slider.before '<span class="distance-label"></span>'
      @label = @$ '.distance-label'
      @model.bind 'change', @update
      @slider.closest('.slider').bind 'touchstart mousedown', =>
        $('body').one 'touchend mouseup', @notify
      # when the jquery mobile code forces the handle to receive focus
      # make sure the scroll is flagged up
      @$('.ui-slider-handle').bind 'focus', -> $(document).trigger 'silentscroll'
    
    
  
  # `IndexPage` is a page view that shows messages filtered by proximity.
  # 
  # Messages are fetched by `ajax()` which sends a GET request for JSON
  # data to `/query?latitude=...&longitude=...`, adding a `distance=...`
  # parameter if the `@distance` value has been set.
  # 
  # Because the `@distance` value isn't set for the first request, the
  # result is to do an initial query without a distance (allowing the
  # back end to calculate the right distance using the
  # adequate-result-volume algorithm.
  # 
  # Subsequent queries are triggered by `@distance` value changes, which
  # derive from `LocationBar.slider` position changes.  This means that
  # each time the user moves the slider, we make a new ajax request.
  class IndexPage extends Backbone.View
    
    query_url: '/query'
    should_ignore_distance_change = false
    
    # `ajax()` makes a new query to the server to `@query_url`, passing
    # the latlng and any distance through as GET parameters.
    # 
    # When the response comes back, we get a `data` dict with `results`
    # list and `distance` value.  We loop through the results and append a
    # `<li />` to the `<ul class="listings" />` dom element for each one.
    # 
    # If the distance value has changed, we update the slider position
    # using the `@should_ignore_distance_change` to avoid triggering
    # another ajax query.
    ajax: =>
      $.ajax
        url: @query_url
        data:
          distance: @distance.get 'value'
          latitude: @here.latitude
          longitude: @here.longitude
        dataType: 'json'
        success: (data) => 
          for item in data.results
            @listings.append '<li>' + item + '</li>'
          if 'distance' of data and data.distance
            @should_ignore_distance_change = true
            @distance.set value: data.distance
            @should_ignore_distance_change = false
          @listings.listview 'refresh'
        
    
    
    # When `@distance`'s value changes we either ignore it if we caused
    # the change, or clear the message listings and trigger an `ajax()`
    # request.
    handleDistanceChange: =>
      if @should_ignore_distance_change
        @should_ignore_distance_change = false
      else
        @listings.html ''
        @ajax()
      true
    
    
    # When `IndexPage` is initialized, we bind to `@distance` change events
    # initialize a `LocationBar` and make an `ajax()` request.
    initialize: ->
      @here = @options.here
      @distance = @options.distance
      @distance.bind 'change', @handleDistanceChange
      @listings = @$ 'ul.listings'
      @location_bar = new LocationBar
        el: @$ '.location-bar'
        model: @distance
      @ajax()
    
    
  
  # Initialize `IndexPage` with the user's current location.  (N.b.: this
  # code should really be within a pageinit handler and we should cache
  # the user's location to avoid waiting *each* time, etc.).
  # 
  # The element show / hiding is to display the "fetching location..."
  # message so the user knows what's going on behind the scenes.
  $('#location-bar').hide()
  $.geolocation.find (coords) =>
      $('#loading-message').hide()
      $('#location-bar').show()
      page = new IndexPage
        el: $ '#index-page'
        distance: new Backbone.Model
        here: coords
      
  
  
