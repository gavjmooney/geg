graph [
  directed 0
  node [
    id 0
    label "Alpha"
    graphics [
      x 0.0
      y 0.0
      w 40.0
      h 30.0
      type "ellipse"
      fill "#FF0000"
    ]
  ]
  node [
    id 1
    label "Beta"
    graphics [
      x 100.0
      y 50.0
      w 60.0
      h 20.0
      type "rectangle"
      fill "#00FF00"
    ]
  ]
  edge [
    source 0
    target 1
    label "bend-edge"
    weight 2.5
    graphics [
      fill "#0000FF"
      width 2.5
      smoothBends 0
      Line [
        point [ x 0.0 y 0.0 ]
        point [ x 25.0 y 25.0 ]
        point [ x 75.0 y 25.0 ]
        point [ x 100.0 y 50.0 ]
      ]
    ]
  ]
]
