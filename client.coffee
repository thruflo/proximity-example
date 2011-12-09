$ ->
  
  # `LocationBar` applies dynamic behaviour to a jQuery Mobile slider widget.
  class LocationBar extends Backbone.View
    n: 64999 / 100000000000000
    p: 8
    _toDistance: (value) ->
      @n * Math.pow value, @p
    
    _toValue: (distance) ->
      Math.pow distance/@n, 1/@p
    
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
    
    notify: =>
      v = @slider.val()
      d = @_toDistance v
      #console.log "notify: slider value #{parseInt v}, distance #{parseInt d}m"
      @model.set value: d
      @displayDistance(d)
      true
    
    update: =>
      d = @model.get 'value'
      v = @_toValue d
      #console.log "update: distance #{parseInt d}m, slider value #{parseInt v}"
      @slider.val(v).slider 'refresh'
      @displayDistance(d)
      true
    
    initialize: ->
      # init the jquery.mobile slider
      @slider = @$ '.location-slider'
      @slider.slider theme: 'c'
      # Override the value display.
      @slider.css display: 'none'
      @slider.before '<span class="distance-label"></span>'
      @label = @$ '.distance-label'
      # when @distance changes, update the slider
      @model.bind 'change', @update
      # when the slider changes, update the distance
      @slider.closest('.slider').bind 'touchstart mousedown', =>
        $('body').one 'touchend mouseup', @notify
      
      # when the jquery mobile code forces the handle to receive focus
      # make sure the scroll is flagged up
      @$('.ui-slider-handle').bind 'focus', -> $(document).trigger 'silentscroll'
    
  
  # `IndexPage` shows messages filtered by proximity.
  class IndexPage extends Backbone.View
    query_url: '/query'
    should_ignore_distance_change = false
    ajax: =>
      $.ajax
        url: @query_url
        data:
          distance: @distance.get 'value'
          latitude: @here.latitude
          longitude: @here.longitude
        dataType: 'json'
        timeout: 4000
        success: (data) => 
          for item in data.results
            @listings.append '<li>' + item + '</li>'
          if 'distance' of data and data.distance
            @should_ignore_distance_change = true
            @distance.set value: data.distance
            @should_ignore_distance_change = false
          @listings.listview 'refresh'
        
    
    handleDistanceChange: =>
      if @should_ignore_distance_change
        @should_ignore_distance_change = false
      else
        @listings.html ''
        @ajax()
      true
    
    initialize: ->
      @here = @options.here
      @distance = @options.distance
      @distance.bind 'change', @handleDistanceChange
      @listings = @$ 'ul.listings'
      @location_bar = new LocationBar
        el: @$ '.location-bar'
        model: @distance
      @ajax()
    
  
  # Initialize `IndexPage` with the user's current location.  (N.b.: should really
  # be within a pageinit handler).
  $('#location-bar').hide()
  $.geolocation.find (coords) =>
      $('#loading-message').hide()
      $('#location-bar').show()
      page = new IndexPage
        el: $ '#index-page'
        distance: new Backbone.Model
        here: coords
      
  
